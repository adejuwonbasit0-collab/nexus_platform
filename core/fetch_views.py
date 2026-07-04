"""
Admin "Fetch" tools — search/browse external music (iTunes) and movie (TMDB)
catalogues and import results straight into the site's own Track / Movie
library, tagged with the importing admin's name and ready to approve
individually or in bulk.
"""
import json as _json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.text import slugify

from .views import _admin_required
from . import external_fetch as ext


# ── Music ────────────────────────────────────────────────────────────────────

@_admin_required
def fetch_music(request):
    tab = request.GET.get('tab', 'search')
    q = request.GET.get('q', '').strip()
    genre_id = request.GET.get('genre', '')

    results = []
    if tab == 'search':
        if q:
            results = ext.itunes_search(q, limit=30)
    elif tab == 'trending':
        results = ext.itunes_chart(genre_id, feed='topsongs', limit=40)
    elif tab == 'latest':
        results = ext.itunes_chart(genre_id, feed='newmusic', limit=40)
    elif tab == 'genre':
        if genre_id:
            results = ext.itunes_chart(genre_id, feed='topsongs', limit=40)

    from music.models import Track
    imported_keys = set(
        f"{t.title.lower()}|{t.artist.name.lower()}"
        for t in Track.objects.filter(is_fetched=True).select_related('artist')
    )
    for r in results:
        r['already_imported'] = f"{r['title'].lower()}|{r['artist'].lower()}" in imported_keys

    pending_count = Track.objects.filter(is_fetched=True, is_published=False).count()

    return render(request, 'admin_panel/modules/fetch_music.html', {
        'tab': tab, 'q': q, 'genre_id': genre_id,
        'results': results, 'genres': ext.ITUNES_GENRES,
        'pending_count': pending_count,
    })


@_admin_required
@require_POST
def fetch_music_import(request):
    from music.models import Track, Artist, Genre

    approve = request.POST.get('approve') == '1'
    try:
        items = _json.loads(request.POST.get('items', '[]'))
    except Exception:
        items = []

    created = 0
    for it in items:
        title = (it.get('title') or '').strip()
        artist_name = (it.get('artist') or '').strip() or 'Unknown Artist'
        if not title:
            continue
        if Track.objects.filter(is_fetched=True, title__iexact=title, artist__name__iexact=artist_name).exists():
            continue

        artist, _c = Artist.objects.get_or_create(
            name__iexact=artist_name,
            defaults={'name': artist_name, 'slug': slugify(artist_name) or 'artist'},
        )
        genre = None
        gname = (it.get('genre') or '').strip()
        if gname:
            genre, _c = Genre.objects.get_or_create(
                name__iexact=gname, defaults={'name': gname, 'slug': slugify(gname) or 'genre'}
            )

        year_raw = str(it.get('release_year') or '').strip()
        year = int(year_raw) if year_raw.isdigit() else 2024

        track = Track(
            title=title, artist=artist, genre=genre,
            audio_url=(it.get('preview_url') or '').strip(),
            release_year=year,
            uploaded_by=request.user,
            is_fetched=True, fetch_source=it.get('source') or 'iTunes',
            is_published=approve,
        )
        track.save()

        cover = it.get('cover') or ''
        if cover:
            ext.download_image_into(track, 'cover_image', cover, filename_hint=f'{title}.jpg')
            track.save(update_fields=['cover_image'])
        created += 1

    if created:
        state = 'imported and approved' if approve else 'imported as pending — approve them from the Tracks tab'
        messages.success(request, f'{created} track(s) {state}.')
    else:
        messages.info(request, 'Nothing new to import — those tracks are already in your library.')
    return redirect('/admin-panel/music/?tab=tracks')


# ── Movies ───────────────────────────────────────────────────────────────────

@_admin_required
def fetch_movies(request):
    tab = request.GET.get('tab', 'search')
    q = request.GET.get('q', '').strip()
    genre_id = request.GET.get('genre', '')

    configured = ext.tmdb_configured()
    results = []
    if configured:
        if tab == 'search':
            if q:
                results = ext.tmdb_search(q)
        elif tab == 'trending':
            results = ext.tmdb_trending()
        elif tab == 'latest':
            results = ext.tmdb_now_playing()
        elif tab == 'genre':
            if genre_id:
                results = ext.tmdb_by_genre(genre_id)

    if request.method == 'POST' and request.POST.get('action') == 'save_tmdb_key':
        from core.models import SiteSettings
        key = request.POST.get('tmdb_api_key', '').strip()
        obj, _c = SiteSettings.objects.get_or_create(key='tmdb_api_key', defaults={'label': 'TMDB API Key', 'group': 'integrations'})
        obj.value = key
        obj.save()
        messages.success(request, 'TMDB API key saved.')
        return redirect('/admin-panel/fetch/movies/')

    from movies.models import Movie
    imported_ids = set(
        Movie.objects.filter(is_fetched=True).values_list('title', flat=True)
    )
    for r in results:
        r['already_imported'] = r['title'] in imported_ids

    genres = ext.tmdb_genre_list() if configured else []
    pending_count = Movie.objects.filter(is_fetched=True, is_published=False).count()

    return render(request, 'admin_panel/modules/fetch_movies.html', {
        'tab': tab, 'q': q, 'genre_id': genre_id,
        'results': results, 'genres': genres,
        'tmdb_configured': configured, 'pending_count': pending_count,
    })


@_admin_required
@require_POST
def fetch_movies_import(request):
    from movies.models import Movie, Genre as MovieGenre

    approve = request.POST.get('approve') == '1'
    try:
        items = _json.loads(request.POST.get('items', '[]'))
    except Exception:
        items = []

    created = 0
    for it in items:
        title = (it.get('title') or '').strip()
        if not title:
            continue
        if Movie.objects.filter(is_fetched=True, title__iexact=title).exists():
            continue

        year_raw = str(it.get('release_year') or '').strip()
        year = int(year_raw) if year_raw.isdigit() else 2024

        movie = Movie(
            title=title,
            description=it.get('description', ''),
            release_year=year,
            uploaded_by=request.user,
            is_fetched=True, fetch_source=it.get('source') or 'TMDB',
            is_published=approve,
        )
        tmdb_id = it.get('external_id', '')
        if tmdb_id:
            movie.trailer_url = ext.tmdb_trailer_url(tmdb_id) or ''
        movie.save()

        cover = it.get('cover') or ''
        if cover:
            ext.download_image_into(movie, 'thumbnail', cover, filename_hint=f'{title}.jpg')
            movie.save(update_fields=['thumbnail'])
        created += 1

    if created:
        state = 'imported and approved' if approve else 'imported as pending — approve them from the Movies tab'
        messages.success(request, f'{created} movie(s) {state}. Posters, ratings, and trailers were fetched — add the actual video file/link on each one before publishing.')
    else:
        messages.info(request, 'Nothing new to import — those movies are already in your library.')
    return redirect('/admin-panel/movies/')


# ── Bulk approve / reject / delete for fetched (pending) items ──────────────

@_admin_required
@require_POST
def fetch_bulk_action(request):
    """Shared bulk endpoint for both Tracks and Movies tables. Expects
    kind=track|movie, action=approve|reject|delete, pks=comma list."""
    kind = request.POST.get('kind', '')
    action = request.POST.get('action', '')
    pks = [p for p in request.POST.get('pks', '').split(',') if p.strip()]
    if not pks or kind not in ('track', 'movie') or action not in ('approve', 'reject', 'delete'):
        return JsonResponse({'ok': False, 'error': 'Invalid request'}, status=400)

    if kind == 'track':
        from music.models import Track
        qs = Track.objects.filter(pk__in=pks)
    else:
        from movies.models import Movie
        qs = Movie.objects.filter(pk__in=pks)

    count = qs.count()
    if action == 'approve':
        qs.update(is_published=True)
    elif action == 'reject':
        qs.update(is_published=False)
    elif action == 'delete':
        qs.delete()

    return JsonResponse({'ok': True, 'count': count, 'action': action})
