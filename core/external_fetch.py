"""
External content fetch service — powers the admin "Fetch" tools for Music
and Movies. Music uses the free, keyless iTunes Search/RSS API. Movies use
TMDB (themoviedb.org), which needs a free API key stored via
SiteSettings (key='tmdb_api_key', set from Admin → Fetch Movies → Settings).

All network calls are wrapped in short timeouts and broad except blocks so a
slow or unreachable third party can never hang a request or 500 the page —
callers just get an empty list back and the template shows "no results".
"""
import json
import urllib.request
import urllib.parse
import urllib.error


TIMEOUT = 10

# ── iTunes genre IDs (used for both search-affinity and RSS charts) ───────────
ITUNES_GENRES = [
    ('14', 'Pop'), ('18', 'Hip-Hop/Rap'), ('15', 'R&B/Soul'), ('17', 'Dance'),
    ('7',  'Electronic'), ('21', 'Rock'), ('20', 'Alternative'), ('6',  'Country'),
    ('12', 'Latin'), ('24', 'Reggae'), ('19', 'World'), ('11', 'Jazz'),
    ('5',  'Classical'), ('2',  'Blues'), ('26', 'Gospel & Christian'), ('16', 'Reggaeton'),
]


def download_image_into(instance, field_name, url, filename_hint='cover.jpg'):
    """Download a remote image URL and attach it to instance.<field_name>.
    Silently no-ops on any failure — a missing cover should never block an
    import."""
    if not url:
        return False
    try:
        from django.core.files.base import ContentFile
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content = resp.read()
        if not content:
            return False
        ext = 'jpg'
        for e in ('.png', '.webp', '.jpeg', '.jpg'):
            if e in url.lower():
                ext = e.replace('.', '')
                break
        name = f"{filename_hint.rsplit('.', 1)[0][:60]}.{ext}"
        getattr(instance, field_name).save(name, ContentFile(content), save=False)
        return True
    except Exception:
        return False


def _fix_escaped_unicode(s):
    """Apple's RSS chart feed sometimes contains literal \\u002D-style escape
    text inside the JSON string values themselves (not real JSON escapes,
    so json.loads doesn't decode them) — this shows up as genre names like
    'Afro\\u002DPop' instead of 'Afro-Pop'. Clean those up."""
    if not s or '\\u' not in s:
        return s
    import re
    def repl(m):
        try:
            return chr(int(m.group(1), 16))
        except Exception:
            return m.group(0)
    return re.sub(r'\\u([0-9a-fA-F]{4})', repl, s)


def _get_json(url, data=None, headers=None, timeout=TIMEOUT):
    try:
        req = urllib.request.Request(url, data=data, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='ignore'))
    except Exception:
        return None


def _get_json_verbose(url, headers=None, timeout=TIMEOUT):
    """Same as _get_json but returns (data, error_message) instead of
    swallowing failures — used where we want to show the admin exactly
    why a search came back empty (network block vs. bad key vs. a
    genuinely empty result) rather than a generic 'no results'."""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='ignore')), None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, f'Rejected with HTTP {e.code} — the saved API key is likely invalid or expired.'
        return None, f'HTTP {e.code} error from the server.'
    except Exception as e:
        return None, f'{type(e).__name__}: {str(e)[:150]} — this server likely can\'t reach that domain at all.'


# ── Music: iTunes ──────────────────────────────────────────────────────────────

def itunes_search(term, limit=25):
    """Free-text search for songs. No API key required."""
    if not term or not term.strip():
        return []
    q = urllib.parse.urlencode({'term': term.strip(), 'entity': 'song', 'limit': limit})
    data = _get_json(f'https://itunes.apple.com/search?{q}')
    if not data:
        return []
    return [_itunes_to_result(r) for r in data.get('results', []) if r.get('trackName')]


def itunes_chart(genre_id='', feed='topsongs', limit=50):
    """Trending / latest charts via the iTunes RSS feed API. feed is one of
    'topsongs' (trending) or 'newmusic' (latest releases).
    Returns items with cover art straight from the RSS feed (upgraded to
    600x600) and no preview_url yet — previews are looked up individually
    at import time (see enrich_for_import) so a handful of failed lookups
    can never blank out an entire browse page of results."""
    genre_part = f'/genre={genre_id}' if genre_id else ''
    url = f'https://itunes.apple.com/us/rss/{feed}/limit={limit}{genre_part}/json'
    data = _get_json(url)
    if not data:
        return []
    try:
        entries = data['feed']['entry']
    except Exception:
        return []
    if isinstance(entries, dict):
        entries = [entries]
    out = []
    for e in entries:
        try:
            title = _fix_escaped_unicode(e['im:name']['label'])
            artist = _fix_escaped_unicode(e['im:artist']['label'])
            images = e.get('im:image', [])
            cover = images[-1]['label'] if images else ''
            if cover:
                cover = cover.replace('100x100', '600x600').replace('170x170', '600x600')
            itunes_id = e.get('id', {}).get('attributes', {}).get('im:id', '')
            out.append({
                'source': 'iTunes', 'external_id': itunes_id,
                'title': title, 'artist': artist, 'album': '',
                'cover': cover, 'preview_url': '',
                'genre': _fix_escaped_unicode(e.get('category', {}).get('attributes', {}).get('label', '')),
                'release_year': '',
            })
        except Exception:
            continue
    return out


def enrich_for_import(item):
    """Fill in a missing preview_url/cover/album/year for a single item right
    before it's imported. Called per-selected-item (not per browse-page-item)
    so it's fast and a single failed lookup only affects that one track."""
    if item.get('preview_url'):
        return item
    try:
        q = urllib.parse.urlencode({'term': f"{item.get('artist','')} {item.get('title','')}", 'entity': 'song', 'limit': 1})
        data = _get_json(f'https://itunes.apple.com/search?{q}', timeout=8)
        if data and data.get('results'):
            found = data['results'][0]
            item['preview_url'] = found.get('previewUrl', '') or item.get('preview_url', '')
            item['album'] = found.get('collectionName', '') or item.get('album', '')
            item['release_year'] = (found.get('releaseDate') or '')[:4] or item.get('release_year', '')
            if not item.get('cover') and found.get('artworkUrl100'):
                item['cover'] = found['artworkUrl100'].replace('100x100', '600x600')
    except Exception:
        pass
    return item


def _itunes_to_result(r):
    return {
        'source': 'iTunes',
        'external_id': str(r.get('trackId', '')),
        'title': _fix_escaped_unicode(r.get('trackName', '')),
        'artist': _fix_escaped_unicode(r.get('artistName', '')),
        'album': _fix_escaped_unicode(r.get('collectionName', '')),
        'cover': (r.get('artworkUrl100') or '').replace('100x100', '600x600'),
        'preview_url': r.get('previewUrl', ''),
        'genre': _fix_escaped_unicode(r.get('primaryGenreName', '')),
        'release_year': (r.get('releaseDate') or '')[:4],
        'duration_ms': r.get('trackTimeMillis', 0),
    }


# ── Movies: TMDB ────────────────────────────────────────────────────────────────

def _tmdb_key():
    try:
        from core.models import SiteSettings
        obj = SiteSettings.objects.filter(key='tmdb_api_key').first()
        return obj.value.strip() if obj and obj.value else ''
    except Exception:
        return ''


def tmdb_configured():
    return bool(_tmdb_key())


IMG_BASE = 'https://image.tmdb.org/t/p/w780'


def _tmdb_get(path, params=None):
    key = _tmdb_key()
    if not key:
        return None
    params = params or {}
    params['api_key'] = key
    q = urllib.parse.urlencode(params)
    return _get_json(f'https://api.themoviedb.org/3{path}?{q}')


def tmdb_genre_list():
    data = _tmdb_get('/genre/movie/list')
    if not data:
        return []
    return [(str(g['id']), g['name']) for g in data.get('genres', [])]


def tmdb_search(query, limit=20):
    data = _tmdb_get('/search/movie', {'query': query, 'include_adult': 'false'})
    return _tmdb_results(data, limit)


def tmdb_trending(limit=20):
    data = _tmdb_get('/trending/movie/day')
    return _tmdb_results(data, limit)


def tmdb_now_playing(limit=20):
    data = _tmdb_get('/movie/now_playing')
    return _tmdb_results(data, limit)


def tmdb_by_genre(genre_id, limit=20):
    data = _tmdb_get('/discover/movie', {'with_genres': genre_id, 'sort_by': 'popularity.desc'})
    return _tmdb_results(data, limit)


def _tmdb_results(data, limit):
    if not data:
        return []
    out = []
    for m in data.get('results', [])[:limit]:
        out.append({
            'source': 'TMDB',
            'external_id': str(m.get('id', '')),
            'title': m.get('title') or m.get('original_title', ''),
            'description': m.get('overview', ''),
            'cover': f"{IMG_BASE}{m['poster_path']}" if m.get('poster_path') else '',
            'backdrop': f"{IMG_BASE}{m['backdrop_path']}" if m.get('backdrop_path') else '',
            'release_year': (m.get('release_date') or '')[:4],
            'rating': m.get('vote_average', 0),
            'genre_ids': m.get('genre_ids', []),
        })
    return out


def tmdb_trailer_url(tmdb_id):
    """Best-effort YouTube trailer link for a TMDB movie id."""
    data = _tmdb_get(f'/movie/{tmdb_id}/videos')
    if not data:
        return ''
    for v in data.get('results', []):
        if v.get('site') == 'YouTube' and v.get('type') == 'Trailer':
            return f"https://www.youtube.com/watch?v={v['key']}"
    return ''


def tmdb_credits(tmdb_id, limit=12):
    """Real cast — actor's actual name, character they played, and a
    photo — pulled straight from TMDB, the same info any normal movie
    site shows. Returns a JSON-ready list, empty list on failure."""
    data = _tmdb_get(f'/movie/{tmdb_id}/credits')
    if not data:
        return []
    out = []
    for c in data.get('cast', [])[:limit]:
        out.append({
            'name': c.get('name', ''),
            'character': c.get('character', ''),
            'photo_url': f"{IMG_BASE}{c['profile_path']}" if c.get('profile_path') else '',
        })
    return out


# ── Stock images: Pexels ─────────────────────────────────────────────────────

def _pexels_key():
    try:
        from core.models import SiteSettings
        obj = SiteSettings.objects.filter(key='pexels_api_key').first()
        return obj.value.strip() if obj and obj.value else ''
    except Exception:
        return ''


def pexels_configured():
    return bool(_pexels_key())


def pexels_search(query, per_page=15):
    key = _pexels_key()
    if not key or not query.strip():
        return []
    q = urllib.parse.urlencode({'query': query.strip(), 'per_page': per_page, 'orientation': 'landscape'})
    data = _get_json(f'https://api.pexels.com/v1/search?{q}', headers={'Authorization': key})
    if not data:
        return []
    return _pexels_parse(data)


def pexels_search_verbose(query, per_page=15):
    """Returns (results, error_message). error_message is None on success
    (even if results is genuinely empty) — used by the interactive Fetch
    Images page so a failed request looks different from a real zero-hit
    search instead of both showing a blank 'no results'."""
    key = _pexels_key()
    if not key:
        return [], 'No Pexels API key saved yet.'
    if not query.strip():
        return [], None
    q = urllib.parse.urlencode({'query': query.strip(), 'per_page': per_page, 'orientation': 'landscape'})
    data, err = _get_json_verbose(f'https://api.pexels.com/v1/search?{q}', headers={'Authorization': key})
    if err:
        return [], err
    return _pexels_parse(data), None


def _pexels_parse(data):
    out = []
    for p in data.get('photos', []):
        out.append({
            'source': 'Pexels',
            'external_id': str(p.get('id', '')),
            'thumb': p.get('src', {}).get('medium', ''),
            'full': p.get('src', {}).get('large2x') or p.get('src', {}).get('large', ''),
            'photographer': p.get('photographer', ''),
            'page_url': p.get('url', ''),
        })
    return out


# ── Stock images: Pixabay (alternative source) ──────────────────────────────
# A second provider so there's a fallback if Pexels' domain happens to be
# blocked/unreachable for a given host but Pixabay's isn't, or if a Pexels
# key won't validate for some other reason.

def _pixabay_key():
    try:
        from core.models import SiteSettings
        obj = SiteSettings.objects.filter(key='pixabay_api_key').first()
        return obj.value.strip() if obj and obj.value else ''
    except Exception:
        return ''


def pixabay_configured():
    return bool(_pixabay_key())


def pexels_curated_verbose(per_page=18):
    """Random/curated photos, no search term needed — Pexels' own
    hand-picked 'trending right now' feed."""
    key = _pexels_key()
    if not key:
        return [], 'No Pexels API key saved yet.'
    import random
    page = random.randint(1, 50)  # different picks each click
    q = urllib.parse.urlencode({'per_page': per_page, 'page': page})
    data, err = _get_json_verbose(f'https://api.pexels.com/v1/curated?{q}', headers={'Authorization': key})
    if err:
        return [], err
    return _pexels_parse(data), None


_RANDOM_TERMS = [
    'music', 'concert', 'city skyline', 'nature', 'abstract art', 'neon lights',
    'ocean', 'mountains', 'studio microphone', 'vinyl records', 'crowd concert',
    'sunset', 'urban street', 'stage lights', 'headphones', 'guitar',
]


def pixabay_random_verbose(per_page=18):
    """Pixabay has no curated/random endpoint, so this searches a randomly
    picked broad term with popularity ordering as a stand-in for 'surprise
    me'."""
    import random
    term = random.choice(_RANDOM_TERMS)
    return pixabay_search_verbose(term, per_page=per_page)


def pixabay_search_verbose(query, per_page=18):
    """Returns (results, error_message), same contract as
    pexels_search_verbose."""
    key = _pixabay_key()
    if not key:
        return [], 'No Pixabay API key saved yet.'
    if not query.strip():
        return [], None
    q = urllib.parse.urlencode({
        'key': key, 'q': query.strip(), 'image_type': 'photo',
        'orientation': 'horizontal', 'per_page': max(per_page, 3),
    })
    data, err = _get_json_verbose(f'https://pixabay.com/api/?{q}')
    if err:
        return [], err
    out = []
    for p in data.get('hits', []):
        out.append({
            'source': 'Pixabay',
            'external_id': str(p.get('id', '')),
            'thumb': p.get('webformatURL', ''),
            'full': p.get('largeImageURL') or p.get('webformatURL', ''),
            'photographer': p.get('user', ''),
            'page_url': p.get('pageURL', ''),
        })
    return out, None


# ── Video shorts: Pexels Videos ──────────────────────────────────────────────
# Real stock video clips with direct mp4 URLs — used for Fetch Shorts. Saved
# as a URL (video_url), never downloaded to this server, to keep storage
# usage minimal.

def pexels_video_refresh(external_id):
    """Pexels video file links are temporary, signed Vimeo URLs that expire
    after a while — even though the video itself is permanent, the link we
    saved stops working. Re-fetching the video by its Pexels ID returns a
    fresh, currently-valid link. Returns a new video_url or '' on failure."""
    key = _pexels_key()
    if not key or not external_id:
        return ''
    data = _get_json(f'https://api.pexels.com/videos/videos/{external_id}', headers={'Authorization': key})
    if not data:
        return ''
    files = data.get('video_files', [])
    files_sorted = sorted(files, key=lambda f: f.get('width', 9999))
    best = next((f for f in files_sorted if f.get('height', 0) >= f.get('width', 1)), None) or (files_sorted[0] if files_sorted else None)
    return best.get('link', '') if best else ''


def pexels_videos_search_verbose(query, per_page=15):
    """Returns (results, error_message). Each result has a direct .mp4 URL
    (video_url) plus a thumbnail image URL — nothing is ever downloaded to
    this server, only the link is stored."""
    key = _pexels_key()
    if not key:
        return [], 'No Pexels API key saved yet.'
    if not query.strip():
        return [], None
    q = urllib.parse.urlencode({'query': query.strip(), 'per_page': per_page, 'orientation': 'portrait'})
    data, err = _get_json_verbose(f'https://api.pexels.com/videos/search?{q}', headers={'Authorization': key})
    if err:
        return [], err
    return _pexels_videos_parse(data), None


def pexels_videos_popular_verbose(per_page=15):
    """Random/popular videos, no search term needed — 'surprise me'."""
    key = _pexels_key()
    if not key:
        return [], 'No Pexels API key saved yet.'
    import random
    page = random.randint(1, 30)
    q = urllib.parse.urlencode({'per_page': per_page, 'page': page})
    data, err = _get_json_verbose(f'https://api.pexels.com/videos/popular?{q}', headers={'Authorization': key})
    if err:
        return [], err
    return _pexels_videos_parse(data), None


def _pexels_videos_parse(data):
    out = []
    for v in data.get('videos', []):
        files = v.get('video_files', [])
        # Prefer a reasonably small vertical/portrait file over the largest
        # available — these are meant to stream instantly on mobile.
        files_sorted = sorted(files, key=lambda f: f.get('width', 9999))
        best = next((f for f in files_sorted if f.get('height', 0) >= f.get('width', 1)), None) or (files_sorted[0] if files_sorted else None)
        if not best:
            continue
        out.append({
            'source': 'Pexels',
            'external_id': str(v.get('id', '')),
            'video_url': best.get('link', ''),
            'thumbnail_url': v.get('image', ''),
            'duration': v.get('duration', 0),
            'photographer': v.get('user', {}).get('name', ''),
        })
    return out


def pixabay_videos_search_verbose(query, per_page=18):
    """Same contract, Pixabay video source as a second option."""
    key = _pixabay_key()
    if not key:
        return [], 'No Pixabay API key saved yet.'
    if not query.strip():
        return [], None
    q = urllib.parse.urlencode({'key': key, 'q': query.strip(), 'per_page': max(per_page, 3)})
    data, err = _get_json_verbose(f'https://pixabay.com/api/videos/?{q}')
    if err:
        return [], err
    out = []
    for v in data.get('hits', []):
        videos = v.get('videos', {})
        best = videos.get('medium') or videos.get('small') or videos.get('large') or {}
        if not best.get('url'):
            continue
        out.append({
            'source': 'Pixabay',
            'external_id': str(v.get('id', '')),
            'video_url': best.get('url', ''),
            'thumbnail_url': best.get('thumbnail', ''),
            'duration': v.get('duration', 0),
            'photographer': v.get('user', ''),
        })
    return out, None


# ── Archive.org — public-domain / freely-licensed feature films ─────────────
# Free, keyless, no auth required. Every result here is either public
# domain or explicitly openly-licensed by its uploader, so it's safe to
# stream directly — unlike a commercial catalogue, nothing here needs a
# license check.

def archive_org_configured():
    return True  # no key needed


def archive_org_search(query, per_page=20):
    """Search Archive.org's movies collection. Returns lightweight results
    (title/description/year/thumbnail) — the actual playable file URL is
    resolved separately, only for items actually selected to import, via
    archive_org_get_video_url()."""
    fields = 'identifier,title,description,year,downloads'
    q = f'mediatype:(movies) AND {query}' if query.strip() else 'mediatype:(movies) AND collection:(feature_films)'
    params = urllib.parse.urlencode({
        'q': q, 'fl[]': fields, 'rows': max(per_page, 3),
        'output': 'json', 'sort[]': 'downloads desc',
    }, doseq=True)
    data, err = _get_json_verbose(f'https://archive.org/advancedsearch.php?{params}')
    if err:
        return [], err
    docs = (data.get('response') or {}).get('docs', [])
    out = []
    for d in docs:
        identifier = d.get('identifier', '')
        if not identifier:
            continue
        desc = d.get('description', '')
        if isinstance(desc, list):
            desc = ' '.join(desc)
        out.append({
            'source': 'Archive.org',
            'external_id': identifier,
            'title': d.get('title', identifier),
            'description': (desc or '')[:500],
            'release_year': d.get('year', ''),
            'cover': f'https://archive.org/services/img/{identifier}',
            'detail_url': f'https://archive.org/details/{identifier}',
        })
    return out, None


def archive_org_get_video_url(identifier):
    """Resolves an Archive.org identifier to a direct playable mp4 URL by
    reading its file manifest — only called at import time, once per
    selected item, to avoid a metadata call for every search result."""
    data = _get_json(f'https://archive.org/metadata/{identifier}')
    if not data:
        return ''
    files = data.get('files', [])
    # Prefer a real mp4; Archive.org items often also bundle .ogv/.mpeg —
    # skip those in favor of the most universally-playable format.
    mp4s = [f for f in files if (f.get('name', '').lower().endswith('.mp4'))]
    if not mp4s:
        return ''
    # Larger encodes tend to be the "real" transfer rather than a thumbnail
    # clip; fall back to the first if size is missing.
    mp4s.sort(key=lambda f: int(f.get('size') or 0), reverse=True)
    best = mp4s[0]
    return f'https://archive.org/download/{identifier}/{best["name"]}'


# ── Jamendo — full-length, streamable, Creative-Commons-licensed music ──────
# Independent-artist tracks, full length (not 30-second previews like
# iTunes), free with a client_id (free to register at jamendo.com).

def _jamendo_client_id():
    from core.models import SiteSettings
    try:
        return SiteSettings.objects.get(key='jamendo_client_id').value.strip()
    except SiteSettings.DoesNotExist:
        return ''


def jamendo_configured():
    return bool(_jamendo_client_id())


def jamendo_search(query, per_page=20):
    client_id = _jamendo_client_id()
    if not client_id:
        return [], 'No Jamendo client_id saved yet.'
    params = {
        'client_id': client_id, 'format': 'json', 'limit': max(per_page, 3),
        'include': 'musicinfo', 'audioformat': 'mp32',
    }
    if query.strip():
        params['search'] = query.strip()
    else:
        params['order'] = 'popularity_total'
    q = urllib.parse.urlencode(params)
    data, err = _get_json_verbose(f'https://api.jamendo.com/v3.0/tracks/?{q}')
    if err:
        return [], err
    out = []
    for t in data.get('results', []):
        out.append({
            'source': 'Jamendo',
            'external_id': str(t.get('id', '')),
            'title': t.get('name', 'Untitled'),
            'artist': t.get('artist_name', 'Unknown Artist'),
            'preview_url': t.get('audio', ''),   # full-length stream, not a 30s preview
            'cover': t.get('image', ''),
            'duration': t.get('duration', 0),
            'genre': (t.get('musicinfo') or {}).get('tags', {}).get('genres', [''])[0] if t.get('musicinfo') else '',
            'release_year': (t.get('releasedate') or '')[:4],
        })
    return out, None


# ── YouTube — real embedded Shorts via YouTube's own official player ────────
# Nothing is downloaded or rehosted here — only the video ID + metadata are
# stored, and playback always happens through YouTube's own embedded
# player (same as the existing is_youtube handling in shorts/models.py),
# which is exactly what the YouTube Data API is licensed for.

def _youtube_api_key():
    from core.models import SiteSettings
    try:
        return SiteSettings.objects.get(key='youtube_api_key').value.strip()
    except SiteSettings.DoesNotExist:
        return ''


def youtube_configured():
    return bool(_youtube_api_key())


def youtube_shorts_search(query, per_page=20):
    key = _youtube_api_key()
    if not key:
        return [], 'No YouTube API key saved yet.'
    params = urllib.parse.urlencode({
        'part': 'snippet', 'q': query.strip() or 'comedy skits',
        'type': 'video', 'videoDuration': 'short',  # under 4 minutes — closest official filter to "Shorts"
        'maxResults': max(per_page, 3), 'safeSearch': 'moderate', 'key': key,
    })
    data, err = _get_json_verbose(f'https://www.googleapis.com/youtube/v3/search?{params}')
    if err:
        return [], err
    out = []
    for item in data.get('items', []):
        vid = (item.get('id') or {}).get('videoId', '')
        snippet = item.get('snippet') or {}
        if not vid:
            continue
        thumbs = snippet.get('thumbnails') or {}
        thumb = (thumbs.get('medium') or thumbs.get('default') or {}).get('url', '')
        out.append({
            'source': 'YouTube',
            'external_id': vid,
            'video_url': f'https://www.youtube.com/watch?v={vid}',
            'title': snippet.get('title', 'Untitled'),
            'thumbnail_url': thumb,
            'photographer': snippet.get('channelTitle', 'Unknown'),
            'duration': 0,  # YouTube embed handles its own playback/duration
        })
    return out, None
# auto-fill Track.lyrics_lrc when importing via Fetch Music.

def lrclib_get_lyrics(track_name, artist_name, album_name='', duration=None):
    """Best-effort synced (LRC) lyrics lookup. Returns '' if nothing found —
    never raises, so a missing/unreachable lyrics source can't break an
    import."""
    if not track_name or not artist_name:
        return ''
    params = {'track_name': track_name, 'artist_name': artist_name}
    if album_name:
        params['album_name'] = album_name
    if duration:
        params['duration'] = int(duration)
    q = urllib.parse.urlencode(params)
    data = _get_json(f'https://lrclib.net/api/get?{q}', headers={'User-Agent': 'Bazillin/1.0'})
    if data and data.get('syncedLyrics'):
        return data['syncedLyrics']

    # Exact lookup failed (wrong duration, slight title mismatch, etc.) —
    # fall back to fuzzy search and take the first hit with synced lyrics.
    try:
        sq = urllib.parse.urlencode({'q': f'{track_name} {artist_name}'})
        results = _get_json(f'https://lrclib.net/api/search?{sq}', headers={'User-Agent': 'Bazillin/1.0'})
        if results:
            for r in results:
                if r.get('syncedLyrics'):
                    return r['syncedLyrics']
    except Exception:
        pass
    return ''


# ── OpenSubtitles — real subtitle files, no AI involved ──────────────────────
# The same database VLC/most media players pull from. Needs a free API key
# (register at opensubtitles.com -> API Consumers). Whitelisted on
# PythonAnywhere's free tier, unlike Jamendo.

def _opensubtitles_key():
    from core.models import SiteSettings
    try:
        return SiteSettings.objects.get(key='opensubtitles_api_key').value.strip()
    except SiteSettings.DoesNotExist:
        return ''


def opensubtitles_configured():
    return bool(_opensubtitles_key())


def opensubtitles_fetch(title, year=None, language='en'):
    """Real subtitle files — pulled straight from OpenSubtitles' database,
    the same source VLC and most media players use, no AI involved at all.
    Two-step: search for a matching subtitle, then resolve the actual
    .srt file content. Returns (srt_text, error) — srt_text is None with
    error=None when nothing matched (not a failure, just no result)."""
    key = _opensubtitles_key()
    if not key:
        return None, 'No OpenSubtitles API key saved yet.'

    headers = {
        'Api-Key': key,
        'User-Agent': 'NEXUS v1.0',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    params = {'languages': language, 'query': title.strip().lower()}
    if year:
        params['year'] = str(year)
    # OpenSubtitles asks for GET params sorted alphabetically to avoid an
    # extra redirect round-trip.
    q = urllib.parse.urlencode(dict(sorted(params.items())))
    search_data, err = _get_json_verbose(f'https://api.opensubtitles.com/api/v1/subtitles?{q}', headers=headers)
    if err:
        return None, err
    results = (search_data or {}).get('data', [])
    if not results:
        return None, None

    # Prefer the most-downloaded match — best signal for "the right one"
    # when a title has several community-submitted subtitle files.
    results.sort(key=lambda r: (r.get('attributes') or {}).get('download_count', 0), reverse=True)
    files = (results[0].get('attributes') or {}).get('files') or []
    if not files:
        return None, None
    file_id = files[0].get('file_id')
    if not file_id:
        return None, None

    try:
        body = json.dumps({'file_id': file_id}).encode()
        req = urllib.request.Request('https://api.opensubtitles.com/api/v1/download', data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            download_data = json.loads(resp.read().decode('utf-8', errors='ignore'))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, f'HTTP {e.code} — the saved OpenSubtitles API key is likely invalid.'
        if e.code == 406:
            return None, 'Daily download limit reached for this API key (OpenSubtitles caps free-tier downloads per day).'
        return None, f'HTTP {e.code} error requesting the subtitle download link.'
    except Exception as e:
        return None, f'{type(e).__name__}: {str(e)[:150]}'

    link = download_data.get('link')
    if not link:
        return None, download_data.get('message') or 'No download link in the response.'

    try:
        req = urllib.request.Request(link, headers={'User-Agent': 'NEXUS v1.0'})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            srt_text = resp.read().decode('utf-8', errors='replace')
        return srt_text, None
    except Exception as e:
        return None, f'Downloaded link failed: {e}'


# ── Archive.org audio — another free, full-length music source ──────────────
# Same domain as the movies integration above (already whitelisted on
# PythonAnywhere free tier), so this works even where Jamendo can't.
# Covers netlabels, live concert recordings, and Creative-Commons releases
# — real full tracks, not previews.

def archive_org_audio_search(query, per_page=20):
    q = f'mediatype:(audio) AND {query}' if query.strip() else 'mediatype:(audio) AND collection:(netlabels)'
    params = urllib.parse.urlencode({
        'q': q, 'fl[]': ['identifier', 'title', 'creator', 'year', 'downloads'],
        'rows': max(per_page, 3), 'output': 'json', 'sort[]': 'downloads desc',
    }, doseq=True)
    data, err = _get_json_verbose(f'https://archive.org/advancedsearch.php?{params}')
    if err:
        return [], err
    docs = (data.get('response') or {}).get('docs', [])
    out = []
    for d in docs:
        identifier = d.get('identifier', '')
        if not identifier:
            continue
        creator = d.get('creator', 'Unknown Artist')
        if isinstance(creator, list):
            creator = creator[0] if creator else 'Unknown Artist'
        out.append({
            'source': 'Archive.org',
            'external_id': identifier,
            'title': d.get('title', identifier),
            'artist': creator,
            'cover': f'https://archive.org/services/img/{identifier}',
            'release_year': d.get('year', ''),
            'genre': '',
            # Resolved to a real playable file only for selected imports,
            # same lazy pattern as the movies integration.
        })
    return out, None


def archive_org_audio_get_url(identifier):
    """Resolves an Archive.org audio identifier to a direct playable file
    URL — only called at import time for selected items."""
    data = _get_json(f'https://archive.org/metadata/{identifier}')
    if not data:
        return ''
    files = data.get('files', [])
    audio_exts = ('.mp3', '.ogg', '.m4a')
    candidates = [f for f in files if f.get('name', '').lower().endswith(audio_exts)]
    if not candidates:
        return ''
    # Prefer mp3 for universal browser playback
    mp3s = [f for f in candidates if f['name'].lower().endswith('.mp3')]
    best = (mp3s or candidates)[0]
    return f'https://archive.org/download/{identifier}/{best["name"]}'


# ── lyrics.ovh — plain-text lyrics fallback, whitelisted on PythonAnywhere ──
# lrclib.net (the synced/timed lyrics source above) is NOT on PythonAnywhere's
# free-tier allowlist. This is a fallback for that specific case: not
# timed/synced, just plain lyrics text, but it means something still shows
# instead of nothing when lrclib is unreachable.

def lyricsovh_get_lyrics(title, artist):
    try:
        import urllib.parse as _up
        url = f'https://api.lyrics.ovh/v1/{_up.quote(artist)}/{_up.quote(title)}'
        data = _get_json(url, timeout=8)
        if data and data.get('lyrics'):
            return data['lyrics'].strip()
    except Exception:
        pass
    return ''
