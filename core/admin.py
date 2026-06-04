from django.contrib import admin
from .models import SiteSettings, AILog, AIGeneratedImage, AIProviderSettings, Notification


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'group', 'setting_type']
    search_fields = ['key']


@admin.register(AIProviderSettings)
class AIProviderSettingsAdmin(admin.ModelAdmin):
    list_display  = ['provider', 'is_active', 'model_name', 'updated_at']
    list_editable = ['is_active']

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Don't pre-fill the key in the form for security
        return form


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['user', 'notif_type', 'title', 'is_read', 'created_at']
    list_filter   = ['notif_type', 'is_read']
    search_fields = ['user__username', 'title']


admin.site.register(AILog)
admin.site.register(AIGeneratedImage)
