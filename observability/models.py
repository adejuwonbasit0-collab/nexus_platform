"""
Observability — Audit logs, system snapshots, error tracking, security alerts.
"""
import json
from django.db import models
from django.conf import settings
from django.utils import timezone


class AuditLog(models.Model):
    ACTIONS = [
        ('login',          'Login'),
        ('logout',         'Logout'),
        ('login_failed',   'Login Failed'),
        ('create',         'Create'),
        ('update',         'Update'),
        ('delete',         'Delete'),
        ('approve',        'Approve'),
        ('reject',         'Reject'),
        ('settings_change','Settings Changed'),
        ('payment',        'Payment'),
        ('payout',         'Payout'),
        ('permission_change','Permission Changed'),
        ('export',         'Data Export'),
        ('other',          'Other'),
    ]
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='audit_logs')
    action       = models.CharField(max_length=30, choices=ACTIONS, default='other')
    description  = models.CharField(max_length=500)
    model_name   = models.CharField(max_length=100, blank=True)
    object_id    = models.CharField(max_length=100, blank=True)
    object_repr  = models.CharField(max_length=300, blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.CharField(max_length=500, blank=True)
    extra_data   = models.JSONField(default=dict, blank=True)
    timestamp    = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else 'Anonymous'
        return f'[{self.action}] {user_str} — {self.description[:80]}'


class SecurityAlert(models.Model):
    SEVERITIES = [('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')]
    TYPES = [
        ('brute_force',     'Brute Force Attempt'),
        ('suspicious_login','Suspicious Login'),
        ('multiple_fails',  'Multiple Login Failures'),
        ('unusual_activity','Unusual Activity'),
        ('permission_abuse','Permission Abuse'),
        ('rate_limit',      'Rate Limit Exceeded'),
    ]
    alert_type   = models.CharField(max_length=30, choices=TYPES)
    severity     = models.CharField(max_length=10, choices=SEVERITIES, default='medium')
    description  = models.CharField(max_length=500)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL)
    extra_data   = models.JSONField(default=dict, blank=True)
    is_resolved  = models.BooleanField(default=False)
    resolved_at  = models.DateTimeField(null=True, blank=True)
    resolved_by  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='resolved_alerts')
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.severity.upper()}] {self.description[:100]}'


class SystemMetricSnapshot(models.Model):
    """Point-in-time system health snapshot."""
    cpu_percent     = models.FloatField(default=0)
    ram_percent     = models.FloatField(default=0)
    ram_used_mb     = models.FloatField(default=0)
    ram_total_mb    = models.FloatField(default=0)
    disk_percent    = models.FloatField(default=0)
    disk_used_gb    = models.FloatField(default=0)
    disk_total_gb   = models.FloatField(default=0)
    db_latency_ms   = models.FloatField(default=0)
    db_connections  = models.IntegerField(default=0)
    active_sessions = models.IntegerField(default=0)
    pending_jobs    = models.IntegerField(default=0)
    error_count_1h  = models.IntegerField(default=0)
    request_count_1h= models.IntegerField(default=0)
    extra           = models.JSONField(default=dict, blank=True)
    captured_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-captured_at']

    def __str__(self):
        return f'Snapshot @ {self.captured_at.strftime("%Y-%m-%d %H:%M")}'


class ErrorLog(models.Model):
    LEVELS = [('debug','DEBUG'),('info','INFO'),('warning','WARNING'),('error','ERROR'),('critical','CRITICAL')]
    level       = models.CharField(max_length=10, choices=LEVELS, default='error')
    message     = models.TextField()
    traceback   = models.TextField(blank=True)
    path        = models.CharField(max_length=500, blank=True)
    method      = models.CharField(max_length=10, blank=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'[{self.level}] {self.message[:100]}'
