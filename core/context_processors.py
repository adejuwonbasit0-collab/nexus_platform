from django.core.cache import cache
from .models import SiteSettings, Notification


def site_settings(request):
    settings_data = cache.get('site_settings_all')
    if settings_data is None:
        qs = SiteSettings.objects.all()
        settings_data = {s.key: s.value for s in qs}
        cache.set('site_settings_all', settings_data, 600)

    unread_notifs = 0
    if request.user.is_authenticated:
        unread_notifs = cache.get(f'unread_notifs_{request.user.pk}')
        if unread_notifs is None:
            unread_notifs = Notification.objects.filter(
                user=request.user, is_read=False
            ).count()
            cache.set(f'unread_notifs_{request.user.pk}', unread_notifs, 60)

    # CMS nav and footer pages
    nav_pages    = cache.get('cms_nav_pages')
    footer_pages = cache.get('cms_footer_pages')
    if nav_pages is None:
        try:
            from cms.models import StaticPage
            nav_pages    = list(StaticPage.objects.filter(show_in_nav=True,    status='published').values('title','slug'))
            footer_pages = list(StaticPage.objects.filter(show_in_footer=True, status='published').values('title','slug'))
        except Exception:
            nav_pages = []
            footer_pages = []
        cache.set('cms_nav_pages',    nav_pages,    120)
        cache.set('cms_footer_pages', footer_pages, 120)

    # Branding
    branding = cache.get('cms_branding')
    if branding is None:
        try:
            from cms.models import BrandingConfig
            branding = BrandingConfig.get()
        except Exception:
            branding = None
        cache.set('cms_branding', branding, 300)

    return {
        'site_settings': settings_data,
        'unread_notifs': unread_notifs,
        'nav_pages':     nav_pages or [],
        'footer_pages':  footer_pages or [],
        'branding':      branding,
    }
