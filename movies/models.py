from django.db import models

import os as _os

def _platform_upload(subfolder, filename):
    from core.models import SiteSettings
    try:
        name = SiteSettings.objects.get(key='site_name').value or 'NEXUS'
    except Exception:
        name = 'NEXUS'
    return _os.path.join(name.upper().replace(' ','_'), subfolder, filename)

def movie_thumb_path(instance, filename):   return _platform_upload('movies/thumbs', filename)
def movie_file_path(instance, filename):    return _platform_upload('movies/files', filename)
def series_thumb_path(instance, filename):  return _platform_upload('series/thumbs', filename)
def episode_file_path(instance, filename):  return _platform_upload('episodes/files', filename)
def episode_thumb_path(instance, filename): return _platform_upload('episodes/thumbs', filename)


from django.conf import settings


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    def __str__(self): return self.name


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=5, blank=True)
    def __str__(self): return self.name


class Movie(models.Model):
    QUALITY = [('SD','SD'),('HD','HD'),('FHD','Full HD'),('4K','4K')]
    title        = models.CharField(max_length=300)
    slug         = models.SlugField(unique=True, blank=True)
    description  = models.TextField()
    genres       = models.ManyToManyField(Genre, blank=True)
    release_year = models.IntegerField(default=2024)
    country      = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    thumbnail    = models.ImageField(upload_to=movie_thumb_path, null=True, blank=True)
    trailer_url  = models.URLField(blank=True)
    video_file   = models.FileField(upload_to=movie_file_path, null=True, blank=True)
    video_url    = models.URLField(blank=True, help_text='External link to the video file (used instead of an upload to save storage space).')
    subtitles    = models.TextField(blank=True, help_text='SRT-format subtitles or plain text transcript. If empty, AI can generate a scene summary.')
    quality      = models.CharField(max_length=5, choices=QUALITY, default='HD')
    duration     = models.IntegerField(default=0, help_text='minutes')
    is_premium   = models.BooleanField(default=False)
    is_featured  = models.BooleanField(default=False)
    views_count  = models.IntegerField(default=0)
    downloads_count = models.IntegerField(default=0)
    likes_count  = models.IntegerField(default=0)
    rating       = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    uploaded_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug, n = base, 1
            while Movie.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self): return self.title

    @property
    def has_video(self):
        return bool(self.video_file) or bool(self.video_url)

    @property
    def is_external_video(self):
        """True when this movie's playable file is a remote link rather
        than a locally-hosted upload."""
        return bool(self.video_url) and not self.video_file

    @property
    def playable_url(self):
        if self.video_file:
            return self.video_file.url
        return self.video_url


class Series(models.Model):
    title        = models.CharField(max_length=300)
    slug         = models.SlugField(unique=True, blank=True)
    description  = models.TextField()
    genres       = models.ManyToManyField(Genre, blank=True)
    thumbnail    = models.ImageField(upload_to=series_thumb_path, null=True, blank=True)
    release_year = models.IntegerField(default=2024)
    country      = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    is_premium   = models.BooleanField(default=False)
    is_featured  = models.BooleanField(default=False)
    uploaded_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='movie_series')
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Series'

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug, n = base, 1
            while Series.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self): return self.title


class Season(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='seasons')
    number = models.IntegerField()
    title  = models.CharField(max_length=200, blank=True)
    class Meta: ordering = ['number']
    def __str__(self): return f'{self.series.title} S{self.number}'


class Episode(models.Model):
    season      = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='episodes')
    number      = models.IntegerField()
    title       = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    thumbnail   = models.ImageField(upload_to=episode_thumb_path, null=True, blank=True)
    video_file  = models.FileField(upload_to=episode_file_path, null=True, blank=True)
    video_url   = models.URLField(blank=True, help_text='External link to the video file (used instead of an upload to save storage space).')
    subtitles   = models.TextField(blank=True, help_text='SRT-format subtitles or plain text transcript.')
    duration    = models.IntegerField(default=0, help_text='minutes')
    views_count = models.IntegerField(default=0)
    is_published= models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['number']
    def __str__(self): return f'{self.season} E{self.number}: {self.title}'

    @property
    def has_video(self):
        return bool(self.video_file) or bool(self.video_url)

    @property
    def is_external_video(self):
        return bool(self.video_url) and not self.video_file

    @property
    def playable_url(self):
        if self.video_file:
            return self.video_file.url
        return self.video_url


class WatchProgress(models.Model):
    """Continue watching"""
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    movie      = models.ForeignKey(Movie, null=True, blank=True, on_delete=models.CASCADE)
    episode    = models.ForeignKey(Episode, null=True, blank=True, on_delete=models.CASCADE)
    progress   = models.IntegerField(default=0, help_text='seconds watched')
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: unique_together = [('user','movie'),('user','episode')]


class MovieComment(models.Model):
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    movie     = models.ForeignKey(Movie, null=True, blank=True, on_delete=models.CASCADE, related_name='comments')
    episode   = models.ForeignKey(Episode, null=True, blank=True, on_delete=models.CASCADE, related_name='comments')
    text      = models.TextField()
    created_at= models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']


class MovieLike(models.Model):
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='liked_by')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: unique_together = [('user', 'movie')]