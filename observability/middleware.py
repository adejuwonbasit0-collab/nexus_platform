"""Audit Log Middleware — tracks admin and auth actions."""
import logging
from django.utils import timezone

logger = logging.getLogger('nexus')

TRACKED_PATHS = ['/admin-panel/', '/auth/', '/creator/']
SKIP_EXTENSIONS = ['.css', '.js', '.png', '.jpg', '.ico', '.woff']


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_log(request, response)
        except Exception as e:
            logger.debug('AuditLog error: %s', e)
        return response

    def _maybe_log(self, request, response):
        path = request.path
        # Skip static/media and non-tracked paths
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            return
        if not any(path.startswith(p) for p in TRACKED_PATHS):
            return
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return
        if not request.user.is_authenticated:
            return

        from .models import AuditLog
        action = 'other'
        if '/approve/' in path:
            action = 'approve'
        elif '/reject/' in path:
            action = 'reject'
        elif '/delete/' in path:
            action = 'delete'
        elif request.method == 'POST' and '/create/' in path:
            action = 'create'
        elif request.method == 'POST' and '/edit/' in path:
            action = 'update'
        elif '/settings/' in path:
            action = 'settings_change'
        elif '/login/' in path:
            action = 'login' if response.status_code in (200, 302) else 'login_failed'

        AuditLog.objects.create(
            user=request.user,
            action=action,
            description=f'{request.method} {path}',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            extra_data={'status_code': response.status_code},
        )
