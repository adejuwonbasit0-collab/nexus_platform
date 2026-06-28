"""
Music identification service.

Layers (tried in order, first hit wins):
1. Whisper transcription → DB text search  (own library, requires OpenAI key)
2. AudD.io audio fingerprinting            (global, free tier, no key needed)
3. Claude AI description                   (own library + AI reasoning)
4. Duration + keyword fallback             (own library, no API)
"""
import json
import math
import urllib.request
import urllib.error
import io


# ── Layer 1: Whisper transcription ────────────────────────────────────────────

def whisper_transcribe(audio_bytes: bytes, mime: str = 'audio/webm') -> str:
    """Send audio bytes to OpenAI Whisper, return the transcribed text or ''."""
    from core.utils import get_ai_key
    key = get_ai_key('openai')
    if not key:
        return ''

    import base64, tempfile, os

    # Write to a temp file — Whisper API needs a file object with a .name
    suffix = '.webm'
    if 'mp3' in mime: suffix = '.mp3'
    elif 'mp4' in mime or 'mpeg' in mime: suffix = '.mp4'
    elif 'ogg' in mime: suffix = '.ogg'
    elif 'wav' in mime: suffix = '.wav'

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(audio_bytes)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    try:
        # Use the openai SDK
        from openai import OpenAI
        client = OpenAI(api_key=key)
        with open(tmp_path, 'rb') as f:
            transcript = client.audio.transcriptions.create(
                model='whisper-1',
                file=f,
                response_format='text',
            )
        return str(transcript).strip()
    except Exception as e:
        return ''
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── Layer 2: AudD.io global fingerprinting ────────────────────────────────────

def audd_identify(audio_bytes: bytes) -> dict | None:
    """
    Send audio to AudD.io for global fingerprint matching.
    Free tier: 300 requests/month with no API key.
    Returns a dict with title/artist/album or None.
    """
    import base64, urllib.parse

    b64 = base64.b64encode(audio_bytes).decode()

    data = urllib.parse.urlencode({
        'audio':  b64,
        'return': 'apple_music,spotify',
        'api_token': 'test',  # 'test' gives 10 free requests/day without account
    }).encode()

    try:
        req = urllib.request.Request(
            'https://api.audd.io/',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        if result.get('status') == 'success' and result.get('result'):
            r = result['result']
            return {
                'title':   r.get('title', ''),
                'artist':  r.get('artist', ''),
                'album':   r.get('album', ''),
                'release_date': r.get('release_date', ''),
                'apple_music': r.get('apple_music', {}),
                'spotify': r.get('spotify', {}),
                'cover':   (r.get('apple_music', {}).get('artwork', {}).get('url', '')
                            or '').replace('{w}', '300').replace('{h}', '300'),
            }
    except Exception:
        pass
    return None


# ── Layer 3: Claude AI + own library ─────────────────────────────────────────

def claude_identify(transcript: str, db_tracks: list) -> dict | None:
    """Ask Claude to match a transcribed text against a list of track titles."""
    from core.utils import get_ai_key
    key = get_ai_key('anthropic')
    if not key or not transcript or not db_tracks:
        return None

    track_list = '\n'.join(
        f'{i+1}. "{t["title"]}" by {t["artist"]}'
        for i, t in enumerate(db_tracks[:40])
    )
    prompt = (
        f'A user is trying to identify a song. Here is a partial transcript '
        f'of what was heard:\n\n"{transcript}"\n\n'
        f'Here are the tracks available in this platform\'s library:\n{track_list}\n\n'
        f'Which track number best matches the transcript? '
        f'Reply with ONLY the number, or "0" if none match.'
    )

    try:
        payload = json.dumps({
            'model': 'claude-sonnet-4-6',
            'max_tokens': 10,
            'messages': [{'role': 'user', 'content': prompt}],
        }).encode()
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages', data=payload,
            headers={'Content-Type': 'application/json',
                     'x-api-key': key, 'anthropic-version': '2023-06-01'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            r = json.loads(resp.read())
        idx_str = r['content'][0]['text'].strip()
        idx = int(idx_str) - 1
        if 0 <= idx < len(db_tracks):
            return db_tracks[idx]
    except Exception:
        pass
    return None


# ── Layer 4: Duration + keyword fallback ──────────────────────────────────────

def db_search(hint_title='', hint_artist='', hint_duration='') -> list:
    """Search own DB by text and/or duration."""
    from music.models import Track
    from django.db.models import Q

    candidates = []

    if hint_title or hint_artist:
        qs = Track.objects.filter(is_published=True).select_related('artist', 'album')
        q = Q()
        if hint_title:
            q |= Q(title__icontains=hint_title) | Q(artist__name__icontains=hint_title)
        if hint_artist:
            q |= Q(artist__name__icontains=hint_artist) | Q(title__icontains=hint_artist)
        candidates = list(qs.filter(q)[:10])

    if not candidates and hint_duration:
        try:
            d = float(hint_duration)
            candidates = list(Track.objects.filter(
                is_published=True,
                duration__gte=math.floor(d) - 4,
                duration__lte=math.ceil(d) + 4,
            ).select_related('artist', 'album')[:10])
        except (ValueError, TypeError):
            pass

    return candidates


def serialise_track(t) -> dict:
    return {
        'pk':     t.pk,
        'title':  t.title,
        'artist': t.artist.name if t.artist else '',
        'slug':   t.slug,
        'cover':  (t.cover_image.url if t.cover_image
                   else (t.album.cover_image.url if t.album and t.album.cover_image else '')),
        'duration': t.duration,
        'url':    t.playable_url or '',
        'in_library': True,
    }
