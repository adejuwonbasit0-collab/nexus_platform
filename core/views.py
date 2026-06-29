"""
Core admin panel views — dashboard, content management, user management,
settings, analytics, monetization, notifications.
"""
import json
import logging
from datetime import timedelta, datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.utils import timezone

from accounts.models import User
from content.models import Content
from .models import SiteSettings, Notification, AIProviderSettings
from .utils import notify

logger = logging.getLogger('nexus')


def _admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            return redirect('/auth/login/?next=' + request.path)
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _creator_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/auth/login/?next=' + request.path)
        if not (request.user.is_creator() or request.user.is_admin()):
            messages.error(request, 'Creator account required.')
            return redirect('/')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ── Admin Dashboard ────────────────────────────────────────────────────────────

@_admin_required
def admin_dashboard(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Core stats
    stats = {
        'total_users':    User.objects.count(),
        'new_users_week': User.objects.filter(date_joined__gte=week_ago).count(),
        'total_content':  Content.objects.count(),
        'pending_content': Content.objects.filter(status='pending').count(),
        'approved_content': Content.objects.filter(status='approved').count(),
        'rejected_content': Content.objects.filter(status='rejected').count(),
    }

    # Revenue stats
    try:
        from monetization.models import Payment, Earning, WithdrawalRequest
        stats['revenue_total']   = Payment.objects.filter(status='completed').aggregate(t=Sum('amount'))['t'] or 0
        stats['revenue_month']   = Payment.objects.filter(status='completed', created_at__gte=month_ago).aggregate(t=Sum('amount'))['t'] or 0
        stats['pending_withdrawals'] = WithdrawalRequest.objects.filter(status='pending').count()
        stats['total_earnings']  = Earning.objects.aggregate(t=Sum('amount'))['t'] or 0
    except Exception:
        stats.update({'revenue_total': 0, 'revenue_month': 0, 'pending_withdrawals': 0, 'total_earnings': 0})

    # Recent content pending moderation
    pending_content = Content.objects.filter(status='pending').select_related('creator').order_by('-created_at')[:10]

    # Recent users
    recent_users = User.objects.order_by('-date_joined')[:8]

    # Module counts
    module_stats = {}
    try:
        from music.models import Track
        module_stats['tracks'] = Track.objects.count()
    except Exception:
        module_stats['tracks'] = Content.objects.filter(content_type='music').count()
    try:
        from movies.models import Movie
        module_stats['movies'] = Movie.objects.count()
    except Exception:
        module_stats['movies'] = Content.objects.filter(content_type='video').count()
    try:
        from blog.models import Post
        module_stats['posts'] = Post.objects.count()
    except Exception:
        module_stats['posts'] = Content.objects.filter(content_type='blog').count()
    try:
        from images.models import Image
        module_stats['images'] = Image.objects.count()
    except Exception:
        module_stats['images'] = Content.objects.filter(content_type='image').count()

    # Unread notifications (for the admin user)
    unread_notifs = Notification.objects.filter(user=request.user, is_read=False).count()

    # System health quick check
    try:
        from observability.health import SystemHealthChecker
        health = SystemHealthChecker().get_metrics()
    except Exception:
        health = {'overall': 'unknown'}

    # Open security alerts
    try:
        from observability.models import SecurityAlert
        open_alerts = SecurityAlert.objects.filter(is_resolved=False).count()
    except Exception:
        open_alerts = 0

    return render(request, 'admin_panel/dashboard.html', {
        'stats': stats,
        'module_stats': module_stats,
        'pending_content': pending_content,
        'recent_users': recent_users,
        'unread_notifs': unread_notifs,
        'health': health,
        'open_alerts': open_alerts,
    })


# ── Content Management ────────────────────────────────────────────────────────

@_admin_required
def admin_content(request):
    qs = Content.objects.filter(is_ai_generated=False).select_related('creator').order_by('-created_at')
    status_f  = request.GET.get('status', '')
    type_f    = request.GET.get('type', '')
    creator_f = request.GET.get('creator', '')
    q_f       = request.GET.get('q', '')
    if status_f:  qs = qs.filter(status=status_f)
    if type_f:    qs = qs.filter(content_type=type_f)
    if creator_f: qs = qs.filter(creator__username__icontains=creator_f)
    if q_f:       qs = qs.filter(Q(title__icontains=q_f) | Q(creator__username__icontains=q_f))
    paginator = Paginator(qs, 25)
    page      = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/content.html', {
        'page': page,
        'filter_status': status_f, 'filter_type': type_f,
        'filter_q': q_f, 'filter_creator': creator_f,
    })


@_admin_required
@require_POST
def admin_approve_content(request, pk):
    content = get_object_or_404(Content, pk=pk)
    content.status = 'approved'
    content.save(update_fields=['status'])
    notify(content.creator, 'content_approved', '✅ Content Approved',
           f'Your upload "{content.title}" has been approved and is now live.',
           link=f'/content/{content.pk}/')
    try:
        from automation.engine import WorkflowEngine
        WorkflowEngine.fire('content.approved', {
            'content_id': content.pk, 'content_title': content.title,
            'user_id': content.creator.pk, 'user_email': content.creator.email,
        })
    except Exception:
        pass
    messages.success(request, f'"{content.title}" approved.')
    return redirect(request.META.get('HTTP_REFERER', 'admin_content'))


@_admin_required
@require_POST
def admin_reject_content(request, pk):
    content = get_object_or_404(Content, pk=pk)
    reason  = request.POST.get('reason', 'Does not meet platform guidelines.')
    content.status = 'rejected'
    content.save(update_fields=['status'])
    notify(content.creator, 'content_rejected', '❌ Content Rejected',
           f'Your upload "{content.title}" was rejected. Reason: {reason}',
           link='/creator/')
    try:
        from automation.engine import WorkflowEngine
        WorkflowEngine.fire('content.rejected', {
            'content_id': content.pk, 'content_title': content.title,
            'user_id': content.creator.pk, 'user_email': content.creator.email,
            'reason': reason,
        })
    except Exception:
        pass
    messages.success(request, f'"{content.title}" rejected.')
    return redirect(request.META.get('HTTP_REFERER', 'admin_content'))


@_admin_required
@require_POST
def admin_delete_content(request, pk):
    content = get_object_or_404(Content, pk=pk)
    title = content.title
    content.delete()
    messages.success(request, f'"{title}" deleted.')
    return redirect('admin_content')


@_admin_required
def admin_upload_content(request):
    from core.utils import validate_upload, validate_thumbnail
    if request.method == 'POST':
        content_type = request.POST.get('content_type', '')
        title        = request.POST.get('title', '').strip()
        description  = request.POST.get('description', '').strip()
        tier         = request.POST.get('tier', 'free')
        file_obj     = request.FILES.get('file')
        thumb_obj    = request.FILES.get('thumbnail')

        err = validate_upload(file_obj, content_type) or validate_thumbnail(thumb_obj)
        if err:
            messages.error(request, err)
        elif not title:
            messages.error(request, 'Title is required.')
        else:
            price = request.POST.get('price', '0') or '0'
            c = Content(
                creator=request.user,
                title=title,
                description=description,
                content_type=content_type,
                tier=tier,
                status='approved',
                price=float(price),
            )
            if file_obj:
                c.file = file_obj
            if thumb_obj:
                c.thumbnail = thumb_obj
            if content_type == 'blog':
                c.body = request.POST.get('body', '')
            c.save()
            messages.success(request, f'"{c.title}" uploaded and published.')
            return redirect('admin_content')
    return render(request, 'admin_panel/upload.html', {
        'content_types': Content.TYPE_CHOICES,
        'tiers': Content.TIER_CHOICES,
    })


# ── User Management ────────────────────────────────────────────────────────────

@_admin_required
def admin_users(request):
    qs = User.objects.order_by('-date_joined')
    q     = request.GET.get('q', '')
    role  = request.GET.get('role', '')
    if q:    qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if role: qs = qs.filter(role=role)

    paginator = Paginator(qs, 30)
    page      = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/users.html', {
        'page': page, 'roles': User.ROLE_CHOICES,
        'filter_q': q, 'filter_role': role,
    })


@_admin_required
def admin_user_detail(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_role':
            new_role = request.POST.get('role', user_obj.role)
            if new_role in [r[0] for r in User.ROLE_CHOICES]:
                old_role = user_obj.role
                user_obj.role = new_role
                user_obj.save(update_fields=['role'])
                messages.success(request, f'Role changed: {old_role} → {new_role}')
        elif action == 'toggle_active':
            user_obj.is_active = not user_obj.is_active
            user_obj.save(update_fields=['is_active'])
            messages.success(request, f'User {"activated" if user_obj.is_active else "deactivated"}.')
        elif action == 'grant_premium':
            from monetization.models import SubscriptionPlan
            from django.utils import timezone
            from datetime import timedelta
            plan = SubscriptionPlan.objects.filter(is_active=True).first()
            if plan:
                user_obj.subscription_plan = plan
                user_obj.subscription_expiry = timezone.now() + timedelta(days=30)
                user_obj.save(update_fields=['subscription_plan', 'subscription_expiry'])
                messages.success(request, f'Premium granted to {user_obj.username} for 30 days.')
            else:
                messages.error(request, 'No subscription plan found. Create one in Payment Settings.')
        return redirect('admin_user_detail', pk=pk)

    user_content = Content.objects.filter(creator=user_obj).order_by('-created_at')[:20]
    wallet = None
    try:
        wallet = user_obj.wallet
    except Exception:
        pass
    audit_logs = []
    try:
        from observability.models import AuditLog
        audit_logs = AuditLog.objects.filter(user=user_obj).order_by('-timestamp')[:20]
    except Exception:
        pass

    return render(request, 'admin_panel/user_detail.html', {
        'user_obj': user_obj,
        'user_content': user_content,
        'wallet': wallet,
        'audit_logs': audit_logs,
        'roles': User.ROLE_CHOICES,
    })


# ── Analytics ─────────────────────────────────────────────────────────────────

@_admin_required
def admin_analytics(request):
    now = timezone.now()
    user_growth = []
    for i in range(29, -1, -1):
        day = now - timedelta(days=i)
        user_growth.append({'date': day.strftime('%m/%d'), 'count': User.objects.filter(date_joined__date=day.date()).count()})

    content_by_type = list(Content.objects.values('content_type').annotate(count=Count('id')).order_by('-count'))

    # Safe related_name lookup
    try:
        top_creators = list(User.objects.filter(role='creator').annotate(content_count=Count('contents')).order_by('-content_count')[:10])
    except Exception:
        try:
            top_creators = list(User.objects.filter(role='creator').annotate(content_count=Count('contents')).order_by('-content_count')[:10])
        except Exception:
            top_creators = list(User.objects.filter(role='creator')[:10])
            for c in top_creators:
                c.content_count = Content.objects.filter(creator=c).count()

    revenue_data = []
    total_revenue = 0
    try:
        from monetization.models import Payment
        for i in range(29, -1, -1):
            day = now - timedelta(days=i)
            amount = Payment.objects.filter(status='completed', created_at__date=day.date()).aggregate(t=Sum('amount'))['t'] or 0
            revenue_data.append({'date': day.strftime('%m/%d'), 'amount': float(amount)})
        total_revenue = Payment.objects.filter(status='completed').aggregate(t=Sum('amount'))['t'] or 0
    except Exception:
        revenue_data = [{'date': (now - timedelta(days=i)).strftime('%m/%d'), 'amount': 0} for i in range(29, -1, -1)]

    from movies.models import Movie
    from music.models import Track
    from images.models import Image
    from blog.models import Post

    return render(request, 'admin_panel/analytics.html', {
        'user_growth':     json.dumps(user_growth),
        'content_by_type': json.dumps(content_by_type),
        'revenue_data':    json.dumps(revenue_data),
        'top_creators':    top_creators,
        'total_users':     User.objects.count(),
        'total_content':   Content.objects.count(),
        'total_revenue':   total_revenue,
        'movies_count':    Movie.objects.count(),
        'music_count':     Track.objects.count(),
        'images_count':    Image.objects.count(),
        'blog_count':      Post.objects.count(),
    })


# ── Settings ──────────────────────────────────────────────────────────────────

@_admin_required
def admin_settings(request):
    settings_qs = SiteSettings.objects.all()
    site = {s.key: s.value for s in settings_qs}

    if request.method == 'POST':
        keys = ['site_name', 'site_description', 'site_url',
                'contact_email', 'support_email',
                'max_upload_size_mb', 'enable_registration',
                'default_content_tier']
        for key in keys:
            val = request.POST.get(key, '')
            SiteSettings.objects.update_or_create(key=key, defaults={'value': val})
        from django.core.cache import cache
        cache.clear()
        messages.success(request, 'Settings saved.')
        return redirect('admin_settings')

    return render(request, 'admin_panel/settings.html', {'site': site})


@_admin_required
def admin_ai_settings(request):
    providers = ['openai', 'anthropic', 'stability']
    objs = {p: AIProviderSettings.objects.filter(provider=p).first() for p in providers}

    if request.method == 'POST':
        for p in providers:
            key = request.POST.get(f'{p}_key', '').strip()
            if key:
                AIProviderSettings.objects.update_or_create(
                    provider=p,
                    defaults={'api_key': key, 'is_active': request.POST.get(f'{p}_active') == 'on'}
                )
            else:
                AIProviderSettings.objects.filter(provider=p).update(
                    is_active=request.POST.get(f'{p}_active') == 'on'
                )
        messages.success(request, 'AI settings saved.')
        return redirect('admin_ai_settings')

    return render(request, 'admin_panel/ai_settings.html', {'objs': objs, 'providers': providers})


@_admin_required
def admin_payment_settings(request):
    from monetization.models import PaymentSettings, SubscriptionPlan
    cfg = PaymentSettings.get_active() or PaymentSettings()
    plans = SubscriptionPlan.objects.all().order_by('order', 'price')

    if request.method == 'POST':
        action = request.POST.get('action', 'payment')
        if action == 'payment':
            cfg.public_key = request.POST.get('public_key', '').strip()
            cfg.currency   = request.POST.get('currency', 'NGN')
            cfg.is_active  = True
            cfg.save()
            messages.success(request, 'Payment settings saved. Secret key must be set in environment variables.')

        elif action == 'create_plan':
            import json as _json
            features_raw = request.POST.get('features', '')
            features = [f.strip() for f in features_raw.split('\n') if f.strip()]
            SubscriptionPlan.objects.create(
                name=request.POST.get('plan_name', ''),
                price=request.POST.get('plan_price', 0),
                currency=request.POST.get('plan_currency', 'NGN'),
                interval=request.POST.get('plan_interval', 'monthly'),
                features=features,
                is_featured=request.POST.get('plan_featured') == 'on',
                is_active=True,
            )
            messages.success(request, 'Subscription plan created.')

        elif action == 'delete_plan':
            SubscriptionPlan.objects.filter(pk=request.POST.get('plan_pk')).delete()
            messages.success(request, 'Plan deleted.')

        return redirect('admin_payment_settings')

    return render(request, 'admin_panel/payment_settings.html', {'cfg': cfg, 'plans': plans})


# ── Monetization Center ────────────────────────────────────────────────────────

@_admin_required
def admin_cms_menus(request):
    """Admin view for CMS menus."""
    from cms.models import Menu, MenuItem
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'create_menu':
            name = request.POST.get('name', '').strip()
            location = request.POST.get('location', 'primary')
            if name:
                Menu.objects.get_or_create(name=name, defaults={'location': location, 'is_active': True})
                messages.success(request, f'Menu "{name}" created.')
        return redirect(request.path)
    menus = Menu.objects.prefetch_related('items').all()
    return render(request, 'admin_panel/cms/menus.html', {'menus': menus})


@_admin_required
def admin_monetization(request):
    from monetization.models import Payment, Earning, WithdrawalRequest, Coupon, SubscriptionPlan

    # Stats
    stats = {
        'total_revenue': Payment.objects.filter(status='completed').aggregate(t=Sum('amount'))['t'] or 0,
        'total_earnings': Earning.objects.aggregate(t=Sum('amount'))['t'] or 0,
        'pending_withdrawals_count': WithdrawalRequest.objects.filter(status='pending').count(),
        'pending_withdrawals_amount': WithdrawalRequest.objects.filter(status='pending').aggregate(t=Sum('amount'))['t'] or 0,
    }

    recent_payments = Payment.objects.select_related('user', 'content').order_by('-created_at')[:20]
    pending_withdrawals = WithdrawalRequest.objects.select_related('user').filter(status='pending').order_by('-created_at')
    plans = SubscriptionPlan.objects.all().order_by('order', 'price')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve_withdrawal':
            wr = get_object_or_404(WithdrawalRequest, pk=request.POST.get('withdrawal_pk'))
            wr.status       = 'approved'
            wr.processed_by = request.user
            wr.processed_at = timezone.now()
            wr.admin_note   = request.POST.get('admin_note', '')
            wr.save()
            notify(wr.user, 'payout', '✅ Withdrawal Approved',
                   f'Your withdrawal of {wr.amount} has been approved and will be processed shortly.')
            try:
                from automation.engine import WorkflowEngine
                WorkflowEngine.fire('withdrawal.approved', {
                    'user_id': wr.user.pk, 'user_email': wr.user.email,
                    'amount': str(wr.amount),
                })
            except Exception:
                pass
            messages.success(request, 'Withdrawal approved.')

        elif action == 'reject_withdrawal':
            wr = get_object_or_404(WithdrawalRequest, pk=request.POST.get('withdrawal_pk'))
            wr.status       = 'rejected'
            wr.processed_by = request.user
            wr.processed_at = timezone.now()
            wr.admin_note   = request.POST.get('admin_note', '')
            wr.save()
            # Refund wallet
            try:
                wr.wallet.credit(wr.amount, reason='Withdrawal rejected — refunded', reference=f'REFUND-WR-{wr.pk}')
            except Exception:
                pass
            notify(wr.user, 'payout', '❌ Withdrawal Rejected',
                   f'Your withdrawal of {wr.amount} was rejected. The amount has been returned to your wallet.')
            messages.success(request, 'Withdrawal rejected and funds returned to wallet.')

        elif action == 'create_plan':
            name  = request.POST.get('name', '').strip()
            price = request.POST.get('price', 0)
            if name:
                from django.utils.text import slugify
                import uuid
                slug_base = slugify(name) or str(uuid.uuid4())[:8]
                slug = slug_base; ctr = 1
                while SubscriptionPlan.objects.filter(slug=slug).exists():
                    slug = f'{slug_base}-{ctr}'; ctr += 1
                raw_features = request.POST.get('features', '')
                feat_list = [f.strip() for f in raw_features.splitlines() if f.strip()]
                SubscriptionPlan.objects.create(
                    name=name, slug=slug, price=price,
                    interval=request.POST.get('billing_cycle', 'monthly'),
                    features=feat_list,
                    is_active=request.POST.get('is_active') == 'on',
                )
                messages.success(request, f'Plan "{name}" created.')

        elif action == 'delete_plan':
            get_object_or_404(SubscriptionPlan, pk=request.POST.get('plan_pk')).delete()
            messages.success(request, 'Plan deleted.')

        elif action == 'toggle_plan':
            plan = get_object_or_404(SubscriptionPlan, pk=request.POST.get('plan_pk'))
            plan.is_active = not plan.is_active
            plan.save(update_fields=['is_active'])
            messages.success(request, f'Plan "{plan.name}" {"activated" if plan.is_active else "deactivated"}.')

        return redirect('admin_monetization')

    return render(request, 'admin_panel/monetization.html', {
        'stats': stats,
        'recent_payments': recent_payments,
        'pending_withdrawals': pending_withdrawals,
        'plans': plans,
    })


# ── Series Manager ────────────────────────────────────────────────────────────

@_admin_required
def admin_series(request):
    from movies.models import Series
    series = Series.objects.prefetch_related('seasons__episodes').order_by('-created_at')
    return render(request, 'admin_panel/series.html', {'series': series})


@_admin_required
def admin_create_series(request):
    from movies.models import Series, Genre
    if request.method == 'POST':
        from django.utils.text import slugify
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Title is required.')
            return redirect('admin_create_series')
        base_slug = slugify(title)
        slug, n = base_slug, 1
        while Series.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{n}'; n += 1
        s = Series(
            title=title,
            slug=slug,
            description=request.POST.get('description', ''),
            is_published=request.POST.get('is_published') == 'on',
            is_premium=request.POST.get('tier') == 'premium',
            release_year=int(request.POST.get('release_year', 2024) or 2024),
            uploaded_by=request.user,
        )
        if 'thumbnail' in request.FILES:
            s.thumbnail = request.FILES['thumbnail']
        s.save()
        genre_pks = request.POST.getlist('genres')
        if genre_pks:
            s.genres.set(Genre.objects.filter(pk__in=genre_pks))
        # Mirror to Content so it shows in All Content
        try:
            Content.objects.get_or_create(
                title=s.title, content_type='video', creator=request.user,
                defaults={'description': s.description, 'status': 'approved', 'tier': 'premium' if s.is_premium else 'free'}
            )
        except Exception:
            pass
        messages.success(request, f'Series "{s.title}" created. Now add episodes.')
        return redirect('admin_series')
    genres = Genre.objects.all()
    return render(request, 'admin_panel/series_form.html', {'genres': genres})


@_admin_required
def admin_add_episode(request, series_pk):
    from movies.models import Series, Season, Episode
    series = get_object_or_404(Series, pk=series_pk)
    if request.method == 'POST':
        season_num = int(request.POST.get('season', 1))
        season, _  = Season.objects.get_or_create(series=series, number=season_num)
        ep = Episode(
            season=season,
            number=int(request.POST.get('episode_number', 1)),
            title=request.POST.get('title', ''),
            description=request.POST.get('description', ''),
            is_published=request.POST.get('is_published') == 'on',
            duration=int(request.POST.get('duration', 0) or 0),
        )
        f = request.FILES.get('file') or request.FILES.get('video_file')
        if f: ep.video_file = f
        if 'thumbnail' in request.FILES: ep.thumbnail = request.FILES['thumbnail']
        ep.save()
        messages.success(request, f'Episode "{ep.title}" added to Season {season_num}.')
        if request.POST.get('add_another'):
            return redirect(f'/admin-panel/series/{series_pk}/episode/')
        return redirect('admin_series')
    seasons = series.seasons.prefetch_related('episodes').order_by('number')
    last_season = seasons.last()
    next_ep = (last_season.episodes.count() + 1) if last_season else 1
    return render(request, 'admin_panel/episode_form.html', {
        'series': series, 'seasons': seasons, 'next_episode_number': next_ep,
    })


# ── Categories ────────────────────────────────────────────────────────────────

@_admin_required
def admin_categories(request):
    """Manage content categories across all modules."""
    movie_genres = []
    music_genres = []
    blog_cats    = []
    image_cats   = []
    try:
        from movies.models import Genre as MovieGenre
        movie_genres = MovieGenre.objects.all()
    except Exception:
        pass
    try:
        from music.models import Genre as MusicGenre
        music_genres = MusicGenre.objects.all()
    except Exception:
        pass
    try:
        from blog.models import Category as BlogCat
        blog_cats = BlogCat.objects.all()
    except Exception:
        pass
    try:
        from images.models import Category as ImgCat
        image_cats = ImgCat.objects.all()
    except Exception:
        pass

    if request.method == 'POST':
        module = request.POST.get('module', '')
        action = request.POST.get('action', 'create')
        name   = request.POST.get('name', '').strip()
        if name and action == 'create':
            from django.utils.text import slugify
            slug = slugify(name)
            if module == 'movies':
                from movies.models import Genre as G
                G.objects.get_or_create(name=name, defaults={'slug': slug})
            elif module == 'music':
                from music.models import Genre as G
                G.objects.get_or_create(name=name, defaults={'slug': slug})
            elif module == 'blog':
                from blog.models import Category as G
                G.objects.get_or_create(name=name, defaults={'slug': slug})
            elif module == 'images':
                from images.models import Category as G
                G.objects.get_or_create(name=name, defaults={'slug': slug})
            messages.success(request, f'Category "{name}" added to {module}.')
        return redirect('admin_categories')

    return render(request, 'admin_panel/categories.html', {
        'movie_genres': movie_genres,
        'music_genres': music_genres,
        'blog_cats': blog_cats,
        'image_cats': image_cats,
    })


# ── Branding ──────────────────────────────────────────────────────────────────

@_admin_required
def admin_branding(request):
    """Redirect to the CMS branding center."""
    return redirect('cms_branding')


# ── Notifications ─────────────────────────────────────────────────────────────

@login_required
def notifications_list(request):
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    paginator = Paginator(notifs, 20)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'notifications/list.html', {'page': page})


@login_required
def notifications_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})


# ── Creator Dashboard ─────────────────────────────────────────────────────────

@_creator_required
def creator_dashboard(request):
    from content.models import Content
    content   = Content.objects.filter(creator=request.user).order_by('-created_at')[:10]
    all_cont  = Content.objects.filter(creator=request.user).order_by('-created_at')
    stats = {
        'total_uploads': all_cont.count(),
        'approved':      all_cont.filter(status='approved').count(),
        'pending':       all_cont.filter(status='pending').count(),
        'total_views':   sum(c.views or 0 for c in all_cont),
    }
    wallet = None
    try:
        wallet = request.user.wallet
    except Exception:
        pass
    recent_earnings = []
    try:
        from monetization.models import Earning
        recent_earnings = Earning.objects.filter(creator=request.user).order_by('-created_at')[:10]
    except Exception:
        pass

    # Data for upload forms
    from music.models import Genre as MusicGenre, Artist, Album
    from images.models import Category as ImageCategory, Tag as ImageTag
    from blog.models import Category as BlogCategory, Tag as BlogTag
    try:
        from movies.models import Genre as MovieGenre
        movie_genres = list(MovieGenre.objects.all())
    except Exception:
        movie_genres = []

    return render(request, 'creator/dashboard.html', {
        'content': content,
        'all_content': all_cont,
        'stats': stats,
        'wallet': wallet,
        'recent_earnings': recent_earnings,
        'music_genres':  list(MusicGenre.objects.all()),
        'artists':       list(Artist.objects.all()),
        'albums':        list(Album.objects.all()),
        'image_cats':    list(ImageCategory.objects.all()),
        'image_tags':    list(ImageTag.objects.all()),
        'blog_cats':     list(BlogCategory.objects.all()),
        'blog_tags':     list(BlogTag.objects.all()),
        'movie_genres':  movie_genres,
        'qualities':     [('SD','SD 480p'),('HD','HD 720p'),('FHD','Full HD 1080p'),('4K','4K Ultra HD')],
    })


@_creator_required
def creator_upload(request):
    if request.method != 'POST':
        return redirect('creator_dashboard')

    content_type = request.POST.get('content_type', '')
    title        = request.POST.get('title', '').strip()
    tier         = request.POST.get('tier', 'free')

    if not title:
        messages.error(request, 'Title is required.')
        return redirect('creator_dashboard')

    # ── MUSIC TRACK ──────────────────────────────────────────────────────────
    if content_type == 'music':
        from music.models import Track, Artist, Genre as MusicGenre, Album
        from django.utils.text import slugify
        import uuid

        audio = request.FILES.get('audio_file') or request.FILES.get('file')
        if not audio:
            messages.error(request, 'Audio file is required.')
            return redirect('creator_dashboard')

        artist_pk = request.POST.get('artist_pk')
        artist_name = request.POST.get('artist_name_new', '').strip()

        if artist_pk:
            artist = Artist.objects.filter(pk=artist_pk).first()
        elif artist_name:
            artist, _ = Artist.objects.get_or_create(
                name=artist_name,
                defaults={'slug': slugify(artist_name) or str(uuid.uuid4())[:8]}
            )
        else:
            messages.error(request, 'Artist name is required.')
            return redirect('creator_dashboard')
        if not artist:
            messages.error(request, 'Invalid artist.')
            return redirect('creator_dashboard')

        genre = MusicGenre.objects.filter(pk=request.POST.get('genre_pk')).first()
        album = Album.objects.filter(pk=request.POST.get('album_pk')).first()

        slug_base = slugify(title) or str(uuid.uuid4())[:8]
        slug = slug_base
        ctr = 1
        while Track.objects.filter(slug=slug).exists():
            slug = f'{slug_base}-{ctr}'; ctr += 1

        track = Track(
            title=title, artist=artist, genre=genre, album=album,
            slug=slug, is_premium=(tier=='premium'),
            lyrics=request.POST.get('lyrics', ''),
            produced_by=request.POST.get('produced_by', ''),
            written_by=request.POST.get('written_by', ''),
            label=request.POST.get('label', ''),
            is_published=False,
        )
        if audio:
            track.audio_file = audio
        cover = request.FILES.get('cover_image') or request.FILES.get('thumbnail')
        if cover:
            track.cover_image = cover
        track.save()

        from content.models import Content
        Content.objects.get_or_create(
            slug=track.slug,
            defaults=dict(
                creator=request.user, title=title,
                content_type='music', tier=tier, status='pending',
                thumbnail=cover, description=request.POST.get('lyrics', '')[:500],
            )
        )
        messages.success(request, f'🎵 "{title}" submitted for review.')

    # ── VIDEO / MOVIE ─────────────────────────────────────────────────────────
    elif content_type == 'video':
        from movies.models import Movie
        from django.utils.text import slugify
        import uuid

        video = request.FILES.get('video_file') or request.FILES.get('file')
        if not video:
            messages.error(request, 'Video file is required.')
            return redirect('creator_dashboard')

        slug_base = slugify(title) or str(uuid.uuid4())[:8]
        slug = slug_base; ctr = 1
        while Movie.objects.filter(slug=slug).exists():
            slug = f'{slug_base}-{ctr}'; ctr += 1

        movie = Movie(
            title=title, slug=slug,
            description=request.POST.get('description', ''),
            release_year=request.POST.get('release_year', '') or None,
            quality=request.POST.get('quality', 'HD'),
            trailer_url=request.POST.get('trailer_url', ''),
            is_premium=(tier=='premium'),
            is_published=False,
            uploaded_by=request.user,
        )
        if video:      movie.video_file = video
        thumb = request.FILES.get('thumbnail')
        if thumb:      movie.thumbnail = thumb
        movie.save()

        from content.models import Content
        Content.objects.get_or_create(
            slug=movie.slug,
            defaults=dict(
                creator=request.user, title=title,
                content_type='video', tier=tier, status='pending',
                thumbnail=thumb,
            )
        )
        messages.success(request, f'🎬 "{title}" submitted for review.')

    # ── IMAGE ─────────────────────────────────────────────────────────────────
    elif content_type == 'image':
        from images.models import Image as Img, Category as ImgCat, Tag as ImgTag
        from django.utils.text import slugify
        import uuid

        img_file = request.FILES.get('image_file') or request.FILES.get('file')
        if not img_file:
            messages.error(request, 'Image file is required.')
            return redirect('creator_dashboard')

        slug_base = slugify(title) or str(uuid.uuid4())[:8]
        slug = slug_base; ctr = 1
        while Img.objects.filter(slug=slug).exists():
            slug = f'{slug_base}-{ctr}'; ctr += 1

        cat = ImgCat.objects.filter(pk=request.POST.get('category_pk')).first()

        img = Img(
            title=title, slug=slug,
            description=request.POST.get('description', ''),
            category=cat,
            resolution=request.POST.get('resolution', 'hd'),
            is_premium=(tier=='premium'),
            is_published=False,
            uploaded_by=request.user,
        )
        if img_file: img.image_file = img_file
        img.save()

        tag_ids = request.POST.getlist('tag_ids')
        if tag_ids:
            img.tags.set(ImgTag.objects.filter(pk__in=tag_ids))

        from content.models import Content
        Content.objects.get_or_create(
            slug=img.slug,
            defaults=dict(
                creator=request.user, title=title,
                content_type='image', tier=tier, status='pending',
            )
        )
        messages.success(request, f'🖼 "{title}" submitted for review.')

    # ── BLOG POST ─────────────────────────────────────────────────────────────
    elif content_type == 'blog':
        from blog.models import Post, Category as BlogCat, Tag as BlogTag
        from django.utils.text import slugify
        import uuid

        slug_base = slugify(title) or str(uuid.uuid4())[:8]
        slug = slug_base; ctr = 1
        while Post.objects.filter(slug=slug).exists():
            slug = f'{slug_base}-{ctr}'; ctr += 1

        cat = BlogCat.objects.filter(pk=request.POST.get('category_pk')).first()

        post = Post(
            title=title, slug=slug,
            author=request.user,
            content=request.POST.get('content', ''),
            excerpt=request.POST.get('excerpt', ''),
            category=cat,
            status='draft',
        )
        img = request.FILES.get('featured_img') or request.FILES.get('thumbnail')
        if img: post.featured_img = img
        post.save()

        tag_ids = request.POST.getlist('tag_ids')
        if tag_ids:
            post.tags.set(BlogTag.objects.filter(pk__in=tag_ids))

        from content.models import Content
        Content.objects.get_or_create(
            slug=post.slug,
            defaults=dict(
                creator=request.user, title=title,
                content_type='blog', tier=tier, status='pending',
            )
        )
        messages.success(request, f'📝 "{title}" saved as draft.')

    else:
        messages.error(request, 'Unknown content type.')

    return redirect('creator_dashboard')


@_creator_required
def creator_withdraw(request):
    """Creator withdrawal request."""
    user   = request.user
    wallet = None
    try:
        wallet = user.wallet
    except Exception:
        messages.error(request, 'No wallet found. Please contact support.')
        return redirect('creator_dashboard')

    if request.method == 'POST':
        from monetization.models import WithdrawalRequest
        amount = request.POST.get('amount', '0')
        try:
            from decimal import Decimal
            amount_dec = Decimal(amount)
            if amount_dec <= 0:
                raise ValueError('Amount must be positive.')
            min_withdrawal = Decimal('1000')
            if amount_dec < min_withdrawal:
                messages.error(request, f'Minimum withdrawal is {min_withdrawal} {wallet.currency}.')
                return redirect('creator_withdraw')
            if amount_dec > wallet.balance:
                messages.error(request, 'Insufficient wallet balance.')
                return redirect('creator_withdraw')

            # Debit wallet (moves to pending)
            wallet.debit(amount_dec, reason='Withdrawal request', reference=f'WR-{user.pk}')

            wr = WithdrawalRequest.objects.create(
                user=user, wallet=wallet,
                amount=amount_dec,
                method=request.POST.get('method', 'bank_transfer'),
                bank_name=request.POST.get('bank_name', ''),
                account_number=request.POST.get('account_number', ''),
                account_name=request.POST.get('account_name', ''),
            )
            try:
                from automation.engine import WorkflowEngine
                WorkflowEngine.fire('withdrawal.requested', {
                    'user_id': user.pk, 'user_email': user.email,
                    'amount': str(amount_dec), 'withdrawal_id': wr.pk,
                })
            except Exception:
                pass
            messages.success(request, f'Withdrawal request for {amount_dec} {wallet.currency} submitted.')
            return redirect('creator_dashboard')
        except (ValueError, Exception) as e:
            messages.error(request, str(e))

    return render(request, 'creator/withdraw.html', {'wallet': wallet})


# ── Per-Module Content Admin Views ────────────────────────────────────────────

@_admin_required
def admin_movies(request):
    """Movies management — all CRUD from admin panel."""
    from movies.models import Movie, Genre, Country, Series
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'toggle_publish':
            m = get_object_or_404(Movie, pk=request.POST.get('pk'))
            m.is_published = not m.is_published
            m.save(update_fields=['is_published'])
            return JsonResponse({'published': m.is_published})
        elif action == 'toggle_featured':
            m = get_object_or_404(Movie, pk=request.POST.get('pk'))
            m.is_featured = not m.is_featured
            m.save(update_fields=['is_featured'])
            return JsonResponse({'featured': m.is_featured})
        elif action == 'delete':
            get_object_or_404(Movie, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Movie deleted.')
            return redirect('admin_movies')
        elif action == 'edit_movie':
            m = get_object_or_404(Movie, pk=request.POST.get('pk'))
            m.title = request.POST.get('title', m.title).strip() or m.title
            m.description = request.POST.get('description', m.description)
            m.release_year = int(request.POST.get('release_year', m.release_year) or m.release_year)
            m.quality = request.POST.get('quality', m.quality)
            m.trailer_url = request.POST.get('trailer_url', m.trailer_url)
            m.is_premium = request.POST.get('is_premium') == 'on'
            m.is_published = request.POST.get('is_published') == 'on'
            if 'thumbnail' in request.FILES:
                m.thumbnail = request.FILES['thumbnail']
            if 'video_file' in request.FILES:
                m.video_file = request.FILES['video_file']
            m.save()
            messages.success(request, f'Movie "{m.title}" updated.')
            return redirect('admin_movies')
        elif action == 'create':
            from django.utils.text import slugify
            title = request.POST.get('title', '').strip()
            if title:
                m = Movie(
                    title=title,
                    description=request.POST.get('description', ''),
                    release_year=int(request.POST.get('release_year', 2024) or 2024),
                    quality=request.POST.get('quality', 'HD'),
                    is_premium=request.POST.get('is_premium') == 'on',
                    is_published=request.POST.get('is_published') == 'on',
                    uploaded_by=request.user,
                    trailer_url=request.POST.get('trailer_url', ''),
                )
                if 'thumbnail' in request.FILES:
                    m.thumbnail = request.FILES['thumbnail']
                if 'video_file' in request.FILES:
                    m.video_file = request.FILES['video_file']
                m.save()
                # ── Mirror to Content ──────────────────────────────────────
                try:
                    from content.models import Content as CI
                    ci = CI.objects.create(
                        creator=request.user, title=title,
                        description=m.description, content_type='video',
                        status='approved' if m.is_published else 'pending',
                        tier='premium' if m.is_premium else 'free',
                    )
                    if m.thumbnail:
                        ci.thumbnail = m.thumbnail; ci.save(update_fields=['thumbnail'])
                except Exception as _mirror_err:
                    import logging; logging.getLogger("nexus").warning(f"Content mirror failed: {_mirror_err}")
                messages.success(request, f'Movie "{title}" created.')
            return redirect('admin_movies')

    # Handle series/season/episode actions
    if request.method == 'POST':
        action = request.POST.get('action','')
        if action == 'create_series':
            from django.utils.text import slugify as _sl
            title = request.POST.get('title','').strip()
            if title:
                base = _sl(title); slug = base; n = 1
                while Series.objects.filter(slug=slug).exists():
                    slug = f'{base}-{n}'; n += 1
                s = Series(
                    title=title, slug=slug,
                    description=request.POST.get('description',''),
                    release_year=int(request.POST.get('release_year',2024) or 2024),
                    is_published=request.POST.get('is_published')=='on',
                    is_premium=request.POST.get('tier')=='premium',
                    uploaded_by=request.user,
                )
                if 'thumbnail' in request.FILES: s.thumbnail = request.FILES['thumbnail']
                s.save()
                gids = request.POST.getlist('genres')
                if gids: s.genres.set(Genre.objects.filter(pk__in=gids))
                try:
                    Content.objects.get_or_create(
                        title=s.title, content_type='video', creator=request.user,
                        defaults={'description': s.description, 'status': 'approved', 'tier': 'premium' if s.is_premium else 'free'}
                    )
                except Exception: pass
                messages.success(request, f'Series "{s.title}" created.')
            return redirect('/admin-panel/movies/?tab=series')
        elif action == 'edit_series':
            s = get_object_or_404(Series, pk=request.POST.get('pk'))
            s.title = request.POST.get('title', s.title).strip() or s.title
            s.description = request.POST.get('description', s.description)
            s.release_year = int(request.POST.get('release_year', s.release_year) or s.release_year)
            s.is_published = request.POST.get('is_published')=='on'
            s.is_premium = request.POST.get('tier')=='premium'
            if 'thumbnail' in request.FILES: s.thumbnail = request.FILES['thumbnail']
            s.save()
            gids = request.POST.getlist('genres')
            if gids: s.genres.set(Genre.objects.filter(pk__in=gids))
            messages.success(request, f'Series "{s.title}" updated.')
            return redirect('/admin-panel/movies/?tab=series')
        elif action == 'delete_series':
            get_object_or_404(Series, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Series deleted.')
            return redirect('/admin-panel/movies/?tab=series')
        elif action == 'add_episode':
            from movies.models import Season as Sn, Episode as Ep
            series = get_object_or_404(Series, pk=request.POST.get('series_pk'))
            season_num = int(request.POST.get('season', 1))
            season, _ = Sn.objects.get_or_create(series=series, number=season_num)
            title = request.POST.get('title','').strip()
            if title:
                ep = Ep(
                    season=season,
                    number=int(request.POST.get('episode_number',1)),
                    title=title,
                    description=request.POST.get('description',''),
                    duration=int(request.POST.get('duration',0) or 0),
                    is_published=request.POST.get('is_published')=='on',
                )
                f = request.FILES.get('file') or request.FILES.get('video_file')
                if f: ep.video_file = f
                if 'thumbnail' in request.FILES: ep.thumbnail = request.FILES['thumbnail']
                ep.save()
                messages.success(request, f'Episode "{ep.title}" added.')
            return redirect('/admin-panel/movies/?tab=series')
        elif action == 'edit_episode':
            from movies.models import Episode as Ep
            ep = get_object_or_404(Ep, pk=request.POST.get('pk'))
            ep.title = request.POST.get('title', ep.title).strip() or ep.title
            ep.description = request.POST.get('description', ep.description)
            ep.number = int(request.POST.get('episode_number', ep.number) or ep.number)
            ep.duration = int(request.POST.get('duration', ep.duration) or ep.duration)
            ep.is_published = request.POST.get('is_published')=='on'
            if request.FILES.get('file'): ep.video_file = request.FILES['file']
            if 'thumbnail' in request.FILES: ep.thumbnail = request.FILES['thumbnail']
            ep.save()
            messages.success(request, f'Episode "{ep.title}" updated.')
            return redirect('/admin-panel/movies/?tab=series')
        elif action == 'delete_episode':
            from movies.models import Episode as Ep
            ep = get_object_or_404(Ep, pk=request.POST.get('pk'))
            ep.delete()
            messages.success(request, 'Episode deleted.')
            return redirect('/admin-panel/movies/?tab=series')

    qs = Movie.objects.select_related('uploaded_by').order_by('-created_at')
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    all_series = Series.objects.prefetch_related('seasons__episodes').order_by('-created_at')
    return render(request, 'admin_panel/modules/movies.html', {
        'page': page, 'q': q,
        'genres': Genre.objects.all(),
        'qualities': Movie.QUALITY,
        'all_series': all_series,
    })


@_admin_required
def admin_music(request):
    """Music management — tracks, artists, genres, albums."""
    from music.models import Track, Artist, Genre, Album
    from django.utils.text import slugify

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Track actions ─────────────────────────────────────────────────────
        if action == 'toggle_publish':
            t = get_object_or_404(Track, pk=request.POST.get('pk'))
            t.is_published = not t.is_published
            t.save(update_fields=['is_published'])
            return JsonResponse({'published': t.is_published})

        elif action == 'toggle_featured':
            t = get_object_or_404(Track, pk=request.POST.get('pk'))
            t.is_featured = not t.is_featured
            t.save(update_fields=['is_featured'])
            return JsonResponse({'featured': t.is_featured})

        elif action == 'toggle_song_of_day':
            Track.objects.update(is_song_of_day=False)
            t = get_object_or_404(Track, pk=request.POST.get('pk'))
            t.is_song_of_day = True
            t.save(update_fields=['is_song_of_day'])
            messages.success(request, f'"{t.title}" is now Song of the Day.')
            return redirect('admin_music')

        elif action == 'delete_track':
            get_object_or_404(Track, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Track deleted.')
            return redirect('admin_music')

        # keep old 'delete' action for backward compat
        elif action == 'delete':
            get_object_or_404(Track, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Track deleted.')
            return redirect('admin_music')

        elif action == 'create_track':
            title     = request.POST.get('title', '').strip()
            artist_pk = request.POST.get('artist_pk', '')
            if title and artist_pk:
                artist = get_object_or_404(Artist, pk=artist_pk)
                genre  = None
                genre_pk = request.POST.get('genre_pk', '')
                if genre_pk:
                    try: genre = Genre.objects.get(pk=genre_pk)
                    except: pass
                # Album
                album = None
                album_pk = request.POST.get('album_pk', '')
                if album_pk:
                    try: album = Album.objects.get(pk=album_pk)
                    except: pass
                base_slug = slugify(title)
                slug, n = base_slug, 1
                while Track.objects.filter(slug=slug).exists():
                    slug = f'{base_slug}-{n}'; n += 1
                track = Track(
                    title=title, artist=artist, genre=genre, album=album,
                    slug=slug,
                    release_year=int(request.POST.get('release_year', 2024) or 2024),
                    lyrics=request.POST.get('lyrics', ''),
                    produced_by=request.POST.get('produced_by', ''),
                    written_by=request.POST.get('written_by', ''),
                    label=request.POST.get('label', ''),
                    is_premium=request.POST.get('is_premium') == 'on',
                    is_published=request.POST.get('is_published') == 'on',
                    is_featured=request.POST.get('is_featured') == 'on',
                    uploaded_by=request.user,
                )
                if 'audio_file' in request.FILES:
                    track.audio_file = request.FILES['audio_file']
                if 'cover_image' in request.FILES:
                    track.cover_image = request.FILES['cover_image']
                track.save()
                # Featured artists (M2M)
                feat_ids = request.POST.getlist('featured_artist_pks')
                if feat_ids:
                    feat_artists = Artist.objects.filter(pk__in=feat_ids)
                    track.featured_artists.set(feat_artists)
                # ── Mirror to Content so it shows in All Content ──────────────
                try:
                    from content.models import Content as ContentItem
                    ct, _ = ContentItem.objects.get_or_create(
                        title=track.title,
                        content_type='music',
                        creator=request.user,
                        defaults={
                            'description': track.lyrics or '',
                            'status': 'approved',
                            'tier': 'premium' if track.is_premium else 'free',
                        }
                    )
                    if track.cover_image:
                        ct.thumbnail = track.cover_image
                        ct.save(update_fields=['thumbnail'])
                except Exception as _mirror_err:
                    import logging; logging.getLogger("nexus").warning(f"Content mirror failed: {_mirror_err}")
                messages.success(request, f'Track "{title}" created.')
            else:
                messages.error(request, 'Title and main artist are required.')
            return redirect('admin_music')

        # ── Artist actions ────────────────────────────────────────────────────
        elif action == 'create_artist':
            name = request.POST.get('name', '').strip()
            if name:
                base_slug = slugify(name)
                slug, n = base_slug, 1
                while Artist.objects.filter(slug=slug).exists():
                    slug = f'{base_slug}-{n}'; n += 1
                artist = Artist(
                    name=name,
                    slug=slug,
                    bio=request.POST.get('bio', ''),
                    country=request.POST.get('country', ''),
                    website=request.POST.get('website', ''),
                    social_instagram=request.POST.get('social_instagram', ''),
                    social_twitter=request.POST.get('social_twitter', ''),
                    social_youtube=request.POST.get('social_youtube', ''),
                    is_verified=request.POST.get('is_verified') == 'on',
                )
                if 'photo' in request.FILES:
                    artist.photo = request.FILES['photo']
                artist.save()
                messages.success(request, f'Artist "{name}" created.')
            else:
                messages.error(request, 'Artist name is required.')
            return redirect('admin_music')

        elif action == 'update_artist':
            pk = request.POST.get('pk')
            artist = get_object_or_404(Artist, pk=pk)
            artist.name = request.POST.get('name', artist.name).strip() or artist.name
            artist.bio  = request.POST.get('bio', artist.bio)
            artist.country = request.POST.get('country', artist.country)
            artist.website = request.POST.get('website', artist.website)
            artist.social_instagram = request.POST.get('social_instagram', artist.social_instagram)
            artist.social_twitter   = request.POST.get('social_twitter', artist.social_twitter)
            artist.social_youtube   = request.POST.get('social_youtube', artist.social_youtube)
            artist.is_verified = request.POST.get('is_verified') == 'on'
            if 'photo' in request.FILES:
                artist.photo = request.FILES['photo']
            artist.save()
            messages.success(request, f'Artist "{artist.name}" updated.')
            return redirect('admin_music')

        elif action == 'delete_artist':
            artist = get_object_or_404(Artist, pk=request.POST.get('pk'))
            name = artist.name
            artist.delete()
            messages.success(request, f'Artist "{name}" deleted.')
            return redirect('admin_music')

        elif action == 'toggle_verified':
            a = get_object_or_404(Artist, pk=request.POST.get('pk'))
            a.is_verified = not a.is_verified
            a.save(update_fields=['is_verified'])
            return JsonResponse({'verified': a.is_verified})

        # ── Genre actions ─────────────────────────────────────────────────────
        elif action == 'create_genre':
            name = request.POST.get('name', '').strip()
            if name:
                base_slug = slugify(name)
                slug, n = base_slug, 1
                while Genre.objects.filter(slug=slug).exists():
                    slug = f'{base_slug}-{n}'; n += 1
                genre, created = Genre.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'name': name,
                        'icon': request.POST.get('icon', '🎵'),
                    }
                )
                if created:
                    messages.success(request, f'Genre "{name}" created.')
                else:
                    messages.warning(request, f'Genre "{name}" already exists.')
            else:
                messages.error(request, 'Genre name is required.')
            return redirect('admin_music')

        elif action == 'delete_genre':
            genre = get_object_or_404(Genre, pk=request.POST.get('pk'))
            name = genre.name
            genre.delete()
            messages.success(request, f'Genre "{name}" deleted.')
            return redirect('admin_music')

        # ── Album actions ─────────────────────────────────────────────────────
        elif action == 'create_album':
            title     = request.POST.get('title', '').strip()
            artist_pk = request.POST.get('artist_pk', '')
            if title and artist_pk:
                artist = get_object_or_404(Artist, pk=artist_pk)
                genre  = None
                genre_pk = request.POST.get('genre_pk', '')
                if genre_pk:
                    try: genre = Genre.objects.get(pk=genre_pk)
                    except: pass
                base_slug = slugify(f'{artist.name}-{title}')
                slug, n = base_slug, 1
                while Album.objects.filter(slug=slug).exists():
                    slug = f'{base_slug}-{n}'; n += 1
                album = Album(
                    title=title, artist=artist, genre=genre, slug=slug,
                    album_type=request.POST.get('album_type', 'album'),
                    release_year=int(request.POST.get('release_year', 2024) or 2024),
                    description=request.POST.get('description', ''),
                    label=request.POST.get('label', ''),
                    is_published=request.POST.get('is_published') == 'on',
                )
                if 'cover_image' in request.FILES:
                    album.cover_image = request.FILES['cover_image']
                album.save()
                messages.success(request, f'Album "{title}" created.')
            else:
                messages.error(request, 'Album title and main artist are required.')
            return redirect('admin_music')

        elif action == 'update_track':
            t = get_object_or_404(Track, pk=request.POST.get('pk'))
            t.title = request.POST.get('title', t.title).strip() or t.title
            artist_pk = request.POST.get('artist_pk')
            if artist_pk:
                try: t.artist = Artist.objects.get(pk=artist_pk)
                except: pass
            genre_pk = request.POST.get('genre_pk')
            if genre_pk:
                try: t.genre = Genre.objects.get(pk=genre_pk)
                except: pass
            t.lyrics = request.POST.get('lyrics', t.lyrics)
            t.is_published = request.POST.get('is_published') == 'on'
            t.is_premium = request.POST.get('is_premium') == 'on'
            if 'audio_file' in request.FILES:
                t.audio_file = request.FILES['audio_file']
            if 'cover_image' in request.FILES:
                t.cover_image = request.FILES['cover_image']
            t.save()
            messages.success(request, f'Track "{t.title}" updated.')
            return redirect('admin_music')

        elif action == 'edit_album':
            album = get_object_or_404(Album, pk=request.POST.get('pk'))
            album.title = request.POST.get('title', album.title).strip() or album.title
            artist_pk = request.POST.get('artist_pk')
            if artist_pk:
                try: album.artist = Artist.objects.get(pk=artist_pk)
                except: pass
            album.release_year = int(request.POST.get('release_year', album.release_year) or album.release_year)
            album.description = request.POST.get('description', album.description)
            if 'cover_image' in request.FILES:
                album.cover_image = request.FILES['cover_image']
            album.save()
            messages.success(request, f'Album "{album.title}" updated.')
            return redirect('admin_music')

        elif action == 'delete_album':
            album = get_object_or_404(Album, pk=request.POST.get('pk'))
            name = album.title
            album.delete()
            messages.success(request, f'Album "{name}" deleted.')
            return redirect('admin_music')

    # ── GET — build context ────────────────────────────────────────────────────
    qs = Track.objects.select_related('artist', 'genre', 'album').prefetch_related('featured_artists').order_by('-created_at')
    q = request.GET.get('q', '')
    tab = request.GET.get('tab', 'tracks')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(artist__name__icontains=q))

    artist_q = request.GET.get('aq', '')
    artist_qs = Artist.objects.annotate(track_count=Count('tracks')).order_by('name')
    if artist_q:
        artist_qs = artist_qs.filter(Q(name__icontains=artist_q) | Q(country__icontains=artist_q))

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))

    artist_paginator = Paginator(artist_qs, 20)
    artist_page = artist_paginator.get_page(request.GET.get('apage', 1))

    albums = Album.objects.select_related('artist', 'genre').annotate(track_count=Count('tracks')).order_by('-created_at')[:50]

    return render(request, 'admin_panel/modules/music.html', {
        'page': page,
        'q': q,
        'tab': tab,
        'artist_page': artist_page,
        'artist_q': artist_q,
        'albums': albums,
        'all_artists': Artist.objects.all().order_by('name'),
        'genres': Genre.objects.all(),
    })


@_admin_required
def admin_blog(request):
    """Blog management."""
    from blog.models import Post, Category
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'toggle_status':
            p = get_object_or_404(Post, pk=request.POST.get('pk'))
            p.status = 'published' if p.status == 'draft' else 'draft'
            p.save(update_fields=['status'])
            return JsonResponse({'status': p.status})
        elif action == 'toggle_featured':
            p = get_object_or_404(Post, pk=request.POST.get('pk'))
            p.is_featured = not p.is_featured
            p.save(update_fields=['is_featured'])
            return JsonResponse({'featured': p.is_featured})
        elif action == 'delete':
            get_object_or_404(Post, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Post deleted.')
            return redirect('admin_blog')
        elif action == 'create':
            title = request.POST.get('title', '').strip()
            if title:
                cat_pk = request.POST.get('category_pk', '')
                cat = None
                if cat_pk:
                    try:
                        from blog.models import Category as BlogCat
                        cat = BlogCat.objects.get(pk=cat_pk)
                    except Exception:
                        pass
                p = Post(
                    title=title, author=request.user,
                    content=request.POST.get('content', ''),
                    excerpt=request.POST.get('excerpt', ''),
                    status=request.POST.get('status', 'draft'),
                    is_featured=request.POST.get('is_featured') == 'on',
                    category=cat,
                )
                if 'featured_img' in request.FILES:
                    p.featured_img = request.FILES['featured_img']
                p.save()
                # ── Mirror to Content ──────────────────────────────────────
                try:
                    from content.models import Content as CI
                    ci = CI.objects.create(
                        creator=request.user, title=title,
                        description=p.excerpt or p.content[:300],
                        content_type='blog',
                        status='approved' if p.status == 'published' else 'pending',
                        tier='free',
                    )
                    if p.featured_img:
                        ci.thumbnail = p.featured_img; ci.save(update_fields=['thumbnail'])
                except Exception as _mirror_err:
                    import logging; logging.getLogger("nexus").warning(f"Content mirror failed: {_mirror_err}")
                messages.success(request, f'Post "{title}" created.')
            return redirect('admin_blog')

    qs = Post.objects.select_related('author', 'category').order_by('-created_at')
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author__username__icontains=q))
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/modules/blog.html', {
        'page': page, 'q': q,
        'categories': Category.objects.all(),
    })


@_admin_required
def admin_images_mgmt(request):
    """Images/gallery management — list, upload, categories."""
    from images.models import Image, Category as ImageCategory
    from django.utils.text import slugify

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'delete':
            get_object_or_404(Image, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Image deleted.')
            return redirect('admin_images')

        elif action == 'toggle_publish':
            img = get_object_or_404(Image, pk=request.POST.get('pk'))
            img.is_published = not img.is_published
            img.save(update_fields=['is_published'])
            return JsonResponse({'published': img.is_published})

        elif action == 'toggle_featured':
            img = get_object_or_404(Image, pk=request.POST.get('pk'))
            img.is_featured = not img.is_featured
            img.save(update_fields=['is_featured'])
            return JsonResponse({'featured': img.is_featured})

        elif action == 'edit_image':
            img = get_object_or_404(Image, pk=request.POST.get('pk'))
            img.title = request.POST.get('title', img.title).strip() or img.title
            img.description = request.POST.get('description', img.description)
            img.resolution = request.POST.get('resolution', img.resolution)
            img.is_published = request.POST.get('is_published') == 'on'
            img.is_premium = request.POST.get('is_premium') == 'on'
            img.is_featured = request.POST.get('is_featured') == 'on'
            if 'thumbnail' in request.FILES:
                img.thumbnail = request.FILES['thumbnail']
            cat_pk = request.POST.get('category_pk', '')
            if cat_pk:
                try: img.category = ImageCategory.objects.get(pk=cat_pk)
                except: pass
            img.save()
            messages.success(request, f'Image "{img.title}" updated.')
            return redirect('/admin-panel/images/?tab=list')

        elif action == 'upload_image':
            title = request.POST.get('title', '').strip()
            if title and 'image_file' in request.FILES:
                base_slug = slugify(title)
                slug, n = base_slug, 1
                while Image.objects.filter(slug=slug).exists():
                    slug = f'{base_slug}-{n}'; n += 1

                cat = None
                cat_pk = request.POST.get('category_pk', '')
                if cat_pk:
                    try: cat = ImageCategory.objects.get(pk=cat_pk)
                    except: pass

                img = Image(
                    title=title, slug=slug,
                    description=request.POST.get('description', ''),
                    image_file=request.FILES['image_file'],
                    category=cat,
                    resolution=request.POST.get('resolution', 'hd'),
                    is_published=request.POST.get('is_published') == 'on',
                    is_premium=request.POST.get('is_premium') == 'on',
                    is_featured=request.POST.get('is_featured') == 'on',
                    uploaded_by=request.user,
                )
                if 'thumbnail' in request.FILES:
                    img.thumbnail = request.FILES['thumbnail']
                img.save()

                # Handle tags
                tags_raw = request.POST.get('tags', '')
                if tags_raw:
                    from images.models import Tag as ImageTag
                    for t_name in [x.strip() for x in tags_raw.split(',') if x.strip()]:
                        tag, _ = ImageTag.objects.get_or_create(name=t_name, defaults={'slug': slugify(t_name)})
                        img.tags.add(tag)

                # ── Mirror to Content ──────────────────────────────────────
                try:
                    from content.models import Content as CI
                    ci = CI.objects.create(
                        creator=request.user, title=img.title,
                        description=img.description, content_type='image',
                        status='approved' if img.is_published else 'pending',
                        tier='premium' if img.is_premium else 'free',
                    )
                    if img.thumbnail:
                        ci.thumbnail = img.thumbnail; ci.save(update_fields=['thumbnail'])
                    elif img.image_file:
                        ci.thumbnail = img.image_file; ci.save(update_fields=['thumbnail'])
                except Exception:
                    pass

                messages.success(request, f'Image "{title}" uploaded successfully.')
            else:
                messages.error(request, 'Title and image file are required.')
            return redirect('/admin-panel/images/?tab=list')

        elif action == 'create_image_cat':
            name = request.POST.get('name', '').strip()
            if name:
                ImageCategory.objects.get_or_create(name=name, defaults={'slug': slugify(name)})
                messages.success(request, f'Category "{name}" created.')
            return redirect('/admin-panel/images/?tab=cats')

        elif action == 'delete_image_cat':
            cat = get_object_or_404(ImageCategory, pk=request.POST.get('pk'))
            cat.delete()
            messages.success(request, 'Category deleted.')
            return redirect('/admin-panel/images/?tab=cats')

    qs = Image.objects.select_related('uploaded_by', 'category').order_by('-created_at')
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'admin_panel/modules/images.html', {
        'page': page,
        'q': q,
        'image_cats': ImageCategory.objects.all().order_by('name'),
    })


# =============================================================================
# MISSING CREATOR VIEWS – Fix for AttributeError
# =============================================================================

@_creator_required
def creator_write_blog(request):
    """Handle blog post creation – reuses unified creator_upload."""
    if request.method == 'POST':
        request.POST = request.POST.copy()
        request.POST['content_type'] = 'blog'
        return creator_upload(request)
    messages.info(request, 'Use the upload form on your dashboard.')
    return redirect('creator_dashboard')


@_creator_required
def creator_upload_music(request):
    """Handle music track upload."""
    if request.method == 'POST':
        request.POST = request.POST.copy()
        request.POST['content_type'] = 'music'
        return creator_upload(request)
    messages.info(request, 'Use the upload form on your dashboard.')
    return redirect('creator_dashboard')


@_creator_required
def creator_upload_video(request):
    """Handle video/movie upload."""
    if request.method == 'POST':
        request.POST = request.POST.copy()
        request.POST['content_type'] = 'video'
        return creator_upload(request)
    messages.info(request, 'Use the upload form on your dashboard.')
    return redirect('creator_dashboard')


@_creator_required
def creator_upload_image(request):
    """Handle image upload."""
    if request.method == 'POST':
        request.POST = request.POST.copy()
        request.POST['content_type'] = 'image'
        return creator_upload(request)
    messages.info(request, 'Use the upload form on your dashboard.')
    return redirect('creator_dashboard')


@_creator_required
def creator_manage_content(request):
    """List creator's content (redirect to dashboard where content is shown)."""
    return redirect('creator_dashboard')


@_creator_required
def creator_edit_content(request, pk):
    """Edit a specific content item – not implemented yet."""
    messages.warning(request, 'Editing not yet implemented. Use dashboard.')
    return redirect('creator_dashboard')


@_creator_required
def creator_delete_content(request, pk):
    """Delete a content item belonging to the creator."""
    from content.models import Content
    content = get_object_or_404(Content, pk=pk, creator=request.user)
    title = content.title
    content.delete()
    messages.success(request, f'"{title}" deleted.')
    return redirect('creator_dashboard')

    # =============================================================================
# MISSING CREATOR SERIES VIEWS – add these to avoid AttributeError
# =============================================================================

@_creator_required
def creator_series_list(request):
    """List series created by the user (placeholder)."""
    # You can implement a full list view, or redirect to dashboard
    return redirect('creator_dashboard')


@_creator_required
def creator_series_create(request):
    """Create a new series (placeholder)."""
    return redirect('creator_dashboard')


@_creator_required
def creator_series_edit(request, pk):
    """Edit a series (placeholder)."""
    return redirect('creator_dashboard')


@_creator_required
def creator_series_delete(request, pk):
    """Delete a series (placeholder)."""
    return redirect('creator_dashboard')


# Add any other missing creator series views if needed, e.g.:
# def creator_series_detail(request, pk):
#     return redirect('creator_dashboard')


# =============================================================================
# ADDITIONAL MISSING CREATOR VIEWS – Series, Episodes, etc.
# =============================================================================

@_creator_required
def creator_series_list(request):
    """List series created by the user."""
    return redirect('creator_dashboard')


@_creator_required
def creator_create_series(request):
    """Create a new series."""
    return redirect('creator_dashboard')


@_creator_required
def creator_series_edit(request, pk):
    """Edit a series."""
    return redirect('creator_dashboard')


@_creator_required
def creator_series_delete(request, pk):
    """Delete a series."""
    return redirect('creator_dashboard')


@_creator_required
def creator_series_detail(request, pk):
    """View a series detail."""
    return redirect('creator_dashboard')


# If there are episode-related views, add them too:
@_creator_required
def creator_episode_create(request, series_pk):
    """Create an episode for a series."""
    return redirect('creator_dashboard')


@_creator_required
def creator_episode_edit(request, series_pk, episode_pk):
    """Edit an episode."""
    return redirect('creator_dashboard')


@_creator_required
def creator_episode_delete(request, series_pk, episode_pk):
    """Delete an episode."""
    return redirect('creator_dashboard')

    # =============================================================================
# ALL MISSING CREATOR SERIES/EPISODE VIEWS
# =============================================================================

@_creator_required
def creator_series_episodes(request, series_pk):
    """List episodes of a series."""
    return redirect('creator_dashboard')


@_creator_required
def creator_episode_create(request, series_pk):
    """Create an episode for a series."""
    return redirect('creator_dashboard')


@_creator_required
def creator_episode_edit(request, series_pk, episode_pk):
    """Edit an episode."""
    return redirect('creator_dashboard')


@_creator_required
def creator_episode_delete(request, series_pk, episode_pk):
    """Delete an episode."""
    return redirect('creator_dashboard')


@_creator_required
def creator_episode_detail(request, series_pk, episode_pk):
    """View an episode detail."""
    return redirect('creator_dashboard')


# If your creator_urls.py also expects these:
@_creator_required
def creator_series_publish(request, series_pk):
    """Publish a series."""
    return redirect('creator_dashboard')


@_creator_required
def creator_series_unpublish(request, series_pk):
    """Unpublish a series."""
    return redirect('creator_dashboard')

# =============================================================================
# GENERIC CATCH‑ALL STUBS FOR MISSING CREATOR VIEWS
# (Add these to stop AttributeErrors – replace with real logic later)
# =============================================================================

@_creator_required
def creator_albums_list(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_albums_create(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_albums_edit(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_albums_delete(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_albums_detail(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_tracks_list(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_tracks_create(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_tracks_edit(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_tracks_delete(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_movies_list(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_movies_create(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_movies_edit(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_movies_delete(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_images_list(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_images_create(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_images_edit(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_images_delete(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_blog_list(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_blog_create(request):
    return redirect('creator_dashboard')

@_creator_required
def creator_blog_edit(request, pk):
    return redirect('creator_dashboard')

@_creator_required
def creator_blog_delete(request, pk):
    return redirect('creator_dashboard')

# If you have any other patterns (e.g., creator_playlist_*), add them similarly.

# =============================================================================
# MISSING CREATOR VIEWS – Final comprehensive set
# =============================================================================

@_creator_required
def creator_albums_list(request):
    """List albums for the creator."""
    return redirect('creator_dashboard')

@_creator_required
def creator_create_album(request):
    """Create a new album."""
    return redirect('creator_dashboard')

@_creator_required
def creator_create_series(request):
    """Create a new series."""
    return redirect('creator_dashboard')

@_creator_required
def creator_series_list(request):
    """List series for the creator."""
    return redirect('creator_dashboard')

@_creator_required
def creator_album_tracks(request, album_pk):
    """List tracks in an album."""
    return redirect('creator_dashboard')

# Ensure creator_series_episodes already exists; if not, add it:
@_creator_required
def creator_series_episodes(request, series_pk):
    """List episodes of a series."""
    return redirect('creator_dashboard')