from django.db import models

import os as _os

def _platform_upload(subfolder, filename):
    from core.models import SiteSettings
    try:
        name = SiteSettings.objects.get(key='site_name').value or 'NEXUS'
    except Exception:
        name = 'NEXUS'
    return _os.path.join(name.upper().replace(' ','_'), subfolder, filename)

def image_orig_path(instance, filename):  return _platform_upload('images/originals', filename)
def image_thumb_path(instance, filename): return _platform_upload('images/thumbs', filename)


from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    def __str__(self): return self.name


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    def __str__(self): return self.name


class Image(models.Model):
    RESOLUTION_CHOICES = [
        ('sd','SD (≤720p)'), ('hd','HD (1080p)'),
        ('2k','2K'), ('4k','4K / Ultra HD'),
    ]
    title           = models.CharField(max_length=300)
    slug            = models.SlugField(unique=True, blank=True)
    description     = models.TextField(blank=True)
    image_file      = models.ImageField(upload_to=image_orig_path)
    thumbnail       = models.ImageField(upload_to=image_thumb_path, null=True, blank=True)
    category        = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    tags            = models.ManyToManyField(Tag, blank=True)
    resolution      = models.CharField(max_length=5, choices=RESOLUTION_CHOICES, default='hd')
    width           = models.IntegerField(default=0)
    height          = models.IntegerField(default=0)
    is_premium      = models.BooleanField(default=False)
    is_featured     = models.BooleanField(default=False)
    is_published    = models.BooleanField(default=True)
    views_count     = models.IntegerField(default=0)
    downloads_count = models.IntegerField(default=0)
    uploaded_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta: ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug, n = base, 1
            while Image.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self): return self.title


class ImageComment(models.Model):
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    image     = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='comments')
    text      = models.TextField()
    created_at= models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']
