from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
                ('action', models.CharField(choices=[('login','Login'),('logout','Logout'),('login_failed','Login Failed'),('create','Create'),('update','Update'),('delete','Delete'),('approve','Approve'),('reject','Reject'),('settings_change','Settings Changed'),('payment','Payment'),('payout','Payout'),('permission_change','Permission Changed'),('export','Data Export'),('other','Other')], default='other', max_length=30)),
                ('description', models.CharField(max_length=500)),
                ('model_name', models.CharField(blank=True, max_length=100)),
                ('object_id', models.CharField(blank=True, max_length=100)),
                ('object_repr', models.CharField(blank=True, max_length=300)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=500)),
                ('extra_data', models.JSONField(blank=True, default=dict)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={'ordering': ['-timestamp']},
        ),
        migrations.CreateModel(
            name='SecurityAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('brute_force','Brute Force Attempt'),('suspicious_login','Suspicious Login'),('multiple_fails','Multiple Login Failures'),('unusual_activity','Unusual Activity'),('permission_abuse','Permission Abuse'),('rate_limit','Rate Limit Exceeded')], max_length=30)),
                ('severity', models.CharField(choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], default='medium', max_length=10)),
                ('description', models.CharField(max_length=500)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('extra_data', models.JSONField(blank=True, default=dict)),
                ('is_resolved', models.BooleanField(default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_alerts', to=settings.AUTH_USER_MODEL)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SystemMetricSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cpu_percent', models.FloatField(default=0)),
                ('ram_percent', models.FloatField(default=0)),
                ('ram_used_mb', models.FloatField(default=0)),
                ('ram_total_mb', models.FloatField(default=0)),
                ('disk_percent', models.FloatField(default=0)),
                ('disk_used_gb', models.FloatField(default=0)),
                ('disk_total_gb', models.FloatField(default=0)),
                ('db_latency_ms', models.FloatField(default=0)),
                ('db_connections', models.IntegerField(default=0)),
                ('active_sessions', models.IntegerField(default=0)),
                ('pending_jobs', models.IntegerField(default=0)),
                ('error_count_1h', models.IntegerField(default=0)),
                ('request_count_1h', models.IntegerField(default=0)),
                ('extra', models.JSONField(blank=True, default=dict)),
                ('captured_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={'ordering': ['-captured_at']},
        ),
        migrations.CreateModel(
            name='ErrorLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(choices=[('debug','DEBUG'),('info','INFO'),('warning','WARNING'),('error','ERROR'),('critical','CRITICAL')], default='error', max_length=10)),
                ('message', models.TextField()),
                ('traceback', models.TextField(blank=True)),
                ('path', models.CharField(blank=True, max_length=500)),
                ('method', models.CharField(blank=True, max_length=10)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('is_resolved', models.BooleanField(default=False)),
                ('occurred_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={'ordering': ['-occurred_at']},
        ),
        migrations.AddIndex(model_name='auditlog', index=models.Index(fields=['user', '-timestamp'], name='obs_audit_user_idx')),
        migrations.AddIndex(model_name='auditlog', index=models.Index(fields=['action', '-timestamp'], name='obs_audit_action_idx')),
    ]
