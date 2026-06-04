"""Core utilities — file validation, notifications, email sending."""
import os
import mimetypes
import logging
from django.utils import timezone

logger = logging.getLogger('nexus')

ALLOWED_VIDEO_TYPES  = {'video/mp4','video/webm','video/ogg','video/quicktime','video/x-msvideo'}
ALLOWED_IMAGE_TYPES  = {'image/jpeg','image/png','image/webp','image/gif'}
ALLOWED_AUDIO_TYPES  = {'audio/mpeg','audio/ogg','audio/wav','audio/flac','audio/aac','audio/mp4'}
ALLOWED_DOC_TYPES    = {'application/pdf','text/plain','text/html'}
ALLOWED_EXTENSIONS   = {'.mp4','.webm','.ogg','.mov','.avi','.jpg','.jpeg','.png','.webp',
                         '.gif','.mp3','.wav','.flac','.aac','.m4a','.pdf','.txt'}
MAX_SIZES = {'video': 500, 'image': 50, 'music': 100, 'thumbnail': 10}


def _mime_from_file(file_obj):
    name = getattr(file_obj, 'name', '')
    mime, _ = mimetypes.guess_type(name)
    return mime or ''


def validate_upload(file_obj, content_type):
    if not file_obj:
        return None  # optional — let caller decide
    ext  = os.path.splitext(getattr(file_obj, 'name', ''))[1].lower()
    mime = _mime_from_file(file_obj)
    size_mb = file_obj.size / (1024 * 1024)

    if ext and ext not in ALLOWED_EXTENSIONS:
        return f'File type "{ext}" is not allowed.'

    if content_type == 'video' and mime not in ALLOWED_VIDEO_TYPES:
        return 'Please upload a valid video file (MP4, WebM, MOV, AVI).'
    if content_type in ('image',) and mime not in ALLOWED_IMAGE_TYPES:
        return 'Please upload a valid image (JPG, PNG, WebP, GIF).'
    if content_type == 'music' and mime not in ALLOWED_AUDIO_TYPES:
        return 'Please upload a valid audio file (MP3, WAV, FLAC, AAC).'

    max_mb = MAX_SIZES.get(content_type, 500)
    if size_mb > max_mb:
        return f'File too large. Maximum size for {content_type} is {max_mb} MB.'
    return None


def validate_thumbnail(file_obj):
    if not file_obj:
        return None
    ext  = os.path.splitext(getattr(file_obj, 'name', ''))[1].lower()
    mime = _mime_from_file(file_obj)
    size_mb = file_obj.size / (1024 * 1024)
    if mime not in ALLOWED_IMAGE_TYPES:
        return 'Thumbnail must be a valid image (JPG, PNG, WebP).'
    if size_mb > MAX_SIZES['thumbnail']:
        return f'Thumbnail too large. Maximum size is {MAX_SIZES["thumbnail"]} MB.'
    return None


def notify(user, notif_type, title, message, link=''):
    """Create an in-app notification for the given user."""
    try:
        from .models import Notification
        Notification.objects.create(
            user=user, notif_type=notif_type,
            title=title, message=message, link=link,
        )
    except Exception as e:
        logger.warning('notify() failed: %s', e)


def send_template_email(template_type, to_email, context):
    """
    Send an email using a CMS EmailTemplate.
    Falls back to plain text if template not found.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        from cms.models import EmailTemplate
        tmpl = EmailTemplate.objects.filter(
            template_type=template_type, is_active=True
        ).first()
        if tmpl:
            subject  = tmpl.subject
            body_html = tmpl.body_html
            body_text = tmpl.body_text or ''
            for key, val in context.items():
                placeholder = f'{{{{{key}}}}}'
                subject   = subject.replace(placeholder, str(val))
                body_html = body_html.replace(placeholder, str(val))
                body_text = body_text.replace(placeholder, str(val))
            from_email = (
                f'{tmpl.from_name} <{tmpl.from_email}>' if tmpl.from_name and tmpl.from_email
                else settings.DEFAULT_FROM_EMAIL
            )
            send_mail(subject, body_text, from_email, [to_email],
                      html_message=body_html, fail_silently=True)
            return True
    except Exception as e:
        logger.warning('send_template_email failed: %s', e)
    return False


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')

# AI helper functions
def get_ai_key(provider):
    """Get API key for AI provider (OpenAI or Anthropic)"""
    import os
    from django.conf import settings
    if provider.lower() == 'openai':
        return os.environ.get('OPENAI_API_KEY', getattr(settings, 'OPENAI_API_KEY', ''))
    elif provider.lower() == 'anthropic':
        return os.environ.get('ANTHROPIC_API_KEY', getattr(settings, 'ANTHROPIC_API_KEY', ''))
    return ''

def is_demo_mode(provider='openai'):
    return not get_ai_key(provider)

def get_demo_image_url(prompt):
    import hashlib
    hash_val = hashlib.md5(prompt.encode()).hexdigest()[:8]
    return f"https://picsum.photos/id/{int(hash_val, 16) % 1000}/800/600"

def verify_paystack_transaction(reference):
    import requests
    from django.conf import settings
    paystack_secret = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    if not paystack_secret:
        return {'status': False, 'message': 'Paystack not configured'}
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {'Authorization': f'Bearer {paystack_secret}', 'Content-Type': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()
        if data.get('status') and data.get('data', {}).get('status') == 'success':
            return {'status': True, 'amount': data['data']['amount'] / 100, 'currency': data['data']['currency'], 'customer': data['data']['customer']['email']}
        return {'status': False, 'message': 'Transaction verification failed'}
    except Exception as e:
        return {'status': False, 'message': str(e)}
