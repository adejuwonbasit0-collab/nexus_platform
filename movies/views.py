import os
import mimetypes
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, StreamingHttpResponse, FileResponse, Http404
from django.db.models import Q

from .models import Movie, Series, Season, Episode, MovieComment, MovieLike


def _premium_check(request, obj):
    if getattr(obj, 'is_premium', False):
        if not request.user.is_authenticated:
            return redirect(f'/auth/login/?next={request.path}')
        from monetization.models import UserSubscription
        try:
            if not UserSubscription.objects.filter(user=request.user, status='active').exists():
                return render(request, 'movies/premium_locked.html', {'obj': obj})
        except Exception:
            pass
    return None


def movie_home(request):
    all_movies = Movie.objects.filter(is_published=True)
    featured   = list(all_movies.filter(is_featured=True).order_by('-created_at')[:1])
    trending   = list(all_movies.order_by('-views_count')[:12])
    recent     = list(all_movies.order_by('-created_at')[:16])
    series     = list(Series.objects.filter(is_published=True).prefetch_related('seasons').order_by('-created_at'))
    try:
        from movies.models import Genre
        genres = list(Genre.objects.all())
    except Exception:
        genres = []
    return render(request, 'movies/home.html', {
        'featured': featured, 'trending': trending,
        'recent': recent, 'series': series, 'genres': genres,
    })


def movie_browse(request):
    qs = Movie.objects.filter(is_published=True).order_by('-created_at')
    q = request.GET.get('q', '')
    genre = request.GET.get('genre', '')
    quality = request.GET.get('quality', '')
    if q:      qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if genre:   qs = qs.filter(genres__slug=genre)
    if quality: qs = qs.filter(quality=quality)
    from django.core.paginator import Paginator
    page = Paginator(qs, 24).get_page(request.GET.get('page', 1))
    # Also show published series
    series_qs = Series.objects.filter(is_published=True).order_by('-created_at')
    return render(request, 'movies/browse.html', {
        'page': page, 'series_list': series_qs[:12],
        'q': q, 'genre': genre, 'quality': quality,
        'genres': __import__('movies.models', fromlist=['Genre']).Genre.objects.all() if hasattr(__import__('movies.models', fromlist=['Genre']), 'Genre') else [],
    })


def movie_detail(request, slug):
    movie   = get_object_or_404(Movie, slug=slug, is_published=True)
    block   = _premium_check(request, movie)
    if block: return block
    # Increment view count
    Movie.objects.filter(pk=movie.pk).update(views_count=movie.views_count + 1)
    movie.refresh_from_db()
    related  = Movie.objects.filter(is_published=True).exclude(pk=movie.pk).order_by('-created_at')[:6]
    comments = movie.comments.select_related('user').filter(episode__isnull=True).order_by('-created_at')[:30]
    user_liked = False
    if request.user.is_authenticated:
        user_liked = MovieLike.objects.filter(user=request.user, movie=movie).exists()
    progress = None
    if request.user.is_authenticated:
        try:
            from .models import WatchProgress
            progress = WatchProgress.objects.filter(user=request.user, movie=movie).first()
        except Exception:
            pass
    return render(request, 'movies/detail.html', {
        'movie': movie, 'related': related, 'progress': progress,
        'comments': comments, 'user_liked': user_liked,
    })


def series_detail(request, slug):
    series  = get_object_or_404(Series, slug=slug, is_published=True)
    block   = _premium_check(request, series)
    if block: return block
    seasons = series.seasons.prefetch_related('episodes').order_by('number')
    related = Series.objects.filter(is_published=True).exclude(pk=series.pk).order_by('-created_at')[:6]
    return render(request, 'movies/series_detail.html', {
        'series': series, 'seasons': seasons, 'related': related,
    })


def episode_watch(request, pk):
    ep = get_object_or_404(Episode, pk=pk, is_published=True)
    block = _premium_check(request, ep.season.series)
    if block: return block
    # Increment view count
    Episode.objects.filter(pk=ep.pk).update(views_count=ep.views_count + 1)
    ep.refresh_from_db()
    # All episodes in same series for sidebar
    all_eps = Episode.objects.filter(
        season__series=ep.season.series, is_published=True
    ).select_related('season').order_by('season__number', 'number')
    return render(request, 'movies/episode_watch.html', {
        'episode': ep, 'series': ep.season.series,
        'all_episodes': all_eps,
    })


def stream_video(request, model, pk):
    if model == 'movie':
        obj = get_object_or_404(Movie, pk=pk, is_published=True)
        if not obj.video_file: raise Http404
        file_path = obj.video_file.path
    else:
        obj = get_object_or_404(Episode, pk=pk)
        if not obj.video_file: raise Http404
        file_path = obj.video_file.path
    if not os.path.exists(file_path): raise Http404
    file_size = os.path.getsize(file_path)
    ct, _ = mimetypes.guess_type(file_path)
    ct = ct or 'video/mp4'
    rh = request.META.get('HTTP_RANGE', '').strip()
    if rh:
        parts = rh.replace('bytes=', '').split('-')
        fb = int(parts[0]) if parts[0] else 0
        lb = int(parts[1]) if parts[1] else file_size - 1
        cs = (lb - fb) + 1
        def gen():
            with open(file_path, 'rb') as f:
                f.seek(fb); rem = cs
                while rem > 0:
                    chunk = f.read(min(8192, rem))
                    if not chunk: break
                    yield chunk; rem -= len(chunk)
        r = StreamingHttpResponse(gen(), status=206, content_type=ct)
        r['Content-Range']  = f'bytes {fb}-{lb}/{file_size}'
        r['Content-Length'] = cs
        r['Accept-Ranges']  = 'bytes'
        return r
    return FileResponse(open(file_path, 'rb'), content_type=ct)


def stream_movie(request, pk):
    return stream_video(request, 'movie', pk)


@login_required
def download_movie(request, pk):
    movie = get_object_or_404(Movie, pk=pk, is_published=True)
    block = _premium_check(request, movie)
    if block: return block
    if not movie.video_file or not os.path.exists(movie.video_file.path):
        raise Http404
    Movie.objects.filter(pk=pk).update(downloads_count=movie.downloads_count + 1)
    return FileResponse(
        open(movie.video_file.path, 'rb'),
        as_attachment=True,
        filename=f'{movie.title}.mp4'
    )


@login_required
def download_episode(request, pk):
    ep = get_object_or_404(Episode, pk=pk)
    block = _premium_check(request, ep.season.series)
    if block: return block
    if not ep.video_file or not os.path.exists(ep.video_file.path):
        raise Http404
    return FileResponse(
        open(ep.video_file.path, 'rb'),
        as_attachment=True,
        filename=f'S{ep.season.number}E{ep.number}_{ep.title}.mp4'
    )


@require_POST
@login_required
def save_progress(request, pk):
    movie = get_object_or_404(Movie, pk=pk)
    try:
        from .models import WatchProgress
        progress = int(request.POST.get('progress', 0))
        WatchProgress.objects.update_or_create(
            user=request.user, movie=movie,
            defaults={'progress': progress}
        )
    except Exception:
        pass
    return JsonResponse({'ok': True})


@require_POST
def toggle_movie_like(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error":"login_required","count":0,"liked":False},status=401)
    movie = get_object_or_404(Movie, pk=pk)
    like, created = MovieLike.objects.get_or_create(user=request.user, movie=movie)
    if not created:
        like.delete()
        Movie.objects.filter(pk=pk).update(likes_count=max(0, movie.likes_count - 1))
        liked = False
    else:
        Movie.objects.filter(pk=pk).update(likes_count=movie.likes_count + 1)
        liked = True
    movie.refresh_from_db()
    return JsonResponse({'liked': liked, 'count': movie.likes_count})


@require_POST
def add_episode_comment(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok":False,"error":"login_required"},status=401)
    ep   = get_object_or_404(Episode, pk=pk)
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'Empty comment'})
    comment = MovieComment.objects.create(user=request.user, episode=ep, text=text)
    return JsonResponse({
        'ok': True, 'username': request.user.username,
        'text': comment.text, 'id': comment.pk,
    })


@require_POST
def add_movie_comment(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok":False,"error":"login_required"},status=401)
    movie = get_object_or_404(Movie, pk=pk)
    text  = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'Empty comment'})
    comment = MovieComment.objects.create(user=request.user, movie=movie, text=text)
    return JsonResponse({
        'ok': True,
        'username': request.user.username,
        'text': comment.text,
        'id': comment.pk,
    })