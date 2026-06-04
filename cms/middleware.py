"""
CMS Middleware:
1. MaintenanceModeMiddleware — shows maintenance page when enabled
2. CMSContextMiddleware — (placeholder, most work done in context_processors)
"""
from django.http import HttpResponse
from django.shortcuts import render
from django.core.cache import cache


class MaintenanceModeMiddleware:
    BYPASS_PATHS = ['/auth/login/', '/static/', '/media/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip bypass paths
        for path in self.BYPASS_PATHS:
            if request.path.startswith(path):
                return self.get_response(request)

        try:
            maintenance = cache.get('cms_maintenance')
            if maintenance is None:
                from cms.models import MaintenanceConfig
                maintenance = MaintenanceConfig.get()
                cache.set('cms_maintenance', maintenance, 60)

            if maintenance and maintenance.is_active:
                # Allow admins through
                if maintenance.allow_admins and request.user.is_authenticated and request.user.is_staff:
                    return self.get_response(request)
                # Allow whitelisted IPs
                if maintenance.allowed_ips:
                    client_ip = request.META.get('REMOTE_ADDR', '')
                    allowed = [ip.strip() for ip in maintenance.allowed_ips.split(',')]
                    if client_ip in allowed:
                        return self.get_response(request)
                # Show maintenance page
                return render(request, 'cms/maintenance.html',
                              {'maintenance': maintenance}, status=503)
        except Exception:
            pass

        return self.get_response(request)


class CMSContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
