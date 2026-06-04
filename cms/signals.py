"""Invalidate CMS cache when models are saved."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache


def _clear_cms_cache(prefix='cms'):
    keys = ['cms_branding', 'cms_theme', 'cms_seo', 'cms_scripts',
            'cms_maintenance', 'cms_active_announcement']
    for key in keys:
        cache.delete(key)


def connect_signals():
    try:
        from cms.models import (
            BrandingConfig, ThemeConfig, GlobalSEO,
            ScriptInjection, MaintenanceConfig, Announcement
        )
        for model in [BrandingConfig, ThemeConfig, GlobalSEO,
                      ScriptInjection, MaintenanceConfig, Announcement]:
            post_save.connect(lambda sender, **kw: _clear_cms_cache(), sender=model)
    except Exception:
        pass


connect_signals()
