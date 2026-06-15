"""
Accounts views — login, register, logout, profile, password change.
Security: rate limiting tracked manually (no external package needed),
brute-force detection via failed attempt counting.
"""
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.http import require_POST

from .models import User

logger = logging.getLogger('nexus')


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


def _check_rate_limit(key, limit=5, window=300):
    """Return True if request should be blocked (too many attempts)."""
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, window)
    return False


def _record_failed_login(ip, username):
    """Track failed logins and create security alert if threshold exceeded."""
    fail_key = f'login_fail_{ip}'
    count = cache.get(fail_key, 0) + 1
    cache.set(fail_key, count, 900)  # 15 min window
    if count >= 5:
        try:
            from observability.models import SecurityAlert
            SecurityAlert.objects.get_or_create(
                alert_type='multiple_fails',
                ip_address=ip,
                is_resolved=False,
                defaults={
                    'severity': 'high',
                    'description': f'{count} failed login attempts from {ip} (username: {username})',
                    'extra_data': {'ip': ip, 'username': username, 'count': count},
                }
            )
        except Exception:
            pass


def register_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        ip = _get_client_ip(request)
        rate_key = f'register_{ip}'
        if _check_rate_limit(rate_key, limit=5, window=3600):
            messages.error(request, 'Too many registration attempts. Please try again later.')
            return render(request, 'auth/register.html')

        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm  = request.POST.get('confirm_password', '')
        role     = request.POST.get('role', 'user')

        # Validation
        if not username or not email or not password:
            messages.error(request, 'All fields are required.')
            return render(request, 'auth/register.html')
        if len(username) < 3 or len(username) > 30:
            messages.error(request, 'Username must be 3–30 characters.')
            return render(request, 'auth/register.html')
        if password != confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/register.html')
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'auth/register.html')
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'Username already taken.')
            return render(request, 'auth/register.html')
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'auth/register.html')
        if role not in ('user', 'creator'):
            role = 'user'

        user = User.objects.create_user(
            username=username, email=email, password=password, role=role
        )
        login(request, user)

        # Log audit
        try:
            from observability.models import AuditLog
            AuditLog.objects.create(
                user=user, action='create',
                description=f'New {role} registered: {username}',
                ip_address=ip,
            )
        except Exception:
            pass

        # Fire workflow event
        try:
            from automation.engine import WorkflowEngine
            WorkflowEngine.fire('user.registered', {
                'user_id': user.pk, 'user_email': user.email,
                'username': user.username, 'role': user.role,
            })
        except Exception:
            pass

        messages.success(request, f'Welcome to NEXUS, {user.username}!')
        if role == 'creator':
            return redirect('/creator/')
        return redirect('/')

    return render(request, 'auth/register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        ip       = _get_client_ip(request)
        rate_key = f'login_{ip}'

        if _check_rate_limit(rate_key, limit=10, window=300):
            messages.error(request, 'Too many login attempts. Please wait 5 minutes.')
            return render(request, 'auth/login.html', {'blocked': True})

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user:
            # Reset fail counter on success
            cache.delete(f'login_fail_{ip}')
            login(request, user)

            # Audit log
            try:
                from observability.models import AuditLog
                AuditLog.objects.create(
                    user=user, action='login',
                    description=f'Login from {ip}',
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                )
            except Exception:
                pass

            next_url = request.GET.get('next', '')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)

            if user.is_admin():
                return redirect('/admin-panel/')
            elif user.is_creator():
                return redirect('/creator/')
            return redirect('/')

        else:
            _record_failed_login(ip, username)
            messages.error(request, 'Invalid username or password.')
            logger.warning('Failed login: username=%s ip=%s', username, ip)

    return render(request, 'auth/login.html')


@login_required
def logout_view(request):
    try:
        from observability.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action='logout',
            description='User logged out',
            ip_address=_get_client_ip(request),
        )
    except Exception:
        pass
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('/')


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action', 'profile')

        if action == 'profile':
            user.email      = request.POST.get('email', user.email).strip()
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name  = request.POST.get('last_name', '').strip()
            user.bio        = request.POST.get('bio', '').strip()
            if 'avatar' in request.FILES:
                user.avatar = request.FILES['avatar']
            user.save()
            messages.success(request, 'Profile updated successfully.')

        elif action == 'password':
            current  = request.POST.get('current_password', '')
            new_pass = request.POST.get('new_password', '')
            confirm  = request.POST.get('confirm_password', '')
            if not user.check_password(current):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_pass) < 8:
                messages.error(request, 'New password must be at least 8 characters.')
            elif new_pass != confirm:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_pass)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')

        return redirect('profile')

    # Wallet info — only relevant for creators/admins who can actually earn money
    wallet = None
    if user.is_creator():
        try:
            wallet = user.wallet
        except Exception:
            pass

    download_history = []
    try:
        from accounts.models import DownloadHistory
        download_history = DownloadHistory.objects.filter(user=user).order_by('-downloaded_at')[:20]
    except Exception:
        pass

    return render(request, 'auth/profile.html', {
        'wallet': wallet,
        'download_history': download_history,
    })