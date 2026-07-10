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
from django.core.cache import cache

from .views import _admin_required
from . import external_fetch as ext


# ── Music ────────────────────────────────────────────────────────────────────

@_admin_required
def fetch_music(request):
    tab = request.GET.get('tab', 'search')
    q = request.GET.get('q', '').strip()
    genre_id = request.GET.get('genre', '')

    if request.method == 'POST' and request.POST.get('action') == 'save_audd_key':
        from core.models import SiteSettings
        key = request.POST.get('audd_api_token', '').strip()
        obj, _c = SiteSettings.objects.get_or_create(key='audd_api_token', defaults={'label': 'AudD API Token', 'group': 'integrations'})
        obj.value = key
        obj.save()
        messages.success(request, 'AudD API token saved — Discover will use it for song identification.')
        return redirect(request.path + f'?tab={tab}')

    from core.models import SiteSettings
    audd_configured = SiteSettings.objects.filter(key='audd_api_token').exclude(value='').exists()

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
        'pending_count': pending_count, 'audd_configured': audd_configured,
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
    no_audio = 0
    no_cover = 0
    no_lyrics_count = 0
    for it in items:
        title = (it.get('title') or '').strip()
        artist_name = (it.get('artist') or '').strip() or 'Unknown Artist'
        if not title:
            continue
        if Track.objects.filter(is_fetched=True, title__iexact=title, artist__name__iexact=artist_name).exists():
            continue

        # Chart-based browsing (Trending/Latest/Genre) doesn't carry a
        # preview URL — fill it in now, per selected item, so a handful of
        # failed lookups can never affect the whole batch.
        it = ext.enrich_for_import(it)

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
        cover_ok = False
        if cover:
            cover_ok = ext.download_image_into(track, 'cover_image', cover, filename_hint=f'{title}.jpg')
            if cover_ok:
                track.save(update_fields=['cover_image'])

        lyrics = ext.lrclib_get_lyrics(title, artist_name)
        no_lyrics = not lyrics
        if lyrics:
            track.lyrics_lrc = lyrics
            track.save(update_fields=['lyrics_lrc'])

        created += 1
        if not track.audio_url:
            no_audio += 1
        if not cover_ok:
            no_cover += 1
        if no_lyrics:
            no_lyrics_count += 1

    if created:
        state = 'imported and approved' if approve else 'imported as pending — approve them from the Tracks tab'
        msg = f'{created} track(s) {state}.'
        if no_audio:
            msg += f' ⚠ {no_audio} had no preview available on iTunes — edit them to add a real audio file/link.'
        if no_cover:
            msg += f' ⚠ {no_cover} had no cover art fetched — you can upload one via Edit.'
        if no_lyrics_count:
            msg += f' 📝 {no_lyrics_count} had no synced lyrics found — this is common for less-popular tracks.'
        messages.success(request, msg)
    else:
        messages.info(request, 'Nothing new to import — those tracks are already in your library.')
    cache.delete('trending_page_v2')
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
    cache.delete('trending_page_v2')
    return redirect('/admin-panel/movies/')


# ── Bulk approve / reject / delete for fetched (pending) items ──────────────

@_admin_required
def fetch_images(request):
    """Search stock photos (Pexels or Pixabay) or generate an AI image, then
    apply the result as the site-wide default player banner, or as the
    banner/thumbnail for a specific track or movie (pass ?target=track&pk=5
    or ?target=movie&pk=5 to open it pre-scoped to that item)."""
    tab = request.GET.get('tab', 'stock')
    q = request.GET.get('q', '').strip()
    target = request.GET.get('target', 'site')  # site | track | movie
    pk = request.GET.get('pk', '')

    from core.models import SiteSettings
    if 'provider' in request.GET:
        provider = request.GET.get('provider')
        # Remember this choice so the next visit opens on the same
        # provider instead of always defaulting back to Pexels.
        pref, _c = SiteSettings.objects.get_or_create(
            key='preferred_stock_provider', defaults={'label': 'Preferred Stock Photo Provider', 'group': 'integrations'})
        if pref.value != provider:
            pref.value = provider
            pref.save()
    else:
        pref = SiteSettings.objects.filter(key='preferred_stock_provider').first()
        provider = pref.value if pref and pref.value else 'pexels'

    if request.method == 'POST' and request.POST.get('action') == 'save_pexels_key':
        from core.models import SiteSettings
        key = request.POST.get('pexels_api_key', '').strip()
        obj, _c = SiteSettings.objects.get_or_create(key='pexels_api_key', defaults={'label': 'Pexels API Key', 'group': 'integrations'})
        obj.value = key
        obj.save()
        messages.success(request, 'Pexels API key saved.')
        return redirect(request.path + f'?tab=stock&provider=pexels&target={target}&pk={pk}')

    if request.method == 'POST' and request.POST.get('action') == 'save_pixabay_key':
        from core.models import SiteSettings
        key = request.POST.get('pixabay_api_key', '').strip()
        obj, _c = SiteSettings.objects.get_or_create(key='pixabay_api_key', defaults={'label': 'Pixabay API Key', 'group': 'integrations'})
        obj.value = key
        obj.save()
        messages.success(request, 'Pixabay API key saved.')
        return redirect(request.path + f'?tab=stock&provider=pixabay&target={target}&pk={pk}')

    pexels_configured = ext.pexels_configured()
    pixabay_configured = ext.pixabay_configured()
    configured = pexels_configured if provider == 'pexels' else pixabay_configured
    results = []
    search_error = None
    is_random = request.GET.get('random') == '1'
    if tab == 'stock' and configured and is_random:
        if provider == 'pixabay':
            results, search_error = ext.pixabay_random_verbose(per_page=18)
        else:
            results, search_error = ext.pexels_curated_verbose(per_page=18)
    elif tab == 'stock' and configured and q:
        if provider == 'pixabay':
            results, search_error = ext.pixabay_search_verbose(q, per_page=18)
        else:
            results, search_error = ext.pexels_search_verbose(q, per_page=18)

    target_label = 'Site-wide default banner'
    target_obj = None
    if target == 'track' and pk:
        from music.models import Track
        target_obj = Track.objects.filter(pk=pk).first()
        if target_obj:
            target_label = f'Banner for "{target_obj.title}"'
    elif target == 'movie' and pk:
        from movies.models import Movie
        target_obj = Movie.objects.filter(pk=pk).first()
        if target_obj:
            target_label = f'Thumbnail for "{target_obj.title}"'

    return render(request, 'admin_panel/modules/fetch_images.html', {
        'tab': tab, 'q': q, 'results': results,
        'pexels_configured': pexels_configured, 'pixabay_configured': pixabay_configured,
        'provider': provider, 'is_random': is_random,
        'target': target, 'pk': pk, 'target_label': target_label,
        'search_error': search_error,
    })


@_admin_required
@require_POST
def fetch_images_apply(request):
    """Download the chosen stock/AI image URL and attach it to whichever
    target was selected (site default banner, a track's banner, or a
    movie's thumbnail)."""
    image_url = request.POST.get('image_url', '').strip()
    target = request.POST.get('target', 'site')
    pk = request.POST.get('pk', '')

    if not image_url:
        messages.error(request, 'No image selected.')
        return redirect('/admin-panel/fetch/images/')

    if target == 'track' and pk:
        from music.models import Track
        obj = get_object_or_404(Track, pk=pk)
        ok = ext.download_image_into(obj, 'banner_image', image_url, filename_hint=f'{obj.title}-banner.jpg')
        field_label = 'banner'
    elif target == 'movie' and pk:
        from movies.models import Movie
        obj = get_object_or_404(Movie, pk=pk)
        ok = ext.download_image_into(obj, 'thumbnail', image_url, filename_hint=f'{obj.title}-thumb.jpg')
        field_label = 'thumbnail'
    else:
        from cms.models import BrandingConfig
        obj = BrandingConfig.get()
        ok = ext.download_image_into(obj, 'default_player_banner', image_url, filename_hint='default-banner.jpg')
        field_label = 'site default banner'

    if ok:
        obj.save()
        messages.success(request, f'Image applied as the {field_label}.')
    else:
        messages.error(request, 'Could not download that image — try a different one.')

    if target == 'track' and pk:
        return redirect('/admin-panel/music/?tab=tracks')
    elif target == 'movie' and pk:
        return redirect('/admin-panel/movies/')
    return redirect('/admin-panel/fetch/images/')


@_admin_required
@require_POST
def fetch_images_import_gallery(request):
    """Bulk-import selected stock photo search results directly into the
    Gallery (images.Image), mirroring how Fetch Music/Movies import — with
    individual or bulk approve afterward from the Images admin table."""
    approve = request.POST.get('approve') == '1'
    try:
        items = _json.loads(request.POST.get('items', '[]'))
    except Exception:
        items = []

    from images.models import Image

    created = 0
    skipped_dupes = 0
    for it in items:
        image_url = it.get('full') or it.get('thumb') or ''
        if not image_url:
            continue
        source = it.get('source') or ''
        external_id = it.get('external_id') or ''
        # Dedupe by the stock provider's own photo ID, not by title — stock
        # photos don't have real titles, so using a generic fallback title
        # for all of them caused every image after the first to look like
        # a duplicate and get silently skipped.
        if external_id and Image.objects.filter(is_fetched=True, fetch_source=source, description__contains=f'[id:{external_id}]').exists():
            skipped_dupes += 1
            continue
        query = (it.get('query') or 'Photo').strip().title()[:80]
        photographer = it.get('photographer') or 'Unknown'
        title = f"{query} — by {photographer}"[:200]
        img = Image(
            title=title,
            description=f"Photo by {photographer} via {source or 'stock photos'}. [id:{external_id}]",
            uploaded_by=request.user,
            is_fetched=True, fetch_source=source,
            is_published=approve,
        )
        img.save()
        ok = ext.download_image_into(img, 'image_file', image_url, filename_hint=f'{title}.jpg')
        if ok:
            img.save(update_fields=['image_file'])
        created += 1

    if created:
        state = 'imported and approved' if approve else 'imported as pending — approve them from Admin → Images'
        msg = f'{created} image(s) {state}.'
        if skipped_dupes:
            msg += f' ({skipped_dupes} already in your Gallery, skipped.)'
        messages.success(request, msg)
    else:
        messages.info(request, 'Nothing new to import.')
    return redirect(request.META.get('HTTP_REFERER', '/admin-panel/fetch/images/'))


@_admin_required
def fetch_shorts(request):
    """Search real stock video clips (Pexels/Pixabay) and import them as
    Shorts — always saved as a video_url, never downloaded, to keep
    storage minimal."""
    tab = request.GET.get('tab', 'search')
    q = request.GET.get('q', '').strip()
    provider = request.GET.get('provider', 'pixabay')
    is_random = request.GET.get('random') == '1'

    if request.method == 'POST' and request.POST.get('action') == 'save_pexels_key':
        from core.models import SiteSettings
        key = request.POST.get('pexels_api_key', '').strip()
        obj, _c = SiteSettings.objects.get_or_create(key='pexels_api_key', defaults={'label': 'Pexels API Key', 'group': 'integrations'})
        obj.value = key
        obj.save()
        messages.success(request, 'Pexels API key saved.')
        return redirect(request.path + '?tab=search&provider=pexels')

    pexels_configured = ext.pexels_configured()
    pixabay_configured = ext.pixabay_configured()
    configured = pexels_configured if provider == 'pexels' else pixabay_configured

    results = []
    search_error = None
    if configured and is_random and provider == 'pexels':
        results, search_error = ext.pexels_videos_popular_verbose(per_page=18)
    elif configured and q:
        if provider == 'pixabay':
            results, search_error = ext.pixabay_videos_search_verbose(q, per_page=18)
        else:
            results, search_error = ext.pexels_videos_search_verbose(q, per_page=18)

    from shorts.models import Short
    pending_count = Short.objects.filter(is_fetched=True, is_published=False).count()

    return render(request, 'admin_panel/modules/fetch_shorts.html', {
        'tab': tab, 'q': q, 'provider': provider, 'is_random': is_random,
        'results': results, 'search_error': search_error,
        'pexels_configured': pexels_configured, 'pixabay_configured': pixabay_configured,
        'pending_count': pending_count,
    })


@_admin_required
@require_POST
def fetch_shorts_import(request):
    """Import selected video-clip search results as Shorts — video_url only,
    nothing downloaded, matching how Track.audio_url / Movie.video_url work
    for externally-linked media elsewhere in Fetch."""
    approve = request.POST.get('approve') == '1'
    try:
        items = _json.loads(request.POST.get('items', '[]'))
    except Exception:
        items = []

    from shorts.models import Short

    created = 0
    skipped_dupes = 0
    for it in items:
        video_url = it.get('video_url') or ''
        if not video_url:
            continue
        source = it.get('source') or ''
        external_id = it.get('external_id') or ''
        if external_id and Short.objects.filter(is_fetched=True, fetch_source=source, description__contains=f'[id:{external_id}]').exists():
            skipped_dupes += 1
            continue
        query = (it.get('query') or 'Short').strip().title()[:80]
        photographer = it.get('photographer') or 'Unknown'
        title = f"{query} — by {photographer}"[:200]
        short = Short(
            title=title,
            description=f"Clip by {photographer} via {source or 'stock video'}. [id:{external_id}]",
            video_url=video_url,
            thumbnail_url=it.get('thumbnail_url', ''),
            duration_seconds=int(it.get('duration') or 0),
            uploaded_by=request.user,
            is_fetched=True, fetch_source=source,
            is_published=approve,
        )
        short.save()
        created += 1

    if created:
        state = 'imported and approved' if approve else 'imported as pending — approve them from Admin → Shorts'
        msg = f'{created} short(s) {state}.'
        if skipped_dupes:
            msg += f' ({skipped_dupes} already imported, skipped.)'
        messages.success(request, msg)
    else:
        messages.info(request, 'Nothing new to import.')
    return redirect('/admin-panel/fetch/shorts/')


@_admin_required
def admin_shorts(request):
    """Shorts management — list, edit, bulk approve/reject/delete."""
    from shorts.models import Short
    from movies.models import Series

    if request.method == 'POST':
        from django.core.cache import cache
        cache.delete('trending_page_v2')
        action = request.POST.get('action', '')
        if action == 'toggle_publish':
            s = get_object_or_404(Short, pk=request.POST.get('pk'))
            s.is_published = not s.is_published
            s.save(update_fields=['is_published'])
        elif action == 'delete_short':
            get_object_or_404(Short, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Short deleted.')
        elif action == 'edit_short':
            s = get_object_or_404(Short, pk=request.POST.get('pk'))
            s.title = request.POST.get('title', s.title)
            s.description = request.POST.get('description', s.description)
            s.video_url = request.POST.get('video_url', s.video_url)
            s.thumbnail_url = request.POST.get('thumbnail_url', s.thumbnail_url)
            series_pk = request.POST.get('series_pk')
            s.series_id = series_pk or None
            ep = request.POST.get('episode_number')
            s.episode_number = int(ep) if ep and ep.isdigit() else None
            s.is_published = request.POST.get('is_published') == 'on'
            s.is_premium = request.POST.get('is_premium') == 'on'
            s.save()
            messages.success(request, f'"{s.title}" updated.')
        return redirect('/admin-panel/shorts/')

    qs = Short.objects.all().select_related('series', 'uploaded_by').order_by('-created_at')
    from django.core.paginator import Paginator
    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'admin_panel/modules/shorts.html', {
        'page': page, 'series_list': Series.objects.all().order_by('-created_at'),
    })


@_admin_required
@require_POST
def fetch_bulk_action(request):
    """Shared bulk endpoint for Tracks, Movies, Images, and Shorts tables.
    Expects kind=track|movie|image|short, action=approve|reject|delete,
    pks=comma list."""
    kind = request.POST.get('kind', '')
    action = request.POST.get('action', '')
    pks = [p for p in request.POST.get('pks', '').split(',') if p.strip()]
    if not pks or kind not in ('track', 'movie', 'image', 'short') or action not in ('approve', 'reject', 'delete', 'fetch_lyrics', 'refresh_link'):
        return JsonResponse({'ok': False, 'error': 'Invalid request'}, status=400)

    if kind == 'track':
        from music.models import Track
        qs = Track.objects.filter(pk__in=pks)
    elif kind == 'image':
        from images.models import Image
        qs = Image.objects.filter(pk__in=pks)
    elif kind == 'short':
        from shorts.models import Short
        qs = Short.objects.filter(pk__in=pks)
    else:
        from movies.models import Movie
        qs = Movie.objects.filter(pk__in=pks)

    count = qs.count()
    if action == 'refresh_link' and kind == 'short':
        # Pexels video links are temporary signed URLs that expire — this
        # re-fetches a fresh one for each short originally sourced from
        # Pexels, using the saved external ID (stashed in the description).
        import re
        refreshed = 0
        for s in qs:
            if s.fetch_source != 'Pexels':
                continue
            m = re.search(r'\[id:(\d+)\]', s.description or '')
            if not m:
                continue
            new_url = ext.pexels_video_refresh(m.group(1))
            if new_url:
                s.video_url = new_url
                s.save(update_fields=['video_url'])
                refreshed += 1
        return JsonResponse({'ok': True, 'count': count, 'action': action, 'refreshed': refreshed})
    if action == 'approve':
        qs.update(is_published=True)
    elif action == 'reject':
        qs.update(is_published=False)
    elif action == 'delete':
        qs.delete()
    elif action == 'fetch_lyrics' and kind == 'track':
        found = 0
        for t in qs:
            lyrics = ext.lrclib_get_lyrics(t.title, t.artist.name)
            if lyrics:
                t.lyrics_lrc = lyrics
                t.save(update_fields=['lyrics_lrc'])
                found += 1
        return JsonResponse({'ok': True, 'count': count, 'action': action, 'found': found})

    cache.delete('trending_page_v2')
    return JsonResponse({'ok': True, 'count': count, 'action': action})
