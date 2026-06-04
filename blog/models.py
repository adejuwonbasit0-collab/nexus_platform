from django.db import models
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


class Post(models.Model):
    STATUS = [('draft','Draft'),('published','Published')]
    title        = models.CharField(max_length=400)
    slug         = models.SlugField(unique=True, blank=True)
    author       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    category     = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    tags         = models.ManyToManyField(Tag, blank=True)
    featured_img = models.ImageField(upload_to='blog/covers/', null=True, blank=True)
    content      = models.TextField()
    excerpt      = models.TextField(blank=True, max_length=500)
    status       = models.CharField(max_length=20, choices=STATUS, default='draft')
    is_featured  = models.BooleanField(default=False)
    is_ai_generated = models.BooleanField(default=False)
    views_count  = models.IntegerField(default=0)
    likes_count  = models.IntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta: ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug, n = base, 1
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        if not self.excerpt and self.content:
            self.excerpt = self.content[:400].rsplit(' ',1)[0] + '…'
        super().save(*args, **kwargs)

    def __str__(self): return self.title


class Comment(models.Model):
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blog_comments')
    post      = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    parent    = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    text      = models.TextField()
    is_flagged= models.BooleanField(default=False)
    created_at= models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['created_at']


class PostLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    class Meta: unique_together = [('user','post')]


class AIBlogUsage(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post       = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL)
    topic      = models.CharField(max_length=300)
    tokens_used= models.IntegerField(default=0)
    month      = models.CharField(max_length=7)  # 'YYYY-MM'
    created_at = models.DateTimeField(auto_now_add=True)
