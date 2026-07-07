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
            title = e['im:name']['label']
            artist = e['im:artist']['label']
            images = e.get('im:image', [])
            cover = images[-1]['label'] if images else ''
            if cover:
                cover = cover.replace('100x100', '600x600').replace('170x170', '600x600')
            itunes_id = e.get('id', {}).get('attributes', {}).get('im:id', '')
            out.append({
                'source': 'iTunes', 'external_id': itunes_id,
                'title': title, 'artist': artist, 'album': '',
                'cover': cover, 'preview_url': '',
                'genre': e.get('category', {}).get('attributes', {}).get('label', ''),
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
        'title': r.get('trackName', ''),
        'artist': r.get('artistName', ''),
        'album': r.get('collectionName', ''),
        'cover': (r.get('artworkUrl100') or '').replace('100x100', '600x600'),
        'preview_url': r.get('previewUrl', ''),
        'genre': r.get('primaryGenreName', ''),
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


# ── Lyrics: LRCLIB ────────────────────────────────────────────────────────────
# Free, keyless, crowd-sourced synced-lyrics database (lrclib.net). Used to
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
