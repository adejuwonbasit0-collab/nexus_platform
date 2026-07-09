from django.db import models
from django.conf import settings


class Short(models.Model):
    """A short vertical video (TikTok/Reels-style). Video is always an
    external URL, never an uploaded file — keeps storage cheap since these
    are meant to be fetched from stock sources or linked to externally
    hosted clips rather than stored on this server."""

    title        = models.CharField(max_length=200, blank=True)
    slug         = models.SlugField(unique=True, blank=True, max_length=220)
    description  = models.TextField(blank=True)

    video_url    = models.URLField(max_length=500, help_text='Direct video file URL (mp4) or a YouTube link.')
    thumbnail_url = models.URLField(max_length=500, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)

    # Optional link into a Series, so episodes can play back-to-back in the
    # feed like consecutive shorts instead of only standalone clips.
    series          = models.ForeignKey('movies.Series', null=True, blank=True, on_delete=models.SET_NULL, related_name='shorts')
    episode_number  = models.PositiveIntegerField(null=True, blank=True)

    uploaded_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_fetched   = models.BooleanField(default=False)
    fetch_source = models.CharField(max_length=50, blank=True)

    is_published = models.BooleanField(default=False)
    is_premium   = models.BooleanField(default=False)

    view_count   = models.PositiveIntegerField(default=0)
    like_count   = models.PositiveIntegerField(default=0)

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f'Short #{self.pk}'

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title) or 'short'
            slug, n = base, 1
            while Short.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f'{base}-{n}'
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_youtube(self):
        u = (self.video_url or '').lower()
        return 'youtube.com' in u or 'youtu.be' in u

    def get_edit_json(self):
        import json
        data = {
            'title': self.title,
            'description': self.description,
            'video_url': self.video_url,
            'thumbnail_url': self.thumbnail_url,
            'series_pk': self.series_id,
            'episode_number': self.episode_number,
            'is_published': self.is_published,
            'is_premium': self.is_premium,
        }
        return json.dumps(data)


class ShortLike(models.Model):
    short = models.ForeignKey(Short, on_delete=models.CASCADE, related_name='likes')
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('short', 'user')
