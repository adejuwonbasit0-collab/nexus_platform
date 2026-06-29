"""Admin panel views — dashboard, content moderation, users, analytics."""
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from content.models import Content
from accounts.models import User
from .models import SiteSettings, Notification, AIProviderSettings


def _admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            return redirect('/auth/login/?next=' + request.path)
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ── Dashboard ──────────────────────────────────────────────────────────────────

@_admin_required
def admin_dashboard(request):
    now       = timezone.now()
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Core stats ─────────────────────────────────────────────────────────────
    stats = {
        'total_users':      User.objects.count(),
        'new_users_week':   User.objects.filter(date_joined__gte=week_ago).count(),
        'new_users_month':  User.objects.filter(date_joined__gte=month_ago).count(),
        'total_content':    Content.objects.count(),
        'pending_content':  Content.objects.filter(status='pending').count(),
        'approved_content': Content.objects.filter(status='approved').count(),
        'rejected_content': Content.objects.filter(status='rejected').count(),
        'total_views':      Content.objects.aggregate(t=Sum('views'))['t'] or 0,
    }

    # ── Revenue stats ──────────────────────────────────────────────────────────
    try:
        from monetization.models import Payment, Earning, WithdrawalRequest
        stats['revenue_total']       = Payment.objects.filter(status='completed').aggregate(t=Sum('amount'))['t'] or 0
        stats['revenue_month']       = Payment.objects.filter(status='completed', created_at__gte=month_ago).aggregate(t=Sum('amount'))['t'] or 0
        stats['revenue_week']        = Payment.objects.filter(status='completed', created_at__gte=week_ago).aggregate(t=Sum('amount'))['t'] or 0
        stats['pending_withdrawals'] = WithdrawalRequest.objects.filter(status='pending').count()
        stats['total_earnings']      = Earning.objects.aggregate(t=Sum('amount'))['t'] or 0
        stats['active_subs']         = 0
        try:
            from monetization.models import UserSubscription
            stats['active_subs'] = UserSubscription.objects.filter(is_active=True).count()
        except Exception:
            pass
    except Exception:
        stats.update({'revenue_total': 0, 'revenue_month': 0, 'revenue_week': 0,
                      'pending_withdrawals': 0, 'total_earnings': 0, 'active_subs': 0})

    # ── 7-day signups chart (sparkline data) ───────────────────────────────────
    signup_chart = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        signup_chart.append({
            'label': day_start.strftime('%a'),
            'value': User.objects.filter(date_joined__gte=day_start, date_joined__lt=day_end).count(),
        })

    # ── 7-day content uploads chart ────────────────────────────────────────────
    upload_chart = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        upload_chart.append({
            'label': day_start.strftime('%a'),
            'value': Content.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
        })

    # ── Module counts ──────────────────────────────────────────────────────────
    module_stats = {}
    try:
        from music.models import Track
        module_stats['tracks'] = Track.objects.count()
        module_stats['tracks_week'] = Track.objects.filter(created_at__gte=week_ago).count()
    except Exception:
        module_stats['tracks'] = Content.objects.filter(content_type='music').count()
        module_stats['tracks_week'] = 0
    try:
        from movies.models import Movie
        module_stats['movies'] = Movie.objects.count()
        module_stats['movies_week'] = Movie.objects.filter(created_at__gte=week_ago).count()
    except Exception:
        module_stats['movies'] = Content.objects.filter(content_type='video').count()
        module_stats['movies_week'] = 0
    try:
        from blog.models import Post
        module_stats['posts'] = Post.objects.count()
        module_stats['posts_week'] = Post.objects.filter(created_at__gte=week_ago).count()
    except Exception:
        module_stats['posts'] = Content.objects.filter(content_type='blog').count()
        module_stats['posts_week'] = 0
    try:
        from images.models import Image
        module_stats['images'] = Image.objects.count()
        module_stats['images_week'] = Image.objects.filter(created_at__gte=week_ago).count()
    except Exception:
        module_stats['images'] = Content.objects.filter(content_type='image').count()
        module_stats['images_week'] = 0

    # ── Pending moderation ─────────────────────────────────────────────────────
    pending_content = Content.objects.filter(status='pending').select_related('creator').order_by('-created_at')[:10]

    # ── Recent users ───────────────────────────────────────────────────────────
    recent_users = User.objects.order_by('-date_joined')[:8]

    # ── Top content this week ──────────────────────────────────────────────────
    top_content = Content.objects.filter(
        status='approved', created_at__gte=week_ago
    ).order_by('-views').select_related('creator')[:5]

    # ── System health ──────────────────────────────────────────────────────────
    try:
        from observability.health import SystemHealthChecker
        health = SystemHealthChecker().get_metrics()
    except Exception:
        health = {'overall': 'unknown'}

    # ── Open security alerts ───────────────────────────────────────────────────
    try:
        from observability.models import SecurityAlert
        open_alerts = SecurityAlert.objects.filter(is_resolved=False).count()
        recent_alerts = list(SecurityAlert.objects.filter(is_resolved=False).order_by('-created_at')[:3])
    except Exception:
        open_alerts = 0
        recent_alerts = []

    # ── Unread notifications ───────────────────────────────────────────────────
    unread_notifs = Notification.objects.filter(user=request.user, is_read=False).count()

    # ── Creator leaderboard (top earners) ─────────────────────────────────────
    top_creators = []
    try:
        from monetization.models import Earning
        top_creators = list(
            Earning.objects.values('creator__username', 'creator__pk')
            .annotate(total=Sum('amount'))
            .order_by('-total')[:5]
        )
    except Exception:
        pass

    return render(request, 'admin_panel/dashboard.html', {
        'stats':          stats,
        'module_stats':   module_stats,
        'pending_content': pending_content,
        'recent_users':   recent_users,
        'top_content':    top_content,
        'top_creators':   top_creators,
        'signup_chart':   signup_chart,
        'upload_chart':   upload_chart,
        'unread_notifs':  unread_notifs,
        'health':         health,
        'open_alerts':    open_alerts,
        'recent_alerts':  recent_alerts,
    })


# ── Analytics ──────────────────────────────────────────────────────────────────

@_admin_required
def admin_analytics(request):
    """Placeholder — served via settings_views in production."""
    from core import settings_views
    return settings_views.admin_analytics(request)


# ── Content moderation ─────────────────────────────────────────────────────────

@_admin_required
def admin_content(request):
    qs = Content.objects.select_related('creator').order_by('-created_at')
    status = request.GET.get('status', '')
    q      = request.GET.get('q', '')
    ct     = request.GET.get('type', '')
    if status: qs = qs.filter(status=status)
    if q:      qs = qs.filter(Q(title__icontains=q) | Q(creator__username__icontains=q))
    if ct:     qs = qs.filter(content_type=ct)
    paginator = Paginator(qs, 30)
    page      = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/content.html', {
        'page': page, 'filter_status': status,
        'filter_q': q, 'filter_type': ct,
        'content_types': Content.TYPE_CHOICES,
        'pending_count': Content.objects.filter(status='pending').count(),
    })


@_admin_required
@require_POST
def admin_approve_content(request, pk):
    c = get_object_or_404(Content, pk=pk)
    c.status = 'approved'
    c.save()
    messages.success(request, f'"{c.title}" approved.')
    return redirect(request.META.get('HTTP_REFERER', 'admin_content'))


@_admin_required
@require_POST
def admin_reject_content(request, pk):
    c = get_object_or_404(Content, pk=pk)
    c.status = 'rejected'
    c.rejection_reason = request.POST.get('reason', 'Does not meet guidelines.')
    c.save()
    messages.warning(request, f'"{c.title}" rejected.')
    return redirect(request.META.get('HTTP_REFERER', 'admin_content'))


@_admin_required
@require_POST
def admin_delete_content(request, pk):
    c = get_object_or_404(Content, pk=pk)
    title = c.title
    c.delete()
    messages.success(request, f'"{title}" deleted.')
    return redirect(request.META.get('HTTP_REFERER', 'admin_content'))


# ── Upload (file + URL) ────────────────────────────────────────────────────────

@_admin_required
def admin_upload_content(request):
    if request.method == 'POST':
        upload_mode  = request.POST.get('upload_mode', 'file')   # 'file' or 'url'
        content_type = request.POST.get('content_type', '')
        title        = request.POST.get('title', '').strip()
        description  = request.POST.get('description', '').strip()
        tier         = request.POST.get('tier', 'free')
        source_url   = request.POST.get('source_url', '').strip()
        thumb_url    = request.POST.get('thumb_url', '').strip()
        file_obj     = request.FILES.get('file')
        thumb_obj    = request.FILES.get('thumbnail')

        if not title:
            messages.error(request, 'Title is required.')
        elif upload_mode == 'url' and not source_url:
            messages.error(request, 'URL is required when uploading by link.')
        elif upload_mode == 'file' and not file_obj and content_type != 'blog':
            messages.error(request, 'Please select a file to upload.')
        else:
            try:
                price = float(request.POST.get('price', '0') or '0')
            except ValueError:
                price = 0.0

            c = Content(
                creator=request.user,
                title=title,
                description=description,
                content_type=content_type,
                tier=tier,
                status='approved',
                price=price,
            )
            if upload_mode == 'url':
                c.source_url = source_url
                # Also store thumb url if provided
                if thumb_url:
                    c.thumbnail_url = thumb_url
            else:
                if file_obj:
                    c.file = file_obj
                if thumb_obj:
                    c.thumbnail = thumb_obj

            if content_type == 'blog':
                c.body = request.POST.get('body', '')

            # Tags
            tags_raw = request.POST.get('tags', '').strip()
            c.save()
            if tags_raw:
                try:
                    from content.models import Tag
                    for t in [x.strip() for x in tags_raw.split(',') if x.strip()]:
                        tag, _ = Tag.objects.get_or_create(name=t)
                        c.tags.add(tag)
                except Exception:
                    pass

            messages.success(request, f'"{c.title}" uploaded and published.')
            return redirect('admin_content')

    return render(request, 'admin_panel/upload.html', {
        'content_types': Content.TYPE_CHOICES,
        'tiers':         Content.TIER_CHOICES,
    })


# ── Module-specific management ─────────────────────────────────────────────────

@_admin_required
def admin_movies(request):
    try:
        from movies.models import Movie
        qs = Movie.objects.order_by('-created_at')
        q  = request.GET.get('q', '')
        if q: qs = qs.filter(Q(title__icontains=q))
        page = Paginator(qs, 20).get_page(request.GET.get('page', 1))
        return render(request, 'admin_panel/modules/movies.html', {'page': page, 'filter_q': q})
    except Exception as e:
        messages.error(request, str(e))
        return redirect('admin_dashboard')


@_admin_required
def admin_music(request):
    try:
        from music.models import Track, Artist
        qs = Track.objects.select_related('artist').order_by('-created_at')
        q  = request.GET.get('q', '')
        if q: qs = qs.filter(Q(title__icontains=q) | Q(artist__name__icontains=q))
        page    = Paginator(qs, 30).get_page(request.GET.get('page', 1))
        artists = Artist.objects.order_by('name')
        return render(request, 'admin_panel/modules/music.html', {
            'page': page, 'artists': artists, 'filter_q': q
        })
    except Exception as e:
        messages.error(request, str(e))
        return redirect('admin_dashboard')


@_admin_required
def admin_blog(request):
    try:
        from blog.models import Post, Category as BlogCategory
        qs   = Post.objects.select_related('author', 'category').order_by('-created_at')
        q    = request.GET.get('q', '')
        if q: qs = qs.filter(Q(title__icontains=q) | Q(author__username__icontains=q))
        page = Paginator(qs, 20).get_page(request.GET.get('page', 1))
        cats = BlogCategory.objects.all()
        return render(request, 'admin_panel/modules/blog.html', {
            'page': page, 'cats': cats, 'filter_q': q
        })
    except Exception as e:
        messages.error(request, str(e))
        return redirect('admin_dashboard')


@_admin_required
def admin_images_mgmt(request):
    try:
        from images.models import Image
        qs   = Image.objects.select_related('creator').order_by('-created_at')
        q    = request.GET.get('q', '')
        if q: qs = qs.filter(Q(title__icontains=q))
        page = Paginator(qs, 30).get_page(request.GET.get('page', 1))
        return render(request, 'admin_panel/modules/images.html', {'page': page, 'filter_q': q})
    except Exception as e:
        messages.error(request, str(e))
        return redirect('admin_dashboard')


# ── Series management ──────────────────────────────────────────────────────────

@_admin_required
def admin_series(request):
    try:
        from movies.models import Series
        page = Paginator(Series.objects.order_by('-created_at'), 20).get_page(request.GET.get('page', 1))
        return render(request, 'admin_panel/series.html', {'page': page})
    except Exception as e:
        messages.error(request, str(e))
        return redirect('admin_dashboard')


@_admin_required
def admin_create_series(request):
    try:
        from movies.models import Series
        if request.method == 'POST':
            s = Series(
                title=request.POST.get('title', ''),
                description=request.POST.get('description', ''),
                genre=request.POST.get('genre', ''),
                release_year=int(request.POST.get('release_year') or timezone.now().year),
                is_published=request.POST.get('is_published') == 'on',
            )
            if 'thumbnail' in request.FILES:
                s.thumbnail = request.FILES['thumbnail']
            s.save()
            messages.success(request, f'Series "{s.title}" created.')
            return redirect('admin_series')
        return render(request, 'admin_panel/create_series.html')
    except Exception as e:
        messages.error(request, str(e))
        return redirect('admin_series')


@_admin_required
def admin_add_episode(request, series_pk):
    try:
        from movies.models import Series, Season, Episode
        series = get_object_or_404(Series, pk=series_pk)
        if request.method == 'POST':
            season_num  = int(request.POST.get('season_number', 1))
            season, _   = Season.objects.get_or_create(series=series, number=season_num)
            ep = Episode(
                season=season,
                number=int(request.POST.get('episode_number', 1)),
                title=request.POST.get('title', ''),
                description=request.POST.get('description', ''),
                is_free=request.POST.get('is_free') == 'on',
            )
            if 'video_file' in request.FILES:
                ep.video_file = request.FILES['video_file']
            if 'thumbnail' in request.FILES:
                ep.thumbnail = request.FILES['thumbnail']
            ep.save()
            messages.success(request, f'Episode "{ep.title}" added.')
            return redirect('admin_series')
        return render(request, 'admin_panel/add_episode.html', {'series': series})
    except Exception as e:
        messages.error(request, str(e))
        return redirect('admin_series')


# ── Categories ─────────────────────────────────────────────────────────────────

@_admin_required
def admin_categories(request):
    from content.models import Category
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            if name:
                from django.utils.text import slugify
                Category.objects.get_or_create(name=name, defaults={'slug': slugify(name)})
                messages.success(request, f'Category "{name}" created.')
        elif action == 'delete':
            pk = request.POST.get('pk')
            if pk:
                Category.objects.filter(pk=pk).delete()
                messages.success(request, 'Category deleted.')
        return redirect('admin_categories')
    cats = Category.objects.annotate(content_count=Count('content')).order_by('name')
    return render(request, 'admin_panel/categories.html', {'categories': cats})


# ── Users ──────────────────────────────────────────────────────────────────────

@_admin_required
def admin_users(request):
    qs    = User.objects.order_by('-date_joined')
    q     = request.GET.get('q', '')
    role  = request.GET.get('role', '')
    if q:    qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if role: qs = qs.filter(role=role)
    page  = Paginator(qs, 30).get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/users.html', {
        'page': page, 'roles': User.ROLE_CHOICES,
        'filter_q': q, 'filter_role': role,
    })


@_admin_required
def admin_user_detail(request, pk):
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'role':
            u.role = request.POST.get('role', u.role)
            u.save()
            messages.success(request, f'Role updated to {u.role}.')
        elif action == 'ban':
            u.is_active = False
            u.save()
            messages.warning(request, f'{u.username} banned.')
        elif action == 'unban':
            u.is_active = True
            u.save()
            messages.success(request, f'{u.username} unbanned.')
        return redirect('admin_user_detail', pk=pk)

    content  = Content.objects.filter(creator=u).order_by('-created_at')[:10]
    earnings = None
    try:
        from monetization.models import Earning
        earnings = Earning.objects.filter(creator=u).aggregate(total=Sum('amount'))['total'] or 0
    except Exception:
        pass
    return render(request, 'admin_panel/user_detail.html', {
        'u': u, 'content': content, 'earnings': earnings,
        'role_choices': User.ROLE_CHOICES,
    })


# ── Monetization ───────────────────────────────────────────────────────────────

@_admin_required
def admin_monetization(request):
    ctx = {}
    try:
        from monetization.models import Payment, WithdrawalRequest, SubscriptionPlan, UserSubscription
        ctx['payments']     = Payment.objects.order_by('-created_at')[:20]
        ctx['withdrawals']  = WithdrawalRequest.objects.filter(status='pending').order_by('-created_at')[:20]
        ctx['plans']        = SubscriptionPlan.objects.all()
        ctx['active_subs']  = UserSubscription.objects.filter(is_active=True).count()
        ctx['total_rev']    = Payment.objects.filter(status='completed').aggregate(t=Sum('amount'))['t'] or 0
        if request.method == 'POST':
            action = request.POST.get('action')
            if action in ('approve_withdrawal', 'reject_withdrawal'):
                wr = get_object_or_404(WithdrawalRequest, pk=request.POST.get('pk'))
                wr.status = 'completed' if action == 'approve_withdrawal' else 'rejected'
                wr.save()
                messages.success(request, f'Withdrawal {wr.status}.')
                return redirect('admin_monetization')
    except Exception as e:
        messages.error(request, f'Monetization error: {e}')
    return render(request, 'admin_panel/monetization.html', ctx)


# ── Notifications ──────────────────────────────────────────────────────────────

@_admin_required
def notifications_list(request):
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, 'notifications/list.html', {'notifications': notifs})


def notifications_count(request):
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})
