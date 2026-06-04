from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='ScheduledJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('task_name', models.CharField(max_length=300)),
                ('task_kwargs', models.JSONField(blank=True, default=dict)),
                ('interval', models.CharField(choices=[('once','Run Once'),('hourly','Hourly'),('daily','Daily'),('weekly','Weekly'),('monthly','Monthly'),('custom','Custom (cron)')], default='daily', max_length=20)),
                ('cron_expr', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(choices=[('active','Active'),('paused','Paused'),('completed','Completed'),('failed','Failed')], default='active', max_length=20)),
                ('last_run', models.DateTimeField(blank=True, null=True)),
                ('next_run', models.DateTimeField(blank=True, null=True)),
                ('run_count', models.IntegerField(default=0)),
                ('error_count', models.IntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='WorkflowDefinition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('trigger_event', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('run_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='WorkflowAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='automation.workflowdefinition')),
                ('action_type', models.CharField(max_length=30)),
                ('order', models.PositiveIntegerField(default=0)),
                ('config', models.JSONField(default=dict)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['order']},
        ),
        migrations.CreateModel(
            name='WorkflowRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='runs', to='automation.workflowdefinition')),
                ('trigger_context', models.JSONField(default=dict)),
                ('status', models.CharField(choices=[('running','Running'),('completed','Completed'),('failed','Failed'),('skipped','Skipped')], default='running', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('error', models.TextField(blank=True)),
                ('steps_log', models.JSONField(default=list)),
            ],
            options={'ordering': ['-started_at']},
        ),
        migrations.CreateModel(
            name='EmailSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('trigger', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='EmailSequenceStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='automation.emailsequence')),
                ('step_number', models.PositiveIntegerField()),
                ('delay_hours', models.IntegerField(default=0)),
                ('subject', models.CharField(max_length=300)),
                ('body_html', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['step_number']},
        ),
    ]
