from django.contrib import admin
from .models import CommissionSettings, Earning, Payment, PaymentSettings


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ['is_active', 'currency', 'is_test_key', 'updated_at']

    def is_test_key(self, obj):
        return obj.is_test_key
    is_test_key.boolean = True


admin.site.register(CommissionSettings)
admin.site.register(Earning)
admin.site.register(Payment)
