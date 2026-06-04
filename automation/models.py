"""
Automation Center — workflow definitions, scheduled jobs, email sequences.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class ScheduledJob(models.Model):
    STATUSES = [('active','Active'),('paused','Paused'),('completed','Completed'),('failed','Failed')]
    INTERVALS = [
        ('once','Run Once'),('hourly','Hourly'),('daily','Daily'),
        ('weekly','Weekly'),('monthly','Monthly'),('custom','Custom (cron)'),
    ]
    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    task_name    = models.CharField(max_length=300, help_text='Dotted task path, e.g. music.tasks.update_trends')
    task_kwargs  = models.JSONField(default=dict, blank=True)
    interval     = models.CharField(max_length=20, choices=INTERVALS, default='daily')
    cron_expr    = models.CharField(max_length=100, blank=True, help_text='Cron expression if interval=custom')
    status       = models.CharField(max_length=20, choices=STATUSES, default='active')
    last_run     = models.DateTimeField(null=True, blank=True)
    next_run     = models.DateTimeField(null=True, blank=True)
    run_count    = models.IntegerField(default=0)
    error_count  = models.IntegerField(default=0)
    last_error   = models.TextField(blank=True)
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.interval})'


class WorkflowDefinition(models.Model):
    TRIGGER_EVENTS = [
        ('user.registered',       'User Registered'),
        ('user.subscribed',       'User Subscribed'),
        ('user.cancelled',        'Subscription Cancelled'),
        ('content.approved',      'Content Approved'),
        ('content.rejected',      'Content Rejected'),
        ('content.uploaded',      'Content Uploaded'),
        ('payment.completed',     'Payment Completed'),
        ('payment.failed',        'Payment Failed'),
        ('withdrawal.requested',  'Withdrawal Requested'),
        ('withdrawal.approved',   'Withdrawal Approved'),
        ('creator.milestone',     'Creator Milestone Reached'),
        ('comment.posted',        'Comment Posted'),
    ]
    name          = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    trigger_event = models.CharField(max_length=50, choices=TRIGGER_EVENTS)
    is_active     = models.BooleanField(default=True)
    run_count     = models.IntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} → {self.trigger_event}'


class WorkflowAction(models.Model):
    ACTION_TYPES = [
        ('send_email',         'Send Email'),
        ('send_notification',  'Send Notification'),
        ('send_webhook',       'Call Webhook'),
        ('update_user',        'Update User Field'),
        ('wait',               'Wait (delay)'),
        ('condition',          'Conditional Branch'),
    ]
    workflow    = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    order       = models.PositiveIntegerField(default=0)
    config      = models.JSONField(default=dict, help_text='Action-specific configuration')
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'[{self.action_type}] Step {self.order} of "{self.workflow.name}"'


class WorkflowRun(models.Model):
    STATUSES = [('running','Running'),('completed','Completed'),('failed','Failed'),('skipped','Skipped')]
    workflow   = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='runs')
    trigger_context = models.JSONField(default=dict)
    status     = models.CharField(max_length=20, choices=STATUSES, default='running')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at= models.DateTimeField(null=True, blank=True)
    error      = models.TextField(blank=True)
    steps_log  = models.JSONField(default=list)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'Run #{self.pk} of {self.workflow.name} ({self.status})'


class EmailSequence(models.Model):
    """Multi-step email drip sequences."""
    name       = models.CharField(max_length=200)
    trigger    = models.CharField(max_length=50, choices=WorkflowDefinition.TRIGGER_EVENTS)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class EmailSequenceStep(models.Model):
    sequence      = models.ForeignKey(EmailSequence, on_delete=models.CASCADE, related_name='steps')
    step_number   = models.PositiveIntegerField()
    delay_hours   = models.IntegerField(default=0, help_text='Hours after previous step')
    subject       = models.CharField(max_length=300)
    body_html     = models.TextField()
    is_active     = models.BooleanField(default=True)

    class Meta:
        ordering = ['step_number']

    def __str__(self):
        return f'Step {self.step_number}: {self.subject}'
