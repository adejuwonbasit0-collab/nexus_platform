from django.contrib.auth.models import AbstractUser
from django.db import models


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [('free', 'Free'), ('premium', 'Premium'), ('creator_ai', 'Creator AI')]
    name         = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    price        = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    duration_days= models.IntegerField(default=30)
    description  = models.TextField(blank=True)
    features     = models.JSONField(default=list)

    def __str__(self): return self.name


class User(AbstractUser):
    ROLE_CHOICES = [('admin', 'Admin'), ('creator', 'Creator'), ('user', 'User')]
    role            = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    avatar          = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio             = models.TextField(blank=True)
    website         = models.URLField(blank=True)
    followers_count = models.IntegerField(default=0)
    total_earnings  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_verified     = models.BooleanField(default=False)
    # Subscription
    subscription_plan   = models.ForeignKey(SubscriptionPlan, null=True, blank=True, on_delete=models.SET_NULL)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    ai_credits_used     = models.IntegerField(default=0)   # monthly AI blog usage
    ai_credits_reset    = models.DateField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    def is_admin(self):    return self.role == 'admin'
    def is_creator(self):  return self.role in ('admin', 'creator')

    @property
    def is_premium(self):
        from django.utils import timezone
        if self.role == 'admin': return True
        if self.subscription_plan and self.subscription_plan.name in ('premium', 'creator_ai'):
            if self.subscription_expiry and self.subscription_expiry > timezone.now():
                return True
        return False

    @property
    def has_ai_access(self):
        if self.role == 'admin': return True
        return bool(
            self.subscription_plan and
            self.subscription_plan.name == 'creator_ai' and
            self.is_premium
        )

    def __str__(self): return self.username


class Subscription(models.Model):
    STATUS = [('active','Active'),('expired','Expired'),('cancelled','Cancelled')]
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan       = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    status     = models.CharField(max_length=20, choices=STATUS, default='active')
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    payment_ref= models.CharField(max_length=200, blank=True)

    def __str__(self): return f'{self.user.username} – {self.plan.name}'


class SavedContent(models.Model):
    """User's saved/favourited items across all content types."""
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_items')
    content_type = models.CharField(max_length=20)  # movie/music/image/blog
    object_id    = models.IntegerField()
    saved_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'content_type', 'object_id')]


class DownloadHistory(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='download_history')
    content_type = models.CharField(max_length=20)
    object_id    = models.IntegerField()
    file_url     = models.CharField(max_length=500)
    downloaded_at= models.DateTimeField(auto_now_add=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)


# Ensure wallet is auto-created for all new users
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender='accounts.User')
def create_wallet(sender, instance, created, **kwargs):
    if created:
        try:
            from monetization.models import Wallet
            Wallet.objects.get_or_create(user=instance)
        except Exception:
            pass
