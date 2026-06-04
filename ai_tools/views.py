"""
ai_tools/views.py
-----------------
All AI endpoints.  API keys come from DB via core.utils.get_ai_key().
Falls back gracefully to demo mode when no key is configured.
"""
import json
import urllib.request
import urllib.error
import logging

from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings

from core.models import AILog, AIGeneratedImage
from core.utils import get_ai_key

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _post_json(url, payload, headers):
    """POST JSON and return parsed response dict, or raise ValueError."""
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise ValueError(f'HTTP {e.code}: {body}')
    except Exception as e:
        raise ValueError(str(e))


# ── views ──────────────────────────────────────────────────────────────────────

def ai_studio(request):
    user_images = []
    if request.user.is_authenticated:
        user_images = AIGeneratedImage.objects.filter(
            user=request.user
        ).order_by('-created_at')[:20]

    # Tell the template whether a real key is configured
    has_image_key = bool(get_ai_key('openai') or get_ai_key('stability'))
    return render(request, 'ai/studio.html', {
        'user_images':   user_images,
        'has_image_key': has_image_key,
    })


@require_POST
def generate_image(request):
    prompt = request.POST.get('prompt', '').strip()
    if not prompt:
        return JsonResponse({'error': 'Prompt is required.'}, status=400)

    user = request.user if request.user.is_authenticated else None

    # ── Try OpenAI DALL-E ────────────────────────────────────────────────────
    openai_key = get_ai_key('openai')
    if openai_key:
        try:
            result = _post_json(
                'https://api.openai.com/v1/images/generations',
                payload={
                    'model':  'dall-e-3',
                    'prompt': prompt,
                    'n':      1,
                    'size':   '1024x1024',
                },
                headers={
                    'Content-Type':  'application/json',
                    'Authorization': f'Bearer {openai_key}',
                },
            )
            image_url = result['data'][0]['url']
            img_obj   = AIGeneratedImage.objects.create(
                user=user, prompt=prompt, image_url=image_url
            )
            AILog.objects.create(
                action='image_generation', input_data=prompt,
                output_data=image_url, model_used='dall-e-3', user=user,
            )
            return JsonResponse({'success': True, 'image_url': image_url, 'id': img_obj.pk})

        except ValueError as e:
            logger.warning('OpenAI image generation failed: %s', e)
            # Try Stability as fallback before returning error
            stability_key = get_ai_key('stability')
            if not stability_key:
                return JsonResponse({'error': f'Image generation failed: {e}'}, status=502)

    # ── Try Stability AI ─────────────────────────────────────────────────────
    stability_key = get_ai_key('stability')
    if stability_key:
        try:
            result = _post_json(
                'https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image',
                payload={
                    'text_prompts': [{'text': prompt, 'weight': 1}],
                    'cfg_scale':    7,
                    'height':       1024,
                    'width':        1024,
                    'samples':      1,
                    'steps':        30,
                },
                headers={
                    'Content-Type':  'application/json',
                    'Authorization': f'Bearer {stability_key}',
                    'Accept':        'application/json',
                },
            )
            import base64, os, uuid
            from django.core.files.base import ContentFile
            b64 = result['artifacts'][0]['base64']
            img_data = base64.b64decode(b64)
            fname = f'stability_{uuid.uuid4().hex[:8]}.png'
            img_obj = AIGeneratedImage(user=user, prompt=prompt, image_url='')
            img_obj.local_file.save(fname, ContentFile(img_data), save=False)
            img_obj.image_url = request.build_absolute_uri(img_obj.local_file.url)
            img_obj.save()
            AILog.objects.create(
                action='image_generation', input_data=prompt,
                output_data=img_obj.image_url,
                model_used='stable-diffusion-xl', user=user,
            )
            return JsonResponse({'success': True, 'image_url': img_obj.image_url, 'id': img_obj.pk})

        except ValueError as e:
            logger.warning('Stability AI failed: %s', e)
            return JsonResponse({'error': f'Image generation failed: {e}'}, status=502)

    # ── Demo mode (no key configured) ────────────────────────────────────────
    demo_url = f'https://picsum.photos/seed/{abs(hash(prompt)) % 9999}/1024/1024'
    return JsonResponse({
        'success':   True,
        'image_url': demo_url,
        'prompt':    prompt,
        'demo':      True,
        'message':   'Demo mode – configure an API key in Admin → AI Settings for real generation.',
    })


@require_POST
def ai_assistant(request):
    message = request.POST.get('message', '').strip()
    if not message:
        return JsonResponse({'reply': 'Please type a message.'})

    history_raw = request.POST.get('history', '[]')
    try:
        history_data = json.loads(history_raw)
        if not isinstance(history_data, list):
            history_data = []
    except Exception:
        history_data = []

    user = request.user if request.user.is_authenticated else None

    # ── System prompt (editable via DB if desired) ───────────────────────────
    from core.models import SiteSettings
    try:
        system_prompt = SiteSettings.objects.get(key='ai_system_prompt').value
    except SiteSettings.DoesNotExist:
        system_prompt = (
            'You are NEXUS AI Assistant, a helpful guide for a media platform '
            'featuring images, videos, music, blogs and AI tools. Be concise, '
            'helpful and friendly.'
        )

    # ── Try Anthropic Claude ─────────────────────────────────────────────────
    anthropic_key = get_ai_key('anthropic')
    if anthropic_key:
        messages = history_data[-10:] + [{'role': 'user', 'content': message}]
        try:
            result = _post_json(
                'https://api.anthropic.com/v1/messages',
                payload={
                    'model':      'claude-sonnet-4-20250514',
                    'max_tokens': 1024,
                    'system':     system_prompt,
                    'messages':   messages,
                },
                headers={
                    'Content-Type':      'application/json',
                    'x-api-key':         anthropic_key,
                    'anthropic-version': '2023-06-01',
                },
            )
            reply = result['content'][0]['text']
            AILog.objects.create(
                action='chat', input_data=message,
                output_data=reply, model_used='claude-sonnet', user=user,
            )
            return JsonResponse({'reply': reply})

        except ValueError as e:
            logger.warning('Anthropic chat failed: %s', e)
            return JsonResponse({
                'reply': (
                    '⚠️ AI assistant is temporarily unavailable. '
                    f'Error: {str(e)[:120]}'
                )
            })

    # ── Demo fallback ─────────────────────────────────────────────────────────
    demo_replies = {
        'hello':    "Hello! I'm NEXUS AI. How can I help you today?",
        'hi':       "Hey there! Ask me anything about the platform.",
        'help':     "I can help you find content, generate images, and navigate the platform!",
        'image':    "Head to AI Studio (✨ in the nav) to generate images with AI!",
        'download': "You need to be logged in to download content. Free content is available to all members.",
        'upload':   "Creators can upload content from their dashboard after registering as a creator.",
    }
    msg_lower = message.lower()
    reply = next(
        (v for k, v in demo_replies.items() if k in msg_lower),
        (
            f'I understand you\'re asking about "{message[:60]}". '
            'Configure an Anthropic API key in Admin → AI Settings for full AI chat.'
        )
    )
    return JsonResponse({'reply': reply, 'demo': True})


@require_POST
def moderate_content(request):
    """AI-powered moderation. Uses Claude if available, else keyword fallback."""
    content_id = request.POST.get('content_id')
    from content.models import Content
    obj = get_object_or_404(Content, pk=content_id)

    score = 0.85
    flags = {}

    # Keyword scan (always runs)
    bad_words = ['spam', 'xxx', 'hack', 'scam', 'malware', 'phishing']
    text = f'{obj.title} {obj.description}'.lower()
    for word in bad_words:
        if word in text:
            flags[word] = True
            score -= 0.2

    # Claude moderation (if key available)
    anthropic_key = get_ai_key('anthropic')
    if anthropic_key and obj.description:
        try:
            result = _post_json(
                'https://api.anthropic.com/v1/messages',
                payload={
                    'model':      'claude-haiku-4-5-20251001',
                    'max_tokens': 200,
                    'messages': [{
                        'role': 'user',
                        'content': (
                            f'Rate this content for a family-friendly media platform. '
                            f'Title: {obj.title}. Description: {obj.description[:300]}. '
                            'Reply ONLY with JSON: {"safe": true/false, "score": 0.0-1.0, "reason": "..."}'
                        ),
                    }],
                },
                headers={
                    'Content-Type':      'application/json',
                    'x-api-key':         anthropic_key,
                    'anthropic-version': '2023-06-01',
                },
            )
            raw = result['content'][0]['text'].strip()
            # strip markdown fences if present
            if raw.startswith('```'):
                raw = raw.split('```')[1].lstrip('json').strip()
            ai_result = json.loads(raw)
            score = float(ai_result.get('score', score))
            if not ai_result.get('safe', True):
                flags['ai_unsafe'] = ai_result.get('reason', 'Flagged by AI')
        except Exception as e:
            logger.warning('Claude moderation failed: %s', e)

    obj.ai_score    = max(0.0, min(1.0, score))
    obj.ai_flags    = flags
    obj.ai_reviewed = True
    obj.status      = 'approved' if obj.ai_score >= 0.5 and not flags else 'rejected'
    obj.save()

    return JsonResponse({'score': obj.ai_score, 'flags': flags, 'status': obj.status})
