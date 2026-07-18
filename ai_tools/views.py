"""
ai_tools/views.py
-----------------
All AI endpoints. Every provider call goes through core.ai_client, which
reads admin-configured keys from the DB (AIProviderSettings) and tries
providers in priority order, surfacing the real upstream error message
instead of a generic failure. Falls back gracefully to demo mode when no
provider is configured at all.
"""
import json
import logging

from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from core.models import AILog, AIGeneratedImage
from core.utils import get_ai_key
from core import ai_client

logger = logging.getLogger(__name__)


# ── views ──────────────────────────────────────────────────────────────────────

def ai_studio(request):
    user_images = []
    if request.user.is_authenticated:
        user_images = AIGeneratedImage.objects.filter(
            user=request.user
        ).order_by('-created_at')[:20]

    has_image_key = bool(
        get_ai_key('openai') or get_ai_key('gemini') or get_ai_key('stability')
    )
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

    image_url, image_b64, err, provider_used = ai_client.generate_image(prompt)

    if image_url or image_b64:
        if image_url:
            img_obj = AIGeneratedImage.objects.create(user=user, prompt=prompt, image_url=image_url)
        else:
            import base64, uuid
            from django.core.files.base import ContentFile
            img_data = base64.b64decode(image_b64)
            fname = f'{provider_used}_{uuid.uuid4().hex[:8]}.png'
            img_obj = AIGeneratedImage(user=user, prompt=prompt, image_url='')
            img_obj.local_file.save(fname, ContentFile(img_data), save=False)
            img_obj.image_url = request.build_absolute_uri(img_obj.local_file.url)
            img_obj.save()

        AILog.objects.create(
            action='image_generation', input_data=prompt,
            output_data=img_obj.image_url, model_used=provider_used or '', user=user,
        )
        return JsonResponse({'success': True, 'image_url': img_obj.image_url, 'id': img_obj.pk, 'provider': provider_used})

    if err and 'No AI image provider is configured' in err:
        demo_url = f'https://picsum.photos/seed/{abs(hash(prompt)) % 9999}/1024/1024'
        return JsonResponse({
            'success':   True,
            'image_url': demo_url,
            'prompt':    prompt,
            'demo':      True,
            'message':   'Demo mode - configure an API key in Admin -> Settings -> AI for real generation.',
        })

    logger.warning('Image generation failed across all configured providers: %s', err)
    return JsonResponse({'error': f'Image generation failed: {err}'}, status=502)


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

    from core.models import SiteSettings
    try:
        system_prompt = SiteSettings.objects.get(key='ai_system_prompt').value
    except SiteSettings.DoesNotExist:
        system_prompt = (
            'You are NEXUS AI Assistant, a helpful guide for a media platform '
            'featuring images, videos, music, blogs and AI tools. Be concise, '
            'helpful and friendly.'
        )

    reply, err, provider_used = ai_client.generate_text(system_prompt, message, history=history_data)

    if reply:
        AILog.objects.create(
            action='chat', input_data=message,
            output_data=reply, model_used=provider_used or '', user=user,
        )
        return JsonResponse({'reply': reply, 'provider': provider_used})

    if err and 'No AI text provider is configured' in err:
        demo_replies = {
            'hello':    "Hello! I'm NEXUS AI. How can I help you today?",
            'hi':       "Hey there! Ask me anything about the platform.",
            'help':     "I can help you find content, generate images, and navigate the platform!",
            'image':    "Head to AI Studio (✨ in the nav) to generate images with AI!",
            'download': "You need to be logged in to download content. Free content is available to all members.",
            'upload':   "Creators can upload content from their dashboard after registering as a creator.",
        }
        msg_lower = message.lower()
        demo_reply = next(
            (v for k, v in demo_replies.items() if k in msg_lower),
            (
                f'I understand you\'re asking about "{message[:60]}". '
                'Configure an AI provider (Claude, Gemini, OpenRouter, or OpenAI) in Admin -> Settings -> AI for full AI chat.'
            )
        )
        return JsonResponse({'reply': demo_reply, 'demo': True})

    logger.warning('AI assistant failed across all configured providers: %s', err)
    return JsonResponse({
        'reply': f'AI assistant is temporarily unavailable. Error: {str(err)[:200]}'
    })


@require_POST
def moderate_content(request):
    """AI-powered moderation. Uses whichever text provider is configured,
    else keyword fallback."""
    content_id = request.POST.get('content_id')
    from content.models import Content
    obj = get_object_or_404(Content, pk=content_id)

    score = 0.85
    flags = {}

    bad_words = ['spam', 'xxx', 'hack', 'scam', 'malware', 'phishing']
    text = f'{obj.title} {obj.description}'.lower()
    for word in bad_words:
        if word in text:
            flags[word] = True
            score -= 0.2

    if obj.description:
        prompt = (
            f'Rate this content for a family-friendly media platform. '
            f'Title: {obj.title}. Description: {obj.description[:300]}. '
            'Reply ONLY with JSON: {"safe": true/false, "score": 0.0-1.0, "reason": "..."}'
        )
        raw, err, provider_used = ai_client.generate_text(
            'You are a strict but fair content moderator. Reply only with the requested JSON, no other text.',
            prompt,
        )
        if raw:
            try:
                raw = raw.strip()
                if raw.startswith('```'):
                    raw = raw.split('```')[1].lstrip('json').strip()
                ai_result = json.loads(raw)
                score = float(ai_result.get('score', score))
                if not ai_result.get('safe', True):
                    flags['ai_unsafe'] = ai_result.get('reason', 'Flagged by AI')
            except Exception as e:
                logger.warning('Could not parse AI moderation response from %s: %s', provider_used, e)
        elif err and 'No AI text provider is configured' not in err:
            logger.warning('AI moderation failed: %s', err)

    obj.ai_score    = max(0.0, min(1.0, score))
    obj.ai_flags    = flags
    obj.ai_reviewed = True
    obj.status      = 'approved' if obj.ai_score >= 0.5 and not flags else 'rejected'
    obj.save()

    return JsonResponse({'score': obj.ai_score, 'flags': flags, 'status': obj.status})
