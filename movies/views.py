import os, mimetypes
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import StreamingHttpResponse, FileResponse, JsonResponse
from django.views.decorators.http import require_POST
from .models import Movie, Series, Season, Episode, Genre, Country, WatchProgress, MovieComment


def _premium_check(request, obj):
    if not obj.is_premium: return None
    if request.user.is_authenticated and (request.user.is_admin() or request.user.is_premium):
        return None
    return redirect('/subscriptions/')


def movie_home(request):
    featured  = Movie.objects.filter(is_published=True, is_featured=True).select_related('country')[:6]
    trending  = Movie.objects.filter(is_published=True).order_by('-views_count')[:12]
    recent    = Movie.objects.filter(is_published=True).order_by('-created_at')[:12]
    series    = Series.objects.filter(is_published=True).order_by('-created_at')[:8]
    genres    = Genre.objects.all()
    return render(request, 'movies/home.html', {
        'featured': featured, 'trending': trending,
        'recent': recent, 'series': series, 'genres': genres,
    })


def movie_browse(request):
    qs = Movie.objects.filter(is_published=True).select_related('country')
    q       = request.GET.get('q','')
    genre   = request.GET.get('genre','')
    year    = request.GET.get('year','')
    country = request.GET.get('country','')
    sort    = request.GET.get('sort','-created_at')
    if q:       qs = qs.filter(Q(title__icontains=q)|Q(description__icontains=q))
    if genre:   qs = qs.filter(genres__slug=genre)
    if year:    qs = qs.filter(release_year=year)
    if country: qs = qs.filter(country__code=country)
    if sort in ('-views_count','-created_at','-downloads_count'): qs = qs.order_by(sort)
    genres    = Genre.objects.all()
    countries = Country.objects.all()
    years     = range(2024, 1979, -1)
    return render(request, 'movies/browse.html', {
        'movies': qs, 'genres': genres, 'countries': countries,
        'years': years, 'q': q, 'active_genre': genre,
    })


def movie_detail(request, slug):
    movie = get_object_or_404(Movie, slug=slug, is_published=True)
    block = _premium_check(request, movie)
    if block: return block
    # track view
    sk = f'mv_{movie.pk}'
    if not request.session.get(sk):
        movie.views_count += 1; movie.save(update_fields=['views_count'])
        request.session[sk] = True
    related = Movie.objects.filter(genres__in=movie.genres.all(), is_published=True).exclude(pk=movie.pk).distinct()[:6]
    progress = None
    if request.user.is_authenticated:
        progress = WatchProgress.objects.filter(user=request.user, movie=movie).first()
    comments = movie.comments.select_related('user').order_by('-created_at')[:20]
    return render(request, 'movies/detail.html', {
        'movie': movie, 'related': related, 'progress': progress, 'comments': comments,
    })


def series_detail(request, slug):
    series  = get_object_or_404(Series, slug=slug, is_published=True)
    block   = _premium_check(request, series)
    if block: return block
    seasons = series.seasons.prefetch_related('episodes').order_by('number')
    return render(request, 'movies/series_detail.html', {'series': series, 'seasons': seasons})


def episode_watch(request, pk):
    ep    = get_object_or_404(Episode, pk=pk, is_published=True)
    block = _premium_check(request, ep.season.series)
    if block: return block
    ep.views_count += 1; ep.save(update_fields=['views_count'])
    other_eps = ep.season.episodes.filter(is_published=True)
    return render(request, 'movies/watch.html', {'episode': ep, 'other_eps': other_eps})


def stream_video(request, model, pk):
    if model == 'movie':
        obj = get_object_or_404(Movie, pk=pk, is_published=True)
        if not obj.video_file: return JsonResponse({'error':'No file'},status=404)
        file_path = obj.video_file.path
    else:
        ep = get_object_or_404(Episode, pk=pk)
        file_path = ep.video_file.path

    file_size = os.path.getsize(file_path)
    ct, _     = mimetypes.guess_type(file_path)
    ct        = ct or 'video/mp4'
    rh        = request.META.get('HTTP_RANGE','').strip()
    if rh:
        parts = rh.replace('bytes=','').split('-')
        fb    = int(parts[0]) if parts[0] else 0
        lb    = int(parts[1]) if parts[1] else file_size-1
        cs    = (lb-fb)+1
        def gen():
            with open(file_path,'rb') as f:
                f.seek(fb); rem=cs
                while rem>0:
                    chunk=f.read(min(8192,rem))
                    if not chunk: break
                    yield chunk; rem-=len(chunk)
        r = StreamingHttpResponse(gen(), status=206, content_type=ct)
        r['Content-Range']  = f'bytes {fb}-{lb}/{file_size}'
        r['Content-Length'] = cs
        r['Accept-Ranges']  = 'bytes'
        return r
    return FileResponse(open(file_path,'rb'), content_type=ct)


@login_required
def download_movie(request, pk):
    movie = get_object_or_404(Movie, pk=pk, is_published=True)
    block = _premium_check(request, movie)
    if block: return block
    if not movie.video_file:
        from django.contrib import messages
        messages.error(request,'No file available'); return redirect('movie_detail', slug=movie.slug)
    movie.downloads_count += 1; movie.save(update_fields=['downloads_count'])
    from accounts.models import DownloadHistory
    DownloadHistory.objects.create(user=request.user, content_type='movie', object_id=movie.pk,
                                   file_url=movie.video_file.url, ip_address=request.META.get('REMOTE_ADDR'))
    return FileResponse(open(movie.video_file.path,'rb'), as_attachment=True,
                        filename=os.path.basename(movie.video_file.name))


@require_POST
@login_required
def save_progress(request, pk):
    movie    = get_object_or_404(Movie, pk=pk)
    progress = int(request.POST.get('progress',0))
    WatchProgress.objects.update_or_create(user=request.user, movie=movie, defaults={'progress':progress})
    return JsonResponse({'ok': True})


@require_POST
@login_required
def add_movie_comment(request, pk):
    movie = get_object_or_404(Movie, pk=pk)
    text  = request.POST.get('text','').strip()
    if text:
        c = MovieComment.objects.create(user=request.user, movie=movie, text=text)
        return JsonResponse({'ok':True,'username':request.user.username,'text':c.text,'id':c.pk})
    return JsonResponse({'ok':False})
