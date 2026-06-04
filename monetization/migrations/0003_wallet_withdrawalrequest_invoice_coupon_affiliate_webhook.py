from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('monetization', '0002_paymentsettings_payment_currency_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Wallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to=settings.AUTH_USER_MODEL)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('pending_balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_earned', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_withdrawn', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('currency', models.CharField(default='NGN', max_length=5)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='WalletTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='monetization.wallet')),
                ('txn_type', models.CharField(choices=[('credit','Credit'),('debit','Debit'),('refund','Refund'),('fee','Platform Fee')], max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('balance_after', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reason', models.CharField(blank=True, max_length=300)),
                ('reference', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='WithdrawalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='withdrawal_requests', to=settings.AUTH_USER_MODEL)),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='monetization.wallet')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('method', models.CharField(choices=[('bank_transfer','Bank Transfer'),('paystack','Paystack'),('manual','Manual')], default='bank_transfer', max_length=20)),
                ('bank_name', models.CharField(blank=True, max_length=200)),
                ('account_number', models.CharField(blank=True, max_length=30)),
                ('account_name', models.CharField(blank=True, max_length=200)),
                ('status', models.CharField(choices=[('pending','Pending Review'),('approved','Approved'),('processing','Processing'),('completed','Completed'),('rejected','Rejected')], default='pending', max_length=20)),
                ('admin_note', models.TextField(blank=True)),
                ('processed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_withdrawals', to=settings.AUTH_USER_MODEL)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('description', models.CharField(blank=True, max_length=300)),
                ('discount_type', models.CharField(choices=[('percentage','Percentage'),('fixed','Fixed Amount')], default='percentage', max_length=15)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=8)),
                ('max_uses', models.IntegerField(default=0)),
                ('used_count', models.IntegerField(default=0)),
                ('min_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('valid_from', models.DateTimeField(blank=True, null=True)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='AffiliateLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='affiliate_links', to=settings.AUTH_USER_MODEL)),
                ('code', models.CharField(max_length=30, unique=True)),
                ('commission_pct', models.DecimalField(decimal_places=2, default=10, max_digits=5)),
                ('clicks', models.IntegerField(default=0)),
                ('conversions', models.IntegerField(default=0)),
                ('total_earned', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='WebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('paystack','Paystack'),('stripe','Stripe'),('flutterwave','Flutterwave')], max_length=20)),
                ('event_type', models.CharField(max_length=100)),
                ('event_id', models.CharField(db_index=True, max_length=200)),
                ('payload', models.JSONField(default=dict)),
                ('processed', models.BooleanField(default=False)),
                ('error', models.TextField(blank=True)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-received_at'], 'unique_together': {('provider', 'event_id')}},
        ),
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(unique=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='NGN', max_length=5)),
                ('interval', models.CharField(choices=[('monthly','Monthly'),('yearly','Yearly'),('lifetime','Lifetime')], default='monthly', max_length=20)),
                ('features', models.JSONField(default=list)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('paystack_plan_code', models.CharField(blank=True, max_length=100)),
                ('stripe_price_id', models.CharField(blank=True, max_length=100)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['order', 'price']},
        ),
    ]
