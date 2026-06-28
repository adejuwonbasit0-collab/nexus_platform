import os
import math
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Case, When, IntegerField
from django.http import FileResponse, JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import (
    Track, Artist, Album, Genre, Playlist,
    MusicComment, TrackLike, TrendingSnapshot, PlatformBranding,
)


def _branding():
    return PlatformBranding.get()


def _ordered_by_ids(qs, ids):
    preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)],
                     output_field=IntegerField())
    return qs.filter(pk__in=ids).order_by(preserved)


# ── Home ──────────────────────────────────────────────────────────────────────

def music_home(request):
    now = timezone.now()

    # Song of the Day
    song_of_day = (
        Track.objects.filter(is_published=True, is_song_of_day=True)
        .select_related('artist', 'album', 'genre').first()
    )
    if not song_of_day:
        song_of_day = (
            Track.objects.filter(is_published=True)
            .order_by('-trend_score')
            .select_related('artist', 'album', 'genre').first()
        )

    # Trending tracks from snapshot
    trend_ids = list(
        TrendingSnapshot.objects.filter(content_type='track')
        .order_by('rank').values_list('object_id', flat=True)[:15]
    )
    if trend_ids:
        trending = list(_ordered_by_ids(
            Track.objects.filter(is_published=True).select_related('artist', 'album'),
            trend_ids,
        ))
    else:
        trending = list(
            Track.objects.filter(is_published=True)
            .order_by('-trend_score')
            .select_related('artist', 'album')[:15]
        )

    # Trending artists from snapshot
    art_ids = list(
        TrendingSnapshot.objects.filter(content_type='artist')
        .order_by('rank').values_list('object_id', flat=True)[:8]
    )
    if art_ids:
        trending_artists = list(_ordered_by_ids(Artist.objects.all(), art_ids))
    else:
        trending_artists = list(Artist.objects.order_by('-trend_score')[:8])

    # New releases last 30 days
    new_releases = list(
        Track.objects.filter(
            is_published=True,
            created_at__gte=now - timedelta(days=30),
        ).select_related('artist', 'album').order_by('-created_at')[:12]
    )

    # Popular albums
    popular_albums = list(
        Album.objects.filter(is_published=True).order_by('-plays_count')[:8]
    )

    # Top artists all-time
    top_artists = list(Artist.objects.order_by('-trend_score')[:10])

    genres   = Genre.objects.all()
    branding = _branding()

    return render(request, 'music/home.html', {
        'song_of_day':      song_of_day,
        'trending':         trending,
        'trending_artists': trending_artists,
        'new_releases':     new_releases,
        'popular_albums':   popular_albums,
        'top_artists':      top_artists,
        'genres':           genres,
        'branding':         branding,
    })


# ── Browse ────────────────────────────────────────────────────────────────────

def music_browse(request):
    qs = Track.objects.filter(is_published=True).select_related('artist', 'album', 'genre')

    q           = request.GET.get('q', '')
    genre_slug  = request.GET.get('genre', '')
    artist_slug = request.GET.get('artist', '')
    year        = request.GET.get('year', '')
    sort        = request.GET.get('sort', '-trend_score')

    if q:           qs = qs.filter(Q(title__icontains=q) | Q(artist__name__icontains=q) | Q(album__title__icontains=q))
    if genre_slug:  qs = qs.filter(genre__slug=genre_slug)
    if artist_slug: qs = qs.filter(artist__slug=artist_slug)
    if year:        qs = qs.filter(release_year=year)

    allowed_sorts = ('-trend_score', '-plays_count', '-created_at', '-downloads_count', '-likes_count')
    if sort in allowed_sorts:
        qs = qs.order_by(sort)

    genres   = Genre.objects.all()
    artists  = Artist.objects.order_by('name')
    branding = _branding()

    return render(request, 'music/browse.html', {
        'tracks':        qs,
        'genres':        genres,
        'artists':       artists,
        'q':             q,
        'branding':      branding,
        'active_genre':  genre_slug,
        'active_artist': artist_slug,
    })


# ── Artist ────────────────────────────────────────────────────────────────────

def artist_detail(request, slug):
    artist = get_object_or_404(Artist, slug=slug)
    tracks  = artist.tracks.filter(is_published=True).select_related('album', 'genre').order_by('-trend_score')
    albums  = artist.albums.filter(is_published=True).order_by('-release_year')
    collabs = (
        Track.objects.filter(featured_artists=artist, is_published=True)
        .select_related('artist', 'album').order_by('-created_at')
    )
    latest_comments = (
        MusicComment.objects.filter(track__artist=artist)
        .select_related('user', 'track').order_by('-created_at')[:10]
    )
    artist_genres = Genre.objects.filter(track__artist=artist).distinct()
    similar = (
        Artist.objects.filter(tracks__genre__in=artist_genres)
        .exclude(pk=artist.pk).distinct().order_by('-trend_score')[:6]
    )
    branding = _branding()

    return render(request, 'music/artist.html', {
        'artist':          artist,
        'tracks':          tracks,
        'albums':          albums,
        'collabs':         collabs,
        'latest_comments': latest_comments,
        'similar':         similar,
        'branding':        branding,
    })


# ── Album ─────────────────────────────────────────────────────────────────────

def album_detail(request, slug):
    album  = get_object_or_404(Album, slug=slug, is_published=True)
    tracks = album.tracks.filter(is_published=True).select_related('artist', 'genre').order_by('id')
    more_albums = (
        Album.objects.filter(artist=album.artist, is_published=True)
        .exclude(pk=album.pk).order_by('-release_year')[:5]
    )
    branding = _branding()

    return render(request, 'music/album.html', {
        'album':       album,
        'tracks':      tracks,
        'more_albums': more_albums,
        'branding':    branding,
    })


# ── Track ─────────────────────────────────────────────────────────────────────

def track_detail(request, slug):
    track = get_object_or_404(Track, slug=slug, is_published=True)

    sk = f'tr_{track.pk}'
    if not request.session.get(sk):
        track.plays_count += 1
        track.save(update_fields=['plays_count'])
        if track.album:
            track.album.plays_count += 1
            track.album.save(update_fields=['plays_count'])
        request.session[sk] = True

    comments  = track.comments.select_related('user')[:30]
    related   = (
        Track.objects.filter(artist=track.artist, is_published=True)
        .exclude(pk=track.pk).order_by('-trend_score')[:8]
    )
    user_liked = (
        TrackLike.objects.filter(user=request.user, track=track).exists()
        if request.user.is_authenticated else False
    )
    branding = _branding()
    user_playlists = (
        Playlist.objects.filter(owner=request.user)
        if request.user.is_authenticated else []
    )

    return render(request, 'music/track.html', {
        'track':          track,
        'comments':       comments,
        'related':        related,
        'user_liked':     user_liked,
        'branding':       branding,
        'user_playlists': user_playlists,
    })


# ── Like ──────────────────────────────────────────────────────────────────────

@require_POST
def toggle_like(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error":"login_required","count":0,"liked":False},status=401)
    track = get_object_or_404(Track, pk=pk)
    like, created = TrackLike.objects.get_or_create(user=request.user, track=track)
    if not created:
        like.delete()
        track.likes_count = max(0, track.likes_count - 1)
        liked = False
    else:
        track.likes_count += 1
        liked = True
    track.save(update_fields=['likes_count'])
    return JsonResponse({'liked': liked, 'count': track.likes_count})


# ── Download ──────────────────────────────────────────────────────────────────

@login_required
def download_track(request, pk):
    track = get_object_or_404(Track, pk=pk, is_published=True)

    if track.is_premium and not request.user.is_premium:
        return redirect('/subscriptions/')

    if not track.has_audio:
        raise Http404

    track.downloads_count += 1
    track.save(update_fields=['downloads_count'])

    from accounts.models import DownloadHistory
    DownloadHistory.objects.create(
        user=request.user, content_type='music', object_id=track.pk,
        file_url=track.playable_url, ip_address=request.META.get('REMOTE_ADDR'),
    )

    if track.is_external_audio:
        # No local copy to serve — send the user to the source link directly.
        return redirect(track.audio_url)

    # Branded filename: NEXUS_ArtistName_TrackTitle.mp3
    try:
        from core.models import SiteSettings
        pname = SiteSettings.objects.get(key='site_name').value or 'NEXUS'
    except Exception:
        pname = 'NEXUS'

    ext     = os.path.splitext(track.audio_file.name)[1] or '.mp3'
    safe    = lambda s: s.replace(' ', '_').replace('/', '-')
    dl_name = f"{safe(pname.upper())}_{safe(track.artist.name)}_{safe(track.title)}{ext}"

    return FileResponse(
        open(track.audio_file.path, 'rb'),
        as_attachment=True,
        filename=dl_name,
    )


# ── Comment ───────────────────────────────────────────────────────────────────

@require_POST
def add_music_comment(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok":False,"error":"login_required"},status=401)
    track = get_object_or_404(Track, pk=pk)
    text  = request.POST.get('text', '').strip()
    if text:
        c = MusicComment.objects.create(user=request.user, track=track, text=text)
        return JsonResponse({'ok': True, 'username': request.user.username, 'text': c.text, 'id': c.pk})
    return JsonResponse({'ok': False})

# ── Playlists ──────────────────────────────────────────────────────────────────

from django.contrib.auth.decorators import login_required

@login_required
def playlist_list(request):
    playlists = Playlist.objects.filter(owner=request.user).prefetch_related('tracks')
    public    = Playlist.objects.filter(is_public=True).exclude(owner=request.user).order_by('-created_at')[:12]
    return render(request, 'music/playlists.html', {
        'playlists': playlists,
        'public':    public,
    })


@login_required
@require_POST
def playlist_create(request):
    title = request.POST.get('title', '').strip()
    if not title:
        from django.contrib import messages
        messages.error(request, 'Playlist title is required.')
        return redirect('playlist_list')
    p = Playlist.objects.create(
        owner=request.user,
        title=title,
        is_public=request.POST.get('is_public') == '1',
    )
    # Optionally add a track right away (from "add to playlist" flow)
    track_pk = request.POST.get('track_pk')
    if track_pk:
        try:
            p.tracks.add(Track.objects.get(pk=track_pk))
        except Track.DoesNotExist:
            pass
    return redirect('playlist_detail', pk=p.pk)


@login_required
def playlist_detail(request, pk):
    p = get_object_or_404(Playlist, pk=pk)
    if not p.is_public and p.owner != request.user:
        from django.http import Http404
        raise Http404
    tracks  = p.tracks.select_related('artist', 'album').order_by('title')
    # Tracks the user could add (not already in playlist, published)
    all_tracks = Track.objects.filter(is_published=True).exclude(
        pk__in=tracks.values_list('pk', flat=True)
    ).select_related('artist')[:50]
    return render(request, 'music/playlist_detail.html', {
        'playlist':   p,
        'tracks':     tracks,
        'all_tracks': all_tracks,
        'is_owner':   (request.user == p.owner),
    })


@login_required
@require_POST
def playlist_add_track(request, pk, track_pk):
    p     = get_object_or_404(Playlist, pk=pk, owner=request.user)
    track = get_object_or_404(Track, pk=track_pk, is_published=True)
    p.tracks.add(track)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'count': p.tracks.count()})
    return redirect('playlist_detail', pk=pk)


@login_required
@require_POST
def playlist_remove_track(request, pk, track_pk):
    p     = get_object_or_404(Playlist, pk=pk, owner=request.user)
    track = get_object_or_404(Track, pk=track_pk)
    p.tracks.remove(track)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'count': p.tracks.count()})
    return redirect('playlist_detail', pk=pk)


@login_required
@require_POST
def playlist_delete(request, pk):
    p = get_object_or_404(Playlist, pk=pk, owner=request.user)
    p.delete()
    from django.contrib import messages
    messages.success(request, 'Playlist deleted.')
    return redirect('playlist_list')


# ── Genre Tracks ──────────────────────────────────────────────────────────────

def genre_tracks(request, slug):
    from music.models import Genre as MusicGenre
    genre  = get_object_or_404(MusicGenre, slug=slug)
    tracks = Track.objects.filter(genre=genre, is_published=True).select_related('artist', 'album').order_by('-trend_score')
    return render(request, 'music/genre_tracks.html', {
        'genre':  genre,
        'tracks': tracks,
    })


# ── Queue API ─────────────────────────────────────────────────────────────────

def get_queue(request, context, pk):
    """Returns a JSON list of tracks for the mini-player queue.

    context = 'album'   → all tracks on album pk
    context = 'artist'  → all tracks by artist pk
    context = 'genre'   → all tracks in genre pk
    context = 'playlist'→ all tracks in playlist pk
    """
    tracks = []
    try:
        if context == 'album':
            qs = Track.objects.filter(album_id=pk, is_published=True).select_related('artist', 'album').order_by('title')
        elif context == 'artist':
            qs = Track.objects.filter(artist_id=pk, is_published=True).select_related('artist', 'album').order_by('-trend_score')
        elif context == 'genre':
            qs = Track.objects.filter(genre_id=pk, is_published=True).select_related('artist', 'album').order_by('-trend_score')
        elif context == 'playlist':
            p  = get_object_or_404(Playlist, pk=pk)
            if not p.is_public and (not request.user.is_authenticated or p.owner != request.user):
                return JsonResponse({'error': 'private'}, status=403)
            qs = p.tracks.filter(is_published=True).select_related('artist', 'album')
        else:
            return JsonResponse({'error': 'unknown context'}, status=400)

        for t in qs[:50]:
            tracks.append({
                'pk':    t.pk,
                'title': t.title,
                'artist': t.artist.name if t.artist else '',
                'url':   t.playable_url or '',
                'cover': (t.cover_image.url if t.cover_image else
                         (t.album.cover_image.url if t.album and t.album.cover_image else '')),
                'detail': f'/music/track/{t.slug}/',
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'tracks': tracks})


# ── Discover (Shazam-like) ────────────────────────────────────────────────────

def music_discover(request):
    """Full-page Shazam-like UI — user holds up their phone to music playing,
    we capture audio from the microphone, then try to match it against the
    platform's own track library."""
    return render(request, 'music/discover.html')


@require_POST
def music_identify(request):
    """
    4-layer music identification:
    1. Whisper transcribes the audio blob → text search in DB
    2. AudD.io global fingerprinting (works for any song worldwide)
    3. Claude AI matches transcript against DB track list
    4. Duration + keyword fallback (always returns something)
    """
    from music.identify_service import (
        whisper_transcribe, audd_identify,
        claude_identify, db_search, serialise_track,
    )

    # Collect inputs
    hint_title   = request.POST.get('hint_title', '').strip()
    hint_artist  = request.POST.get('hint_artist', '').strip()
    hint_duration = request.POST.get('duration', '')
    audio_file   = request.FILES.get('audio')
    audio_bytes  = audio_file.read() if audio_file else None

    transcript = ''
    external_match = None   # from AudD
    db_match  = None        # from own library
    candidates = []

    # ── Layer 1: Whisper transcription ────────────────────────────────────
    if audio_bytes:
        mime = getattr(audio_file, 'content_type', 'audio/webm')
        transcript = whisper_transcribe(audio_bytes, mime)
        if transcript:
            # Update hint_title with transcribed words
            hint_title = hint_title or transcript[:200]

    # ── Layer 2: AudD global fingerprint ──────────────────────────────────
    if audio_bytes:
        ext_result = audd_identify(audio_bytes)
        if ext_result:
            external_match = ext_result
            # Also search our DB for the identified title
            db_hits = db_search(
                hint_title=ext_result.get('title',''),
                hint_artist=ext_result.get('artist','')
            )
            if db_hits:
                db_match = serialise_track(db_hits[0])

    # ── Layer 3: DB search with all hints ─────────────────────────────────
    db_candidates = db_search(hint_title, hint_artist, hint_duration)

    # ── Layer 4: Claude narrows DB candidates ─────────────────────────────
    if not db_match and transcript and db_candidates:
        track_dicts = [serialise_track(t) for t in db_candidates]
        claude_pick = claude_identify(transcript, track_dicts)
        if claude_pick:
            db_match = claude_pick

    # Build candidates list
    candidates = [serialise_track(t) for t in db_candidates]

    # If AudD found something not in our DB, prepend it as a suggestion
    if external_match and not db_match:
        candidates.insert(0, {
            'pk': None,
            'title':  external_match.get('title',''),
            'artist': external_match.get('artist',''),
            'album':  external_match.get('album',''),
            'slug':   None,
            'cover':  external_match.get('cover',''),
            'duration': 0,
            'url':    '',
            'in_library': False,
            'spotify_url': (external_match.get('spotify',{}) or {}).get('external_urls',{}).get('spotify',''),
            'apple_url':   (external_match.get('apple_music',{}) or {}).get('url',''),
        })

    matched  = bool(db_match or external_match)
    best     = db_match or (candidates[0] if candidates else None)

    return JsonResponse({
        'matched':    matched,
        'transcript': transcript,
        'track':      best,
        'external':   external_match,
        'candidates': candidates[:10],
    })


# ── Lyrics (stored + AI generation) ──────────────────────────────────────────

def track_lyrics(request, pk):
    """Returns lyrics as JSON.
    Priority:
    1. Stored LRC (timestamped) lyrics  → real-time scrolling
    2. Stored plain lyrics              → static display
    3. Whisper transcription of audio   → auto-generated LRC
    4. Claude AI text generation        → AI plain lyrics
    """
    track = get_object_or_404(Track, pk=pk, is_published=True)
    artist_name = track.artist.name if track.artist else 'Unknown Artist'

    # 1. Stored LRC
    if track.lyrics_lrc.strip():
        return JsonResponse({
            'ok': True, 'has_lrc': True,
            'lyrics': track.lyrics, 'lrc': track.lyrics_lrc,
            'ai_generated': False, 'source': 'stored_lrc',
            'title': track.title, 'artist': artist_name,
        })

    # 2. Stored plain lyrics
    if track.lyrics.strip():
        return JsonResponse({
            'ok': True, 'has_lrc': False,
            'lyrics': track.lyrics, 'lrc': '',
            'ai_generated': False, 'source': 'stored',
            'title': track.title, 'artist': artist_name,
        })

    from core.utils import get_ai_key
    import json as _json, urllib.request

    # 3. Whisper transcription (if audio file exists and OpenAI key configured)
    openai_key = get_ai_key('openai')
    if openai_key and track.audio_file:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            with open(track.audio_file.path, 'rb') as f:
                # verbose_json gives us word-level timestamps for LRC
                transcript = client.audio.transcriptions.create(
                    model='whisper-1',
                    file=f,
                    response_format='verbose_json',
                    timestamp_granularities=['segment'],
                )
            # Build LRC from Whisper segments
            lrc_lines = []
            plain_lines = []
            for seg in (transcript.segments or []):
                t = seg.get('start', 0) if isinstance(seg, dict) else seg.start
                text = seg.get('text', '').strip() if isinstance(seg, dict) else seg.text.strip()
                if text:
                    mins = int(t // 60)
                    secs = t % 60
                    lrc_lines.append(f'[{mins:02d}:{secs:05.2f}] {text}')
                    plain_lines.append(text)
            if lrc_lines:
                lrc_text = '\n'.join(lrc_lines)
                plain_text = '[Whisper Transcription]\n\n' + '\n'.join(plain_lines)
                Track.objects.filter(pk=pk).update(lyrics=plain_text, lyrics_lrc=lrc_text)
                return JsonResponse({
                    'ok': True, 'has_lrc': True,
                    'lyrics': plain_text, 'lrc': lrc_text,
                    'ai_generated': True, 'source': 'whisper',
                    'title': track.title, 'artist': artist_name,
                })
        except Exception:
            pass  # fall through to Claude

    # 4. Claude AI text generation
    api_key = get_ai_key('anthropic')
    if not api_key:
        return JsonResponse({
            'ok': False, 'error': 'no_key',
            'message': 'No API key configured. Add an Anthropic or OpenAI key in Settings → AI Settings.',
        })

    try:
        genre_name = track.genre.name if track.genre else ''
        prompt = (
            f'Write complete, original song lyrics for a track called "{track.title}" '
            f'by {artist_name}'
            + (f' in the {genre_name} genre' if genre_name else '')
            + '. Include verses, a chorus, and a bridge. Format with clear section '
            'labels like [Verse 1], [Chorus], [Bridge]. '
            'These are AI-generated lyrics for demonstration purposes.'
        )
        payload = {
            'model': 'claude-sonnet-4-6',
            'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        data = _json.dumps(payload).encode()
        req  = urllib.request.Request(
            'https://api.anthropic.com/v1/messages', data=data,
            headers={'Content-Type': 'application/json',
                     'x-api-key': api_key, 'anthropic-version': '2023-06-01'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read())
        generated = result['content'][0]['text']
        plain = '[AI Generated]\n\n' + generated
        Track.objects.filter(pk=pk).update(lyrics=plain)
        return JsonResponse({
            'ok': True, 'has_lrc': False,
            'lyrics': plain, 'lrc': '',
            'ai_generated': True, 'source': 'claude',
            'title': track.title, 'artist': artist_name,
        })

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})
