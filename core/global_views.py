"""Public-facing platform views — homepage, search, content detail, trending, user dashboard, subscriptions."""
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, F
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from content.models import Content
from accounts.models import User


def platform_home(request):
    # CMS homepage sections (admin-controlled)
    try:
        from cms.models import HomepageSection
        cms_sections = list(HomepageSection.objects.filter(is_visible=True).order_by('order'))
    except Exception:
        cms_sections = []

    # Fetch content per module - cached 5 min
    cache_key = 'homepage_content_v2'
    content_data = cache.get(cache_key)
    if content_data is None:
        base_qs = Content.objects.filter(status='approved').select_related('creator')
        content_data = {
            'featured':  list(base_qs.filter(featured=True).order_by('-created_at')[:12]),
            'recent':    list(base_qs.order_by('-created_at')[:16]),
            'trending':  list(base_qs.order_by('-views')[:12]),
        }
        cache.set(cache_key, content_data, 300)

    # Movies
    movie_list = []
    try:
        from movies.models import Movie
        movie_list = list(Movie.objects.filter(is_published=True)
                          .select_related('uploaded_by').order_by('-created_at')[:8])
    except Exception:
        pass

    # Music
    music_list = []
    try:
        from music.models import Track
        music_list = list(Track.objects.filter(is_published=True)
                          .select_related('artist').order_by('-plays_count')[:8])
    except Exception:
        pass

    # Blog
    blog_list = []
    try:
        from blog.models import Post
        blog_list = list(Post.objects.filter(status='published')
                         .select_related('author').order_by('-created_at')[:6])
    except Exception:
        pass

    # Platform stats - cached 10 min
    stats = cache.get('platform_stats_v2')
    if stats is None:
        stats = {
            'total_content':  Content.objects.filter(status='approved').count(),
            'total_creators': User.objects.filter(role='creator').count(),
            'total_members':  User.objects.count(),
        }
        cache.set('platform_stats_v2', stats, 600)

    return render(request, 'platform_home.html', {
        'cms_sections':  cms_sections,
        'featured':      content_data['featured'],
        'recent':        content_data['recent'],
        'trending':      content_data['trending'],
        'movie_list':    movie_list,
        'music_list':    music_list,
        'blog_list':     blog_list,
        'stats':         stats,
    })


def global_search(request):
    q = request.GET.get('q', '').strip()
    results = {}
    total = 0

    if q and len(q) >= 2:
        content_qs = Content.objects.filter(
            status='approved'
        ).filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        ).select_related('creator')[:20]
        if content_qs.exists():
            results['Content'] = content_qs
            total += content_qs.count()

        try:
            from music.models import Track
            t_qs = Track.objects.filter(is_published=True).filter(
                Q(title__icontains=q) | Q(artist__name__icontains=q))[:10]
            if t_qs.exists():
                results['Music'] = t_qs
                total += t_qs.count()
        except Exception:
            pass

        try:
            from movies.models import Movie
            m_qs = Movie.objects.filter(is_published=True).filter(
                Q(title__icontains=q) | Q(description__icontains=q))[:10]
            if m_qs.exists():
                results['Movies'] = m_qs
                total += m_qs.count()
        except Exception:
            pass

        try:
            from blog.models import Post
            b_qs = Post.objects.filter(status='published').filter(
                Q(title__icontains=q) | Q(excerpt__icontains=q))[:10]
            if b_qs.exists():
                results['Blog'] = b_qs
                total += b_qs.count()
        except Exception:
            pass

        try:
            from music.models import Artist
            a_qs = Artist.objects.filter(Q(name__icontains=q))[:6]
            if a_qs.exists():
                results['Artists'] = a_qs
                total += a_qs.count()
        except Exception:
            pass

        try:
            cr_qs = User.objects.filter(role='creator', is_active=True).filter(
                Q(username__icontains=q) | Q(first_name__icontains=q))[:6]
            if cr_qs.exists():
                results['Creators'] = cr_qs
                total += cr_qs.count()
        except Exception:
            pass

    return render(request, 'search/results.html', {
        'q': q, 'results': results, 'total': total
    })


def content_detail(request, pk):
    """View for displaying individual content detail."""
    content = get_object_or_404(Content, id=pk, is_published=True)
    content.views = (content.views or 0) + 1
    content.save(update_fields=['views'])
    return render(request, 'content/detail.html', {
        'content': content,
    })


def trending_view(request):
    """Trending content across all modules."""
    trending_movies = []
    trending_music = []
    trending_content = []

    try:
        from movies.models import Movie
        trending_movies = list(Movie.objects.filter(is_published=True)
                               .order_by('-views_count')[:10])
    except Exception:
        pass

    try:
        from music.models import Track
        trending_music = list(Track.objects.filter(is_published=True)
                              .select_related('artist').order_by('-plays_count')[:10])
    except Exception:
        pass

    trending_content = list(Content.objects.filter(status='approved')
                            .order_by('-views').select_related('creator')[:20])

    return render(request, 'trending.html', {
        'trending_movies': trending_movies,
        'trending_music':  trending_music,
        'trending_content': trending_content,
    })


@login_required
def user_dashboard(request):
    """Logged-in user's personal dashboard."""
    user = request.user

    # Recent content
    my_content = Content.objects.filter(creator=user).order_by('-created_at')[:10]

    # Subscription
    sub = None
    try:
        from monetization.models import UserSubscription
        sub = UserSubscription.objects.filter(user=user, is_active=True).first()
    except Exception:
        pass

    # Wallet
    wallet = None
    try:
        from monetization.models import Wallet
        wallet, _ = Wallet.objects.get_or_create(user=user)
    except Exception:
        pass

    # Liked music
    liked_tracks = []
    try:
        from music.models import TrackLike
        liked_tracks = list(
            TrackLike.objects.filter(user=user).select_related('track', 'track__artist')[:8]
        )
    except Exception:
        pass

    return render(request, 'user_dashboard.html', {
        'my_content':    my_content,
        'sub':           sub,
        'wallet':        wallet,
        'liked_tracks':  liked_tracks,
    })


def subscriptions_view(request):
    """Public subscriptions/pricing page."""
    plans = []
    try:
        from monetization.models import SubscriptionPlan
        plans = list(SubscriptionPlan.objects.filter(is_active=True).order_by('price'))
    except Exception:
        pass

    return render(request, 'subscriptions.html', {'plans': plans, 'faq': []})