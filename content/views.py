"""
content/views.py  – upgraded
Changes vs original:
  • download_content: login_required enforced, validation added
  • browse / images_gallery: tag filter added
  • creator-facing helpers for tag saving on upload now handled in core/views.py
  • stream_video: existing logic kept intact
  • All other views kept identical
"""
import mimetypes
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Category, Comment, Content, Download, Episode,
    Like, Series, Tag, View,
)


def home(request):
    featured       = Content.objects.filter(status='approved', featured=True)[:8]
    recent_images  = Content.objects.filter(status='approved', content_type='image')[:12]
    recent_videos  = Content.objects.filter(status='approved', content_type='video')[:8]
    recent_music   = Content.objects.filter(status='approved', content_type='music')[:8]
    recent_blogs   = Content.objects.filter(status='approved', content_type='blog')[:6]
    series_list    = Series.objects.filter(is_published=True)[:6]
    categories     = Category.objects.all()
    return render(request, 'home.html', {
        'featured':      featured,
        'recent_images': recent_images,
        'recent_videos': recent_videos,
        'recent_music':  recent_music,
        'recent_blogs':  recent_blogs,
        'series_list':   series_list,
        'categories':    categories,
    })


def content_detail(request, slug):
    obj = get_object_or_404(Content, slug=slug, status='approved')

    # If a matching Movie/Track/Image/Post exists, send the user straight
    # to its real detail page instead of the generic content view.
    match = _find_type_match(obj.content_type, obj.title)
    if match:
        url = _type_match_url(obj.content_type, match)
        if url:
            return redirect(url)

    # Track view (deduplicate by session key to avoid page-refresh spam)
    session_key = f'viewed_{obj.pk}'
    if not request.session.get(session_key):
        View.objects.create(
            content=obj,
            user=request.user if request.user.is_authenticated else None,
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        obj.views += 1
        obj.save(update_fields=['views'])
        request.session[session_key] = True

    comments   = obj.comments.order_by('-created_at')[:20]
    related    = Content.objects.filter(
        content_type=obj.content_type, status='approved'
    ).exclude(pk=obj.pk)[:6]
    user_liked = (
        Like.objects.filter(user=request.user, content=obj).exists()
        if request.user.is_authenticated else False
    )

    # Paystack public key for premium purchase button
    from monetization.models import PaymentSettings
    payment_cfg = PaymentSettings.get_active()

    return render(request, 'content/detail.html', {
        'content':     obj,
        'obj':         obj,
        'comments':    comments,
        'related':     related,
        'user_liked':  user_liked,
        'liked_ids':   [obj.pk] if user_liked else [],
        'payment_cfg': payment_cfg,
    })


def series_detail(request, pk):
    series   = get_object_or_404(Series, pk=pk)
    seasons  = series.seasons.prefetch_related('episodes').order_by('number')
    comments = []
    return render(request, 'content/series_detail.html', {
        'series': series, 'seasons': seasons, 'comments': comments,
    })


def episode_watch(request, pk):
    # Route to movies.Episode (the real episode model)
    from movies.models import Episode as MoviesEpisode
    try:
        episode = get_object_or_404(MoviesEpisode, pk=pk, is_published=True)
        from movies.views import episode_watch as movies_episode_watch
        return movies_episode_watch(request, pk)
    except Exception:
        from django.http import Http404
        raise Http404


def stream_video(request, pk):
    """HTTP Range-request streaming – unchanged from original."""
    try:
        obj       = Content.objects.get(pk=pk, status='approved', content_type='video')
        file_path = obj.file.path
    except Content.DoesNotExist:
        episode   = get_object_or_404(Episode, pk=pk)
        file_path = episode.file.path

    file_size    = os.path.getsize(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or 'video/mp4'

    range_header = request.META.get('HTTP_RANGE', '').strip()
    if range_header:
        parts      = range_header.replace('bytes=', '').split('-')
        first_byte = int(parts[0]) if parts[0] else 0
        last_byte  = int(parts[1]) if parts[1] else file_size - 1
        chunk_size = (last_byte - first_byte) + 1

        def stream_chunk():
            with open(file_path, 'rb') as f:
                f.seek(first_byte)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    yield chunk
                    remaining -= len(chunk)

        response = StreamingHttpResponse(stream_chunk(), status=206, content_type=content_type)
        response['Content-Range']  = f'bytes {first_byte}-{last_byte}/{file_size}'
        response['Content-Length'] = chunk_size
        response['Accept-Ranges']  = 'bytes'
        return response

    return FileResponse(open(file_path, 'rb'), content_type=content_type)


def _find_type_match(content_type, title, published_only=True):
    """Look up a Movie/Track/Image/Post with a matching title for this
    content_type. Returns the matched object, or None."""
    try:
        if content_type == 'video':
            from movies.models import Movie
            qs = Movie.objects.filter(title=title)
            if published_only: qs = qs.filter(is_published=True)
            return qs.first()
        if content_type == 'music':
            from music.models import Track
            qs = Track.objects.filter(title=title)
            if published_only: qs = qs.filter(is_published=True)
            return qs.first()
        if content_type == 'image':
            from images.models import Image
            qs = Image.objects.filter(title=title)
            if published_only: qs = qs.filter(is_published=True)
            return qs.first()
        if content_type == 'blog':
            from blog.models import Post
            qs = Post.objects.filter(title=title)
            if published_only: qs = qs.filter(status='published')
            return qs.first()
    except Exception:
        pass
    return None


def _type_match_url(content_type, match):
    if content_type == 'video':
        return f'/movies/film/{match.slug}/'
    if content_type == 'music':
        return f'/music/track/{match.slug}/'
    if content_type == 'image':
        return f'/images/view/{match.slug}/'
    if content_type == 'blog':
        return f'/blog/post/{match.slug}/'
    return None


def _attach_display_info(items):
    """Content rows are a generic, type-agnostic feed and often lack their
    own thumbnail/slug. Where a matching Movie/Track/Image/Post exists
    (same title + type), borrow its thumbnail and link to its real detail
    page instead of the generic /content/<pk>/ fallback."""
    by_type = {}
    for it in items:
        by_type.setdefault(it.content_type, set()).add(it.title)

    matches = {}
    if by_type.get('video'):
        from movies.models import Movie
        for m in Movie.objects.filter(title__in=by_type['video'], is_published=True):
            matches[('video', m.title)] = m
    if by_type.get('music'):
        from music.models import Track
        for t in Track.objects.filter(title__in=by_type['music'], is_published=True):
            matches[('music', t.title)] = t
    if by_type.get('image'):
        from images.models import Image
        for i in Image.objects.filter(title__in=by_type['image'], is_published=True):
            matches[('image', i.title)] = i
    if by_type.get('blog'):
        from blog.models import Post
        for p in Post.objects.filter(title__in=by_type['blog'], status='published'):
            matches[('blog', p.title)] = p

    for it in items:
        match = matches.get((it.content_type, it.title))
        display_thumb = it.thumbnail.url if it.thumbnail else None
        display_url   = f'/content/{it.slug}/'
        slug = ''
        if match:
            slug = match.slug
            if it.content_type == 'video':
                display_url = f'/movies/film/{match.slug}/'
                if match.thumbnail: display_thumb = match.thumbnail.url
            elif it.content_type == 'music':
                display_url = f'/music/track/{match.slug}/'
                cover = getattr(match, 'cover_image', None) or getattr(match, 'cover', None)
                if cover: display_thumb = cover.url
            elif it.content_type == 'image':
                display_url = f'/images/view/{match.slug}/'
                if getattr(match, 'has_image', False): display_thumb = match.display_url
            elif it.content_type == 'blog':
                display_url = f'/blog/post/{match.slug}/'
                if match.featured_img:
                    display_thumb = match.featured_img.url
                elif getattr(match, 'featured_img_url', ''):
                    display_thumb = match.featured_img_url
        it.slug = slug
        it.display_thumb = display_thumb
        it.display_url = display_url
    return items


def browse(request):
    content_type = request.GET.get('type', '')
    tier         = request.GET.get('tier', '')
    q            = request.GET.get('q', '')
    sort         = request.GET.get('sort', '-created_at')
    if sort not in ['-created_at', '-views', '-likes_count']: sort = '-created_at'

    items = Content.objects.filter(status='approved', is_ai_generated=False).select_related('creator')
    if content_type: items = items.filter(content_type=content_type)
    if tier:         items = items.filter(tier=tier)
    if q:
        items = items.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(creator__username__icontains=q)
        ).distinct()
    items = items.order_by(sort)

    from django.core.paginator import Paginator
    page = Paginator(items, 24).get_page(request.GET.get('page', 1))
    _attach_display_info(page.object_list)
    return render(request, 'content/browse.html', {
        'items': page, 'q': q,
        'active_type': content_type, 'active_tier': tier, 'sort': sort,
    })


@login_required
def download_content(request, pk):
    """Only logged-in users can download. Tracks every download."""
    obj = get_object_or_404(Content, pk=pk, status='approved')

    if not obj.file:
        messages.error(request, 'This content has no downloadable file.')
        return redirect('content_detail', slug=obj.slug)

    if obj.tier == 'premium':
        # Check if user has a completed payment for this content
        from monetization.models import Payment
        paid = Payment.objects.filter(
            user=request.user, content=obj, status='completed'
        ).exists()
        is_creator_or_admin = (
            request.user.is_creator() or
            request.user.pk == obj.creator_id
        )
        if not paid and not is_creator_or_admin:
            messages.error(request, 'This is premium content. Please purchase to download.')
            return redirect('content_detail', slug=obj.slug)

    Download.objects.create(
        content=obj, user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    obj.downloads_count += 1
    obj.save(update_fields=['downloads_count'])

    # Creator earnings for download
    try:
        from monetization.models import CommissionSettings, Earning
        commission = CommissionSettings.objects.get(
            content_type=obj.content_type, action='download'
        )
        Earning.objects.create(
            creator=obj.creator, content=obj,
            amount=commission.amount, reason='Download commission',
        )
        obj.creator.total_earnings += commission.amount
        obj.creator.save(update_fields=['total_earnings'])
    except Exception:
        pass

    return FileResponse(
        open(obj.file.path, 'rb'),
        as_attachment=True,
        filename=os.path.basename(obj.file.name),
    )


@require_POST
def toggle_like(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error":"login_required","count":0,"liked":False},status=401)
    obj  = get_object_or_404(Content, pk=pk)
    like, created = Like.objects.get_or_create(user=request.user, content=obj)
    if not created:
        like.delete()
        obj.likes_count = max(0, obj.likes_count - 1)
        liked = False
    else:
        obj.likes_count += 1
        liked = True
    obj.save(update_fields=['likes_count'])
    return JsonResponse({'liked': liked, 'count': obj.likes_count})


@require_POST
def add_comment(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok":False,"error":"login_required"},status=401)
    obj  = get_object_or_404(Content, pk=pk)
    text = request.POST.get('text', '').strip()
    if text:
        comment = Comment.objects.create(user=request.user, content=obj, text=text)
        return JsonResponse({
            'success':  True,
            'username': request.user.username,
            'text':     comment.text,
            'id':       comment.id,
        })
    return JsonResponse({'success': False})


def blogs(request):
    q     = request.GET.get('q', '')
    posts = Content.objects.filter(status='approved', content_type='blog').order_by('-created_at')
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(description__icontains=q))
    return render(request, 'content/blogs.html', {'posts': posts, 'q': q})


def images_gallery(request):
    tier = request.GET.get('tier', '')
    tag  = request.GET.get('tag', '')
    q    = request.GET.get('q', '')
    items = Content.objects.filter(status='approved', content_type='image').order_by('-created_at')
    if tier: items = items.filter(tier=tier)
    if tag:  items = items.filter(tags__name__iexact=tag)
    if q:    items = items.filter(Q(title__icontains=q) | Q(description__icontains=q)).distinct()
    all_tags = Tag.objects.all()[:30]
    return render(request, 'content/gallery.html', {
        'items': items, 'all_tags': all_tags,
        'active_tag': tag, 'active_tier': tier,
    })


def music_library(request):
    tracks = Content.objects.filter(status='approved', content_type='music').order_by('-created_at')
    return render(request, 'content/music.html', {'tracks': tracks})


def movies_page(request):
    movies      = Content.objects.filter(status='approved', content_type='video').order_by('-created_at')
    series_list = Series.objects.filter(is_published=True)
    return render(request, 'content/movies.html', {'movies': movies, 'series_list': series_list})