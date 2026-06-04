from django.db import models


class SiteSettings(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    label = models.CharField(max_length=200, blank=True)
    setting_type = models.CharField(
        max_length=20, default='text',
        choices=[
            ('text', 'Text'), ('textarea', 'Textarea'), ('image', 'Image'),
            ('url', 'URL'), ('bool', 'Boolean'), ('color', 'Color'),
        ]
    )
    group = models.CharField(max_length=50, default='general')

    def __str__(self):
        return self.key


class AIProviderSettings(models.Model):
    """Stores AI provider credentials – never hardcoded in settings.py"""
    PROVIDER_CHOICES = [
        ('openai',     'OpenAI (DALL-E / GPT)'),
        ('anthropic',  'Anthropic (Claude)'),
        ('stability',  'Stability AI'),
    ]
    provider   = models.CharField(max_length=30, choices=PROVIDER_CHOICES, unique=True)
    api_key    = models.CharField(max_length=500, blank=True)
    model_name = models.CharField(max_length=100, blank=True, help_text='e.g. dall-e-3, claude-sonnet-4-20250514')
    is_active  = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'AI Provider Setting'
        verbose_name_plural = 'AI Provider Settings'

    def __str__(self):
        return f'{self.get_provider_display()} ({"active" if self.is_active else "inactive"})'

    # ── helpers ──────────────────────────────────────────────────────────────
    @classmethod
    def get_key(cls, provider):
        """Return the stored API key for a provider, or ''."""
        try:
            return cls.objects.get(provider=provider, is_active=True).api_key
        except cls.DoesNotExist:
            return ''


class AILog(models.Model):
    action     = models.CharField(max_length=100)
    input_data = models.TextField()
    output_data = models.TextField()
    model_used = models.CharField(max_length=100)
    user       = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    tokens_used = models.IntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)


class AIGeneratedImage(models.Model):
    user              = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    prompt            = models.TextField()
    image_url         = models.URLField(max_length=1000)
    local_file        = models.ImageField(upload_to='ai_generated/', null=True, blank=True)
    saved_to_platform = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    """Lightweight in-app notification (no WebSockets needed)."""
    TYPE_CHOICES = [
        ('content_approved', 'Content Approved'),
        ('content_rejected', 'Content Rejected'),
        ('payment_success',  'Payment Successful'),
        ('new_content',      'New Content Added'),
        ('general',          'General'),
    ]
    user       = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notifications'
    )
    notif_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='general')
    title      = models.CharField(max_length=200)
    message    = models.TextField(blank=True)
    is_read    = models.BooleanField(default=False)
    link       = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.notif_type}] {self.title} → {self.user.username}'


class EmailConfig(models.Model):
    """Admin-configurable email backend settings — all from frontend, no code changes."""
    BACKENDS = [
        ('smtp',     'SMTP (Custom)'),
        ('sendgrid', 'SendGrid'),
        ('mailgun',  'Mailgun'),
        ('ses',      'Amazon SES'),
        ('console',  'Console (dev only)'),
    ]
    ENCRYPTIONS = [('tls', 'TLS (STARTTLS — port 587)'), ('ssl', 'SSL (port 465)'), ('none', 'None (port 25)')]

    backend        = models.CharField(max_length=20, choices=BACKENDS, default='smtp')
    host           = models.CharField(max_length=300, blank=True, default='smtp.gmail.com')
    port           = models.IntegerField(default=587)
    encryption     = models.CharField(max_length=10, choices=ENCRYPTIONS, default='tls')
    username       = models.CharField(max_length=300, blank=True)
    password       = models.CharField(max_length=500, blank=True, help_text='App password or API key')
    from_email     = models.EmailField(blank=True, default='noreply@example.com')
    from_name      = models.CharField(max_length=200, blank=True, default='NEXUS')
    is_active      = models.BooleanField(default=False)
    # SendGrid / Mailgun
    api_key        = models.CharField(max_length=500, blank=True)
    # Test
    test_recipient = models.EmailField(blank=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Email Configuration'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def apply_to_django(self):
        """Push this config into Django's live email settings."""
        import django.conf
        s = django.conf.settings
        if self.backend == 'console' or not self.is_active:
            s.EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
            return
        s.EMAIL_BACKEND  = 'django.core.mail.backends.smtp.EmailBackend'
        s.EMAIL_HOST     = self.host
        s.EMAIL_PORT     = self.port
        s.EMAIL_USE_TLS  = self.encryption == 'tls'
        s.EMAIL_USE_SSL  = self.encryption == 'ssl'
        s.EMAIL_HOST_USER     = self.username
        s.EMAIL_HOST_PASSWORD = self.password or self.api_key
        s.DEFAULT_FROM_EMAIL  = f'{self.from_name} <{self.from_email}>'

    def __str__(self):
        return f'Email Config ({self.backend})'


class GatewayConfig(models.Model):
    """Per-gateway payment credentials stored in DB."""
    GATEWAYS = [
        ('paystack',    'Paystack'),
        ('stripe',      'Stripe'),
        ('flutterwave', 'Flutterwave'),
        ('wave',        'Wave'),
        ('bank',        'Bank Transfer / Manual'),
    ]
    gateway        = models.CharField(max_length=20, choices=GATEWAYS, unique=True)
    is_active      = models.BooleanField(default=False)
    is_test_mode   = models.BooleanField(default=True)
    public_key     = models.CharField(max_length=500, blank=True)
    secret_key     = models.CharField(max_length=500, blank=True)
    webhook_secret = models.CharField(max_length=500, blank=True)
    extra          = models.JSONField(default=dict, blank=True,
                                     help_text='Gateway-specific: bank_name, account_no, routing_no, etc.')
    currency       = models.CharField(max_length=10, default='NGN')
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Gateway Config'

    def __str__(self):
        return f'{self.get_gateway_display()} ({"test" if self.is_test_mode else "live"})'
