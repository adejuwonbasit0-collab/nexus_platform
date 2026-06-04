import os
import math
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Case, When, IntegerField
from django.http import FileResponse, JsonResponse
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

    return render(request, 'music/track.html', {
        'track':      track,
        'comments':   comments,
        'related':    related,
        'user_liked': user_liked,
        'branding':   branding,
    })


# ── Like ──────────────────────────────────────────────────────────────────────

@require_POST
@login_required
def toggle_like(request, pk):
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

    track.downloads_count += 1
    track.save(update_fields=['downloads_count'])

    from accounts.models import DownloadHistory
    DownloadHistory.objects.create(
        user=request.user, content_type='music', object_id=track.pk,
        file_url=track.audio_file.url, ip_address=request.META.get('REMOTE_ADDR'),
    )

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
@login_required
def add_music_comment(request, pk):
    track = get_object_or_404(Track, pk=pk)
    text  = request.POST.get('text', '').strip()
    if text:
        c = MusicComment.objects.create(user=request.user, track=track, text=text)
        return JsonResponse({'ok': True, 'username': request.user.username, 'text': c.text, 'id': c.pk})
    return JsonResponse({'ok': False})
