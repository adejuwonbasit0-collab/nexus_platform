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
    'topsongs' (trending) or 'newmusic' (latest releases)."""
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
            link = ''
            for l in e.get('link', []):
                if isinstance(l, dict) and l.get('attributes', {}).get('rel') != 'alternate':
                    continue
            itunes_id = e.get('id', {}).get('attributes', {}).get('im:id', '')
            out.append({
                'source': 'iTunes', 'external_id': itunes_id,
                'title': title, 'artist': artist, 'album': '',
                'cover': cover.replace('100x100', '600x600') if cover else '',
                'preview_url': '', 'genre': e.get('category', {}).get('attributes', {}).get('label', ''),
                'release_year': '',
            })
        except Exception:
            continue
    # Charts don't include a 30s preview URL — enrich the first page via search
    # lookup so tracks are actually playable once imported.
    return _enrich_with_lookup(out)


def _enrich_with_lookup(items):
    enriched = []
    for it in items[:50]:
        found = None
        try:
            q = urllib.parse.urlencode({'term': f"{it['artist']} {it['title']}", 'entity': 'song', 'limit': 1})
            data = _get_json(f'https://itunes.apple.com/search?{q}', timeout=6)
            if data and data.get('results'):
                found = data['results'][0]
        except Exception:
            found = None
        if found:
            it['preview_url'] = found.get('previewUrl', '')
            it['external_id'] = str(found.get('trackId', it.get('external_id', '')))
            it['album'] = found.get('collectionName', '')
            it['release_year'] = (found.get('releaseDate') or '')[:4]
            if found.get('artworkUrl100'):
                it['cover'] = found['artworkUrl100'].replace('100x100', '600x600')
        enriched.append(it)
    return enriched


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
