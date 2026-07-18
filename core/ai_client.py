"""
core/ai_client.py
------------------
Single place that knows how to talk to every configured AI provider
(OpenAI, Anthropic, Gemini, OpenRouter, Stability). Every admin-configured
provider goes through this file, so fixing a bug here fixes it everywhere
it's used (AI Studio image generation, AI Assistant chat, content
moderation, AI subtitle summaries) instead of N separate copies of the
same request-building code.
"""
import json
import logging
import urllib.request
import urllib.error

from core.utils import get_ai_key, get_ai_model

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {
    'anthropic':  'claude-sonnet-4-5',
    'openai':     'gpt-4o-mini',
    'gemini':     'gemini-2.5-flash',
    'openrouter': 'openai/gpt-4o-mini',
}
DEFAULT_IMAGE_MODELS = {
    'openai':    'dall-e-3',
    'gemini':    'gemini-2.5-flash-image',
    'stability': 'stable-diffusion-xl-1024-v1-0',
}

TEXT_PROVIDERS = ['anthropic', 'gemini', 'openrouter', 'openai']
IMAGE_PROVIDERS = ['openai', 'gemini', 'stability']


def _post_json(url, payload, headers, timeout=60):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
        except Exception:
            body = ''
        return None, f'HTTP {e.code}: {body[:400]}'
    except urllib.error.URLError as e:
        return None, f'Connection failed: {e.reason}'
    except Exception as e:
        return None, str(e)


def _configured_providers(pool):
    """Providers from `pool` that are active + have a saved key, in order."""
    from core.models import AIProviderSettings
    active = {p.provider for p in AIProviderSettings.objects.filter(is_active=True) if p.api_key}
    return [p for p in pool if p in active]


# ── Text completion ─────────────────────────────────────────────────────────

def _text_anthropic(system, message, history=None):
    key = get_ai_key('anthropic')
    model = get_ai_model('anthropic', DEFAULT_MODELS['anthropic'])
    messages = (history or [])[-10:] + [{'role': 'user', 'content': message}]
    result, err = _post_json(
        'https://api.anthropic.com/v1/messages',
        {'model': model, 'max_tokens': 1024, 'system': system, 'messages': messages},
        {'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01'},
    )
    if err:
        return None, err
    try:
        return result['content'][0]['text'], None
    except (KeyError, IndexError):
        return None, f'Unexpected response shape: {result}'


def _text_openai(system, message, history=None):
    key = get_ai_key('openai')
    model = get_ai_model('openai', DEFAULT_MODELS['openai'])
    messages = [{'role': 'system', 'content': system}] + (history or [])[-10:] + [{'role': 'user', 'content': message}]
    result, err = _post_json(
        'https://api.openai.com/v1/chat/completions',
        {'model': model, 'messages': messages},
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
    )
    if err:
        return None, err
    try:
        return result['choices'][0]['message']['content'], None
    except (KeyError, IndexError):
        return None, f'Unexpected response shape: {result}'


def _text_openrouter(system, message, history=None):
    key = get_ai_key('openrouter')
    model = get_ai_model('openrouter', DEFAULT_MODELS['openrouter'])
    messages = [{'role': 'system', 'content': system}] + (history or [])[-10:] + [{'role': 'user', 'content': message}]
    result, err = _post_json(
        'https://openrouter.ai/api/v1/chat/completions',
        {'model': model, 'messages': messages},
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
    )
    if err:
        return None, err
    try:
        return result['choices'][0]['message']['content'], None
    except (KeyError, IndexError):
        return None, f'Unexpected response shape: {result}'


def _text_gemini(system, message, history=None):
    key = get_ai_key('gemini')
    model = get_ai_model('gemini', DEFAULT_MODELS['gemini'])
    contents = []
    for h in (history or [])[-10:]:
        role = 'model' if h.get('role') == 'assistant' else 'user'
        contents.append({'role': role, 'parts': [{'text': h.get('content', '')}]})
    contents.append({'role': 'user', 'parts': [{'text': message}]})
    payload = {'contents': contents}
    if system:
        payload['system_instruction'] = {'parts': [{'text': system}]}
    result, err = _post_json(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        payload,
        {'Content-Type': 'application/json', 'x-goog-api-key': key},
    )
    if err:
        return None, err
    try:
        parts = result['candidates'][0]['content']['parts']
        text = ''.join(p.get('text', '') for p in parts)
        if not text:
            return None, f'No text in response: {result}'
        return text, None
    except (KeyError, IndexError):
        return None, f'Unexpected response shape: {result}'


_TEXT_FN = {
    'anthropic': _text_anthropic,
    'openai': _text_openai,
    'gemini': _text_gemini,
    'openrouter': _text_openrouter,
}


def generate_text(system, message, history=None, prefer=None):
    """Try text-capable providers in priority order, return
    (text, error, provider_used). `prefer` jumps one provider to the
    front of the line if it's configured."""
    pool = list(TEXT_PROVIDERS)
    if prefer and prefer in pool:
        pool.remove(prefer)
        pool.insert(0, prefer)
    configured = _configured_providers(pool)
    if not configured:
        return None, 'No AI text provider is configured yet. Add an API key in Admin -> Settings -> AI.', None
    errors = []
    for provider in configured:
        text, err = _TEXT_FN[provider](system, message, history)
        if text:
            return text, None, provider
        errors.append(f'{provider}: {err}')
    return None, ' | '.join(errors), None


# ── Image generation ─────────────────────────────────────────────────────────

def _image_openai(prompt):
    key = get_ai_key('openai')
    model = get_ai_model('openai', DEFAULT_IMAGE_MODELS['openai'])
    result, err = _post_json(
        'https://api.openai.com/v1/images/generations',
        {'model': model, 'prompt': prompt, 'n': 1, 'size': '1024x1024'},
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
    )
    if err:
        return None, None, err
    try:
        return result['data'][0]['url'], None, None
    except (KeyError, IndexError):
        return None, None, f'Unexpected response shape: {result}'


def _image_gemini(prompt):
    key = get_ai_key('gemini')
    model = get_ai_model('gemini', DEFAULT_IMAGE_MODELS['gemini'])
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseModalities': ['IMAGE']},
    }
    result, err = _post_json(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        payload,
        {'Content-Type': 'application/json', 'x-goog-api-key': key},
        timeout=90,
    )
    if err:
        return None, None, err
    try:
        parts = result['candidates'][0]['content']['parts']
        for p in parts:
            inline = p.get('inlineData') or p.get('inline_data')
            if inline and inline.get('data'):
                return None, inline['data'], None
        return None, None, f'No image in response: {result}'
    except (KeyError, IndexError):
        return None, None, f'Unexpected response shape: {result}'


def _image_stability(prompt):
    key = get_ai_key('stability')
    model = get_ai_model('stability', DEFAULT_IMAGE_MODELS['stability'])
    result, err = _post_json(
        f'https://api.stability.ai/v1/generation/{model}/text-to-image',
        {'text_prompts': [{'text': prompt, 'weight': 1}], 'cfg_scale': 7, 'height': 1024, 'width': 1024, 'samples': 1, 'steps': 30},
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
        timeout=90,
    )
    if err:
        return None, None, err
    try:
        return None, result['artifacts'][0]['base64'], None
    except (KeyError, IndexError):
        return None, None, f'Unexpected response shape: {result}'


_IMAGE_FN = {
    'openai': _image_openai,
    'gemini': _image_gemini,
    'stability': _image_stability,
}


def generate_image(prompt, prefer=None):
    """Try image-capable providers in priority order. Returns
    (image_url, image_base64, error, provider_used) — exactly one of
    image_url/image_base64 will be set on success."""
    pool = list(IMAGE_PROVIDERS)
    if prefer and prefer in pool:
        pool.remove(prefer)
        pool.insert(0, prefer)
    configured = _configured_providers(pool)
    if not configured:
        return None, None, 'No AI image provider is configured yet. Add an API key in Admin -> Settings -> AI.', None
    errors = []
    for provider in configured:
        url, b64, err = _IMAGE_FN[provider](prompt)
        if url or b64:
            return url, b64, None, provider
        errors.append(f'{provider}: {err}')
    return None, None, ' | '.join(errors), None


# ── Connection testing (surfaces the real error in admin) ───────────────────

def _ping_stability(key):
    req = urllib.request.Request(
        'https://api.stability.ai/v1/user/account',
        headers={'Authorization': f'Bearer {key}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return 'ok', None
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        return None, f'HTTP {e.code}: {body}'
    except Exception as e:
        return None, str(e)


def test_provider(provider):
    """Make the cheapest possible real call to confirm a saved key/model
    actually works, and return the exact error text on failure so admin
    isn't left guessing why a provider 'doesn't work'."""
    key = get_ai_key(provider)
    if not key:
        return False, 'No API key saved for this provider yet.'

    ping_system = 'Reply with exactly one word.'
    ping_message = 'Say "pong".'

    try:
        if provider == 'anthropic':
            text, err = _text_anthropic(ping_system, ping_message)
        elif provider == 'openai':
            text, err = _text_openai(ping_system, ping_message)
        elif provider == 'gemini':
            text, err = _text_gemini(ping_system, ping_message)
        elif provider == 'openrouter':
            text, err = _text_openrouter(ping_system, ping_message)
        elif provider == 'stability':
            text, err = _ping_stability(key)
        else:
            return False, f'Unknown provider "{provider}".'
    except Exception as e:
        return False, f'Unexpected error: {e}'

    if err:
        return False, err
    return True, f'Connected successfully. Model replied: {str(text)[:80]}'
