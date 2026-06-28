import os
from django.db import models
from django.conf import settings
from django.utils.text import slugify


# ── Upload path helpers ───────────────────────────────────────────────────────

def _platform_prefix():
    try:
        from core.models import SiteSettings
        name = SiteSettings.objects.get(key='site_name').value or 'NEXUS'
    except Exception:
        name = 'NEXUS'
    return name.upper().replace(' ', '_')


def artist_photo_path(instance, filename):
    return os.path.join(_platform_prefix(), 'music', 'artists', filename)

def album_cover_path(instance, filename):
    return os.path.join(_platform_prefix(), 'music', 'albums', filename)

def track_audio_path(instance, filename):
    return os.path.join(_platform_prefix(), 'music', 'tracks', filename)

def track_cover_path(instance, filename):
    return os.path.join(_platform_prefix(), 'music', 'covers', filename)

def branding_path(instance, filename):
    return os.path.join(_platform_prefix(), 'branding', filename)


# ── Models ────────────────────────────────────────────────────────────────────

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10, blank=True, default='🎵')

    def __str__(self): return self.name


class Artist(models.Model):
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                             on_delete=models.SET_NULL, related_name='artist_profile')
    name             = models.CharField(max_length=200)
    slug             = models.SlugField(unique=True, blank=True)
    bio              = models.TextField(blank=True)
    photo            = models.ImageField(upload_to=artist_photo_path, null=True, blank=True)
    country          = models.CharField(max_length=100, blank=True)
    website          = models.URLField(blank=True)
    social_instagram = models.URLField(blank=True)
    social_twitter   = models.URLField(blank=True)
    social_youtube   = models.URLField(blank=True)
    is_verified      = models.BooleanField(default=False)
    monthly_listeners= models.IntegerField(default=0)
    trend_score      = models.FloatField(default=0.0)
    created_at       = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug, n = base, 1
            while Artist.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def total_plays(self):
        return self.tracks.aggregate(t=models.Sum('plays_count'))['t'] or 0

    def __str__(self): return self.name


class Album(models.Model):
    ALBUM_TYPES = [
        ('album', 'Album'), ('ep', 'EP'),
        ('single', 'Single'), ('compilation', 'Compilation'),
    ]
    title        = models.CharField(max_length=300)
    slug         = models.SlugField(unique=True, blank=True)
    artist       = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='albums')
    genre        = models.ForeignKey(Genre, null=True, blank=True, on_delete=models.SET_NULL)
    cover_image  = models.ImageField(upload_to=album_cover_path, null=True, blank=True)
    release_year = models.IntegerField(default=2024)
    album_type   = models.CharField(max_length=20, choices=ALBUM_TYPES, default='album')
    description  = models.TextField(blank=True)
    label        = models.CharField(max_length=200, blank=True)
    is_published = models.BooleanField(default=True)
    uploaded_by  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='albums_uploaded')
    plays_count  = models.IntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            artist_name = getattr(self, '_artist_name', '')
            if not artist_name:
                try: artist_name = self.artist.name
                except Exception: artist_name = ''
            base = slugify(f'{artist_name}-{self.title}')
            slug, n = base, 1
            while Album.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self): return f'{self.title} – {self.artist.name}'


class Track(models.Model):
    title            = models.CharField(max_length=300)
    slug             = models.SlugField(unique=True, blank=True)
    artist           = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='tracks')
    featured_artists = models.ManyToManyField(Artist, related_name='featured_on', blank=True)
    album            = models.ForeignKey(Album, null=True, blank=True, on_delete=models.SET_NULL, related_name='tracks')
    genre            = models.ForeignKey(Genre, null=True, blank=True, on_delete=models.SET_NULL)
    audio_file       = models.FileField(upload_to=track_audio_path, null=True, blank=True)
    audio_url        = models.URLField(blank=True, help_text='External link to the audio file (used instead of an upload to save storage space).')
    cover_image      = models.ImageField(upload_to=track_cover_path, null=True, blank=True)
    release_year     = models.IntegerField(default=2024)
    duration         = models.IntegerField(default=0, help_text='seconds')
    lyrics           = models.TextField(blank=True)
    lyrics_lrc       = models.TextField(blank=True, help_text='Timestamped LRC format e.g. [00:12.50] Line of lyrics')
    # Credits
    produced_by  = models.CharField(max_length=300, blank=True)
    recorded_at  = models.CharField(max_length=300, blank=True)
    written_by   = models.CharField(max_length=300, blank=True)
    mixed_by     = models.CharField(max_length=300, blank=True)
    mastered_by  = models.CharField(max_length=300, blank=True)
    country      = models.CharField(max_length=100, blank=True)
    label        = models.CharField(max_length=200, blank=True)
    isrc         = models.CharField(max_length=20, blank=True)
    # Flags
    is_premium     = models.BooleanField(default=False)
    is_featured    = models.BooleanField(default=False)
    is_published   = models.BooleanField(default=True)
    is_song_of_day = models.BooleanField(default=False)
    # Stats
    plays_count     = models.IntegerField(default=0)
    downloads_count = models.IntegerField(default=0)
    likes_count     = models.IntegerField(default=0)
    trend_score     = models.FloatField(default=0.0)
    uploaded_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug, n = base, 1
            while Track.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def duration_str(self):
        if not self.duration: return '—'
        m, s = divmod(self.duration, 60)
        return f'{m}:{s:02d}'

    @property
    def has_audio(self):
        return bool(self.audio_file) or bool(self.audio_url)

    @property
    def is_external_audio(self):
        return bool(self.audio_url) and not self.audio_file

    @property
    def playable_url(self):
        if self.audio_file:
            return self.audio_file.url
        return self.audio_url

    def __str__(self): return f'{self.title} – {self.artist.name}'


class TrackLike(models.Model):
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='liked_by')
    class Meta: unique_together = [('user', 'track')]


class Playlist(models.Model):
    owner      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title      = models.CharField(max_length=200)
    tracks     = models.ManyToManyField(Track, blank=True)
    is_public  = models.BooleanField(default=True)
    cover      = models.ImageField(upload_to=track_cover_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.title


class MusicComment(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='music_comments')
    track      = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='comments')
    text       = models.TextField()
    likes      = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']


class TrendingSnapshot(models.Model):
    CONTENT_CHOICES = [('track', 'Track'), ('artist', 'Artist'), ('album', 'Album')]
    content_type  = models.CharField(max_length=20, choices=CONTENT_CHOICES)
    object_id     = models.IntegerField()
    score         = models.FloatField(default=0.0)
    rank          = models.IntegerField(default=0)
    snapshot_date = models.DateField(auto_now_add=True)
    class Meta: ordering = ['rank']


class PlatformBranding(models.Model):
    logo           = models.ImageField(upload_to=branding_path)
    logo_dark      = models.ImageField(upload_to=branding_path, null=True, blank=True)
    watermark      = models.ImageField(upload_to=branding_path, null=True, blank=True)
    show_on_player = models.BooleanField(default=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta: verbose_name = 'Platform Branding'

    @classmethod
    def get(cls):
        return cls.objects.first()

    def __str__(self): return 'Platform Branding'
