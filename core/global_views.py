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
    """Home — Pulse-style sidebar UI with music charts, movies, genres."""
    try:
        from cms.models import HomepageSection
        cms_sections = list(HomepageSection.objects.filter(is_visible=True).order_by('order'))
    except Exception:
        cms_sections = []

    # ── Music ──────────────────────────────────────────────────────────────────
    song_of_day   = None
    recent_tracks = []
    chart_tracks  = []
    top_artists   = []
    new_albums    = []
    genres        = []
    try:
        from music.models import Track, Artist, Album
        song_of_day   = Track.objects.filter(is_published=True).select_related('artist','album').order_by('-plays_count').first()
        recent_tracks = list(Track.objects.filter(is_published=True).select_related('artist','album').order_by('-created_at')[:16])
        chart_tracks  = list(Track.objects.filter(is_published=True).select_related('artist','album').order_by('-plays_count')[:10])
        top_artists   = list(Artist.objects.order_by('-monthly_listeners')[:12]) or list(Artist.objects.order_by('name')[:12])
        new_albums    = list(Album.objects.filter(is_published=True).select_related('artist').order_by('-created_at')[:10])
        try:
            from music.models import Genre as MusicGenre
            genres = list(MusicGenre.objects.order_by('name')[:6])
        except Exception:
            pass
    except Exception:
        pass

    # ── Movies ─────────────────────────────────────────────────────────────────
    trending_movies = []
    series_list = []
    try:
        from movies.models import Movie, Series
        trending_movies = list(Movie.objects.filter(is_published=True).order_by('-created_at')[:10])
        series_list     = list(Series.objects.filter(is_published=True).order_by('-created_at')[:8])
    except Exception:
        pass

    # ── Images ─────────────────────────────────────────────────────────────────
    images_list = []
    try:
        from images.models import Image
        images_list = list(Image.objects.filter(is_published=True).order_by('-created_at')[:8])
    except Exception:
        pass

    # ── Blog ───────────────────────────────────────────────────────────────────
    blog_list = []
    try:
        from blog.models import Post
        blog_list = list(Post.objects.filter(status='published', is_ai_generated=False)
                         .select_related('author').order_by('-created_at')[:6])
    except Exception:
        pass

    # ── Content (featured / recent) ────────────────────────────────────────────
    cache_key = 'homepage_content_v5'
    content_data = cache.get(cache_key)
    if content_data is None:
        base_qs = Content.objects.filter(status='approved', is_ai_generated=False).select_related('creator')
        content_data = {
            'featured': list(base_qs.filter(featured=True).order_by('-created_at')[:12]),
            'recent':   list(base_qs.order_by('-created_at')[:16]),
            'trending': list(base_qs.order_by('-views')[:12]),
        }
        cache.set(cache_key, content_data, 300)

    # ── Categories ─────────────────────────────────────────────────────────────
    categories = []
    try:
        from content.models import Category
        categories = list(Category.objects.order_by('name')[:10])
    except Exception:
        pass

    # ── Platform stats ─────────────────────────────────────────────────────────
    platform_stats = cache.get('platform_stats_v5')
    if platform_stats is None:
        platform_stats = {'tracks': 0, 'artists': 0, 'movies': 0, 'users': User.objects.count()}
        try:
            from music.models import Track as _T, Artist as _A
            platform_stats['tracks']  = _T.objects.filter(is_published=True).count()
            platform_stats['artists'] = _A.objects.count()
        except Exception:
            pass
        try:
            from movies.models import Movie as _M
            platform_stats['movies'] = _M.objects.filter(is_published=True).count()
        except Exception:
            pass
        cache.set('platform_stats_v5', platform_stats, 600)

    return render(request, 'home.html', {
        'cms_sections':    cms_sections,
        'song_of_day':     song_of_day,
        'recent_tracks':   recent_tracks,
        'chart_tracks':    chart_tracks,
        'top_artists':     top_artists,
        'new_albums':      new_albums,
        'genres':          genres,
        'trending_movies': trending_movies,
        'series_list':     series_list,
        'images_list':     images_list,
        'blog_list':       blog_list,
        'featured':        content_data['featured'],
        'recent':          content_data['recent'],
        'trending':        content_data['trending'],
        'categories':      categories,
        'stats':           platform_stats,
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
            from images.models import Image
            img_qs = Image.objects.filter(is_published=True).filter(
                Q(title__icontains=q) | Q(description__icontains=q))[:10]
            if img_qs.exists():
                results['Images'] = img_qs
                total += img_qs.count()
        except Exception:
            pass

        try:
            from movies.models import Series
            s_qs = Series.objects.filter(is_published=True).filter(
                Q(title__icontains=q) | Q(description__icontains=q))[:6]
            if s_qs.exists():
                results['Series'] = s_qs
                total += s_qs.count()
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


def trending_view(request):
    """Trending content across all modules — platform + external charts."""
    cache_key = 'trending_page_v2'
    cached = cache.get(cache_key)
    if cached:
        return render(request, 'trending.html', cached)

    trending_movies = []
    trending_music = []
    trending_content = []
    external_music = []   # charts from external sources

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

    # ── External trending charts (iTunes Top Charts — free, no key needed) ──
    try:
        import urllib.request, json as _j
        url = 'https://itunes.apple.com/us/rss/topsongs/limit=20/json'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = _j.loads(resp.read())
        entries = data.get('feed', {}).get('entry', [])
        for e in entries:
            external_music.append({
                'title':   e.get('im:name', {}).get('label', ''),
                'artist':  e.get('im:artist', {}).get('label', ''),
                'cover':   e.get('im:image', [{}])[-1].get('label', ''),
                'link':    e.get('link', {}).get('attributes', {}).get('href', '#'),
            })
    except Exception:
        pass

    ctx = {
        'trending_movies':  trending_movies,
        'trending_music':   trending_music,
        'trending_content': trending_content,
        'external_music':   external_music,
    }
    cache.set(cache_key, ctx, 300)   # cache 5 minutes
    return render(request, 'trending.html', ctx)


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

    # Wallet — only relevant for creators/admins who can actually earn money
    wallet = None
    if user.is_creator():
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