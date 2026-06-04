from django.db import models
from django.conf import settings


class Category(models.Model):
    name         = models.CharField(max_length=100)
    slug         = models.SlugField(unique=True)
    content_type = models.CharField(
        max_length=20,
        choices=[('image', 'Image'), ('video', 'Video'), ('music', 'Music'), ('blog', 'Blog')]
    )
    icon = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


# ── File validation constants ─────────────────────────────────────────────────
ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
ALLOWED_VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
ALLOWED_AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}
ALLOWED_DOC_EXTS   = {'.pdf'}
MAX_FILE_SIZE_MB   = 500   # MB
MAX_THUMB_SIZE_MB  = 10


class Content(models.Model):
    TYPE_CHOICES   = [('image', 'Image'), ('video', 'Video'), ('music', 'Music'), ('blog', 'Blog')]
    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    TIER_CHOICES   = [('free', 'Free'), ('premium', 'Premium')]

    creator      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contents'
    )
    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    tier         = models.CharField(max_length=20, choices=TIER_CHOICES, default='free')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    category     = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags         = models.ManyToManyField(Tag, blank=True)

    # Files
    file      = models.FileField(upload_to='content/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True)

    # Blog specific
    body = models.TextField(blank=True)

    # Stats
    views           = models.IntegerField(default=0)
    likes_count     = models.IntegerField(default=0)
    downloads_count = models.IntegerField(default=0)

    # AI moderation
    ai_score    = models.FloatField(null=True, blank=True)
    ai_flags    = models.JSONField(default=dict, blank=True)
    ai_reviewed = models.BooleanField(default=False)

    # Monetisation
    price    = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_ai_generated = models.BooleanField(default=False)
    is_published    = models.BooleanField(default=False)   # NEW – mirrors approved status
    featured        = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Keep is_published in sync with status
        self.is_published = (self.status == 'approved')
        super().save(*args, **kwargs)


class Series(models.Model):
    creator     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    thumbnail   = models.ImageField(upload_to='series/', null=True, blank=True)
    tier        = models.CharField(
        max_length=20, choices=[('free', 'Free'), ('premium', 'Premium')], default='free'
    )
    genre  = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Season(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='seasons')
    number = models.IntegerField()
    title  = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'{self.series.title} S{self.number}'


class Episode(models.Model):
    season      = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='episodes')
    number      = models.IntegerField()
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file        = models.FileField(upload_to='episodes/')
    thumbnail   = models.ImageField(upload_to='ep_thumbs/', null=True, blank=True)
    duration    = models.IntegerField(default=0, help_text='Duration in seconds')
    views       = models.IntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.season} E{self.number}: {self.title}'


class Comment(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content    = models.ForeignKey(
        Content, on_delete=models.CASCADE, null=True, blank=True, related_name='comments'
    )
    series     = models.ForeignKey(
        Series, on_delete=models.CASCADE, null=True, blank=True, related_name='comments'
    )
    text       = models.TextField()
    is_flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Like(models.Model):
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, on_delete=models.CASCADE, null=True, blank=True)
    series  = models.ForeignKey(Series, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'content'), ('user', 'series')]


class Download(models.Model):
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    content    = models.ForeignKey(Content, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class View(models.Model):
    content    = models.ForeignKey(Content, on_delete=models.CASCADE, null=True, blank=True)
    episode    = models.ForeignKey(Episode, on_delete=models.CASCADE, null=True, blank=True)
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
