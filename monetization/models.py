from django.db import models
from django.conf import settings


class PaymentSettings(models.Model):
    """Admin-configurable Paystack credentials – never hardcoded."""
    public_key  = models.CharField(max_length=300, blank=True,
                                   help_text='Paystack public key (pk_test_… or pk_live_…)')
    currency    = models.CharField(max_length=10, default='NGN')
    is_active   = models.BooleanField(default=False)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Payment Settings'
        verbose_name_plural = 'Payment Settings'

    def __str__(self):
        return f'Paystack – {"active" if self.is_active else "inactive"}'

    @property
    def is_test_key(self):
        return self.public_key.startswith('pk_test_')

    @classmethod
    def get_active(cls):
        return cls.objects.filter(is_active=True).first()


class CommissionSettings(models.Model):
    content_type = models.CharField(max_length=20)
    action = models.CharField(
        max_length=20,
        choices=[('view', 'View'), ('download', 'Download'), ('purchase', 'Purchase')]
    )
    amount       = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    is_percentage = models.BooleanField(default=False)

    class Meta:
        unique_together = [('content_type', 'action')]


class Earning(models.Model):
    creator    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earnings'
    )
    content    = models.ForeignKey(
        'content.Content', on_delete=models.SET_NULL, null=True, blank=True
    )
    amount     = models.DecimalField(max_digits=10, decimal_places=2)
    reason     = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class Payment(models.Model):
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content     = models.ForeignKey(
        'content.Content', on_delete=models.SET_NULL, null=True, blank=True
    )
    amount      = models.DecimalField(max_digits=10, decimal_places=2)
    status      = models.CharField(
        max_length=20, default='pending',
        choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')]
    )
    payment_ref   = models.CharField(max_length=200, blank=True)
    paystack_ref  = models.CharField(max_length=200, blank=True)   # reference from Paystack
    currency      = models.CharField(max_length=10, default='NGN')
    created_at    = models.DateTimeField(auto_now_add=True)
    verified_at   = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Payment {self.pk} – {self.status}'


# ═══════════════════════════════════════════════════════════════
# EXTENDED MONETIZATION MODELS — Wallet, Withdrawals, Coupons,
# Affiliates, Invoices, Webhook Events
# ═══════════════════════════════════════════════════════════════

class Wallet(models.Model):
    """Per-user balance ledger."""
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                            related_name='wallet')
    balance          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_balance  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawn  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency         = models.CharField(max_length=5, default='NGN')
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['user'])]

    def __str__(self):
        return f'Wallet({self.user.username}) — {self.currency} {self.balance}'

    def credit(self, amount, reason='', reference=''):
        """Atomically credit the wallet and record the transaction."""
        from django.db import transaction
        from decimal import Decimal
        amount = Decimal(str(amount))
        with transaction.atomic():
            Wallet.objects.filter(pk=self.pk).update(
                balance=models.F('balance') + amount,
                total_earned=models.F('total_earned') + amount,
            )
            self.refresh_from_db()
            WalletTransaction.objects.create(
                wallet=self, txn_type='credit', amount=amount,
                reason=reason, reference=reference,
                balance_after=self.balance,
            )

    def debit(self, amount, reason='', reference=''):
        """Atomically debit the wallet, raises ValueError if insufficient funds."""
        from django.db import transaction
        from decimal import Decimal
        amount = Decimal(str(amount))
        with transaction.atomic():
            # Lock and check balance
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            if wallet.balance < amount:
                raise ValueError(f'Insufficient funds: balance {wallet.balance}, requested {amount}')
            Wallet.objects.filter(pk=self.pk).update(
                balance=models.F('balance') - amount,
                total_withdrawn=models.F('total_withdrawn') + amount,
            )
            self.refresh_from_db()
            WalletTransaction.objects.create(
                wallet=self, txn_type='debit', amount=amount,
                reason=reason, reference=reference,
                balance_after=self.balance,
            )


class WalletTransaction(models.Model):
    TXN_TYPES = [('credit','Credit'),('debit','Debit'),('refund','Refund'),('fee','Platform Fee')]
    wallet       = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    txn_type     = models.CharField(max_length=10, choices=TXN_TYPES)
    amount       = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after= models.DecimalField(max_digits=12, decimal_places=2)
    reason       = models.CharField(max_length=300, blank=True)
    reference    = models.CharField(max_length=200, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.txn_type} {self.amount} ({self.wallet.user.username})'


class WithdrawalRequest(models.Model):
    STATUSES = [
        ('pending','Pending Review'),('approved','Approved'),
        ('processing','Processing'),('completed','Completed'),('rejected','Rejected'),
    ]
    METHODS = [('bank_transfer','Bank Transfer'),('paystack','Paystack'),('manual','Manual')]
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name='withdrawal_requests')
    wallet        = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    amount        = models.DecimalField(max_digits=12, decimal_places=2)
    method        = models.CharField(max_length=20, choices=METHODS, default='bank_transfer')
    bank_name     = models.CharField(max_length=200, blank=True)
    account_number= models.CharField(max_length=30, blank=True)
    account_name  = models.CharField(max_length=200, blank=True)
    status        = models.CharField(max_length=20, choices=STATUSES, default='pending')
    admin_note    = models.TextField(blank=True)
    processed_by  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='processed_withdrawals')
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Withdrawal #{self.pk} — {self.user.username} — {self.amount}'


class Invoice(models.Model):
    STATUSES = [('draft','Draft'),('issued','Issued'),('paid','Paid'),('void','Void')]
    payment     = models.OneToOneField(Payment, on_delete=models.CASCADE,
                                       null=True, blank=True, related_name='invoice')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    subtotal    = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total       = models.DecimalField(max_digits=12, decimal_places=2)
    currency    = models.CharField(max_length=5, default='NGN')
    status      = models.CharField(max_length=20, choices=STATUSES, default='draft')
    line_items  = models.JSONField(default=list)
    issued_at   = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Invoice #{self.invoice_number} — {self.user.username}'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            import uuid
            from django.utils import timezone
            self.invoice_number = f'NX-{timezone.now().year}-{str(uuid.uuid4())[:8].upper()}'
        super().save(*args, **kwargs)


class Coupon(models.Model):
    DISCOUNT_TYPES = [('percentage','Percentage'),('fixed','Fixed Amount')]
    code         = models.CharField(max_length=50, unique=True)
    description  = models.CharField(max_length=300, blank=True)
    discount_type= models.CharField(max_length=15, choices=DISCOUNT_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=8, decimal_places=2)
    max_uses     = models.IntegerField(default=0, help_text='0 = unlimited')
    used_count   = models.IntegerField(default=0)
    min_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text='Minimum order amount')
    is_active    = models.BooleanField(default=True)
    valid_from   = models.DateTimeField(null=True, blank=True)
    valid_until  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.code} ({self.discount_type}: {self.discount_value})'

    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False, 'Coupon is inactive.'
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False, 'Coupon usage limit reached.'
        if self.valid_from and now < self.valid_from:
            return False, 'Coupon not yet valid.'
        if self.valid_until and now > self.valid_until:
            return False, 'Coupon has expired.'
        return True, 'Valid'

    def apply(self, amount):
        from decimal import Decimal
        amount = Decimal(str(amount))
        if self.discount_type == 'percentage':
            discount = amount * (self.discount_value / 100)
        else:
            discount = self.discount_value
        return max(Decimal('0'), amount - discount)


class CouponUsage(models.Model):
    coupon     = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    payment    = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    used_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('coupon', 'user')]


class AffiliateLink(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='affiliate_links')
    code       = models.CharField(max_length=30, unique=True)
    commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    clicks     = models.IntegerField(default=0)
    conversions= models.IntegerField(default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Affiliate/{self.code} ({self.user.username})'


class WebhookEvent(models.Model):
    """Idempotent log of all incoming payment webhook events."""
    PROVIDERS = [('paystack','Paystack'),('stripe','Stripe'),('flutterwave','Flutterwave')]
    provider    = models.CharField(max_length=20, choices=PROVIDERS)
    event_type  = models.CharField(max_length=100)
    event_id    = models.CharField(max_length=200, db_index=True)
    payload     = models.JSONField(default=dict)
    processed   = models.BooleanField(default=False)
    error       = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('provider', 'event_id')]
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.provider}/{self.event_type} #{self.event_id}'


class SubscriptionPlan(models.Model):
    """Configurable subscription tiers."""
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(unique=True)
    description = models.CharField(max_length=255, blank=True, default='')
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    currency    = models.CharField(max_length=5, default='NGN')
    interval    = models.CharField(max_length=20,
                                   choices=[('monthly','Monthly'),('yearly','Yearly'),('lifetime','Lifetime')],
                                   default='monthly')
    features    = models.JSONField(default=list, help_text='List of feature strings')
    is_featured = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    paystack_plan_code = models.CharField(max_length=100, blank=True)
    stripe_price_id    = models.CharField(max_length=100, blank=True)
    order       = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'price']

    def __str__(self):
        return f'{self.name} — {self.currency} {self.price}/{self.interval}'