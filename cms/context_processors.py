"""
CMS Context Processor — injects CMS data into every template.
Uses in-memory cache to avoid repeated DB hits.
"""
from django.core.cache import cache
from django.utils import timezone


def cms_context(request):
    ctx = {}

    # Branding (cached 1 hour)
    branding = cache.get('cms_branding')
    if branding is None:
        try:
            from .models import BrandingConfig
            branding = BrandingConfig.get()
            cache.set('cms_branding', branding, 3600)
        except Exception:
            branding = None
    ctx['branding'] = branding

    # Theme (cached 1 hour)
    theme = cache.get('cms_theme')
    if theme is None:
        try:
            from .models import ThemeConfig
            theme = ThemeConfig.get()
            cache.set('cms_theme', theme, 3600)
        except Exception:
            theme = None
    ctx['cms_theme'] = theme

    # Global SEO
    seo = cache.get('cms_seo')
    if seo is None:
        try:
            from .models import GlobalSEO
            seo = GlobalSEO.get()
            cache.set('cms_seo', seo, 3600)
        except Exception:
            seo = None
    ctx['global_seo'] = seo

    # Page-level SEO override
    try:
        from .models import PageSEO
        path = request.path
        page_seo = cache.get(f'page_seo_{path}')
        if page_seo is None:
            page_seo = PageSEO.objects.filter(path=path).first()
            cache.set(f'page_seo_{path}', page_seo or 'NONE', 600)
        if page_seo == 'NONE':
            page_seo = None
        ctx['page_seo'] = page_seo
    except Exception:
        ctx['page_seo'] = None

    # Active announcement/banner
    announcement = cache.get('cms_active_announcement')
    if announcement is None:
        try:
            from .models import Announcement
            now = timezone.now()
            qs = Announcement.objects.filter(
                is_active=True,
                announcement_type='banner',
            ).filter(
                models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now)
            ).filter(
                models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now)
            )
            # Filter by user state
            if request.user.is_authenticated:
                qs = qs.filter(show_to_logged_in=True)
            else:
                qs = qs.filter(show_to_guests=True)
            announcement = qs.first() or 'NONE'
            cache.set('cms_active_announcement', announcement, 120)
        except Exception:
            announcement = 'NONE'
    ctx['announcement_banner'] = announcement if announcement != 'NONE' else None

    # Scripts for injection
    scripts = cache.get('cms_scripts')
    if scripts is None:
        try:
            from .models import ScriptInjection
            scripts = list(ScriptInjection.objects.filter(is_active=True).order_by('position', 'order'))
            cache.set('cms_scripts', scripts, 600)
        except Exception:
            scripts = []
    ctx['cms_scripts_head']       = [s for s in scripts if s.position == 'head']
    ctx['cms_scripts_body_start'] = [s for s in scripts if s.position == 'body_start']
    ctx['cms_scripts_body_end']   = [s for s in scripts if s.position == 'body_end']

    # Maintenance mode
    maintenance = cache.get('cms_maintenance')
    if maintenance is None:
        try:
            from .models import MaintenanceConfig
            maintenance = MaintenanceConfig.get()
            cache.set('cms_maintenance', maintenance, 60)
        except Exception:
            maintenance = None
    ctx['maintenance_config'] = maintenance

    return ctx


# Fix missing import
from django.db import models
