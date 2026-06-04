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

    return {
        'site_settings': settings_data,
        'unread_notifs': unread_notifs,
    }
