from django.urls import path
from . import views

urlpatterns = [
    path('health/',           views.system_health,       name='system_health'),
    path('health/api/',       views.system_health_api,   name='system_health_api'),
    path('audit-logs/',       views.audit_logs,          name='audit_logs'),
    path('security-alerts/',  views.security_alerts,     name='security_alerts'),
    path('security-alerts/<int:pk>/resolve/', views.resolve_alert, name='resolve_alert'),
    path('error-logs/',       views.error_logs,          name='error_logs'),
    path('health/snapshot/',  views.take_health_snapshot,name='take_health_snapshot'),
]
