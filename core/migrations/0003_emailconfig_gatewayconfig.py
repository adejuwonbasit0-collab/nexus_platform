from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0002_aiprovidersettings_notification')]
    operations = [
        migrations.CreateModel(
            name='EmailConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('backend', models.CharField(choices=[('smtp','SMTP (Custom)'),('sendgrid','SendGrid'),('mailgun','Mailgun'),('ses','Amazon SES'),('console','Console (dev only)')], default='smtp', max_length=20)),
                ('host', models.CharField(blank=True, default='smtp.gmail.com', max_length=300)),
                ('port', models.IntegerField(default=587)),
                ('encryption', models.CharField(choices=[('tls','TLS (STARTTLS — port 587)'),('ssl','SSL (port 465)'),('none','None (port 25)')], default='tls', max_length=10)),
                ('username', models.CharField(blank=True, max_length=300)),
                ('password', models.CharField(blank=True, max_length=500)),
                ('from_email', models.EmailField(blank=True, default='noreply@example.com', max_length=254)),
                ('from_name', models.CharField(blank=True, default='NEXUS', max_length=200)),
                ('is_active', models.BooleanField(default=False)),
                ('api_key', models.CharField(blank=True, max_length=500)),
                ('test_recipient', models.EmailField(blank=True, max_length=254)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Email Configuration'},
        ),
        migrations.CreateModel(
            name='GatewayConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gateway', models.CharField(choices=[('paystack','Paystack'),('stripe','Stripe'),('flutterwave','Flutterwave'),('wave','Wave'),('bank','Bank Transfer / Manual')], max_length=20, unique=True)),
                ('is_active', models.BooleanField(default=False)),
                ('is_test_mode', models.BooleanField(default=True)),
                ('public_key', models.CharField(blank=True, max_length=500)),
                ('secret_key', models.CharField(blank=True, max_length=500)),
                ('webhook_secret', models.CharField(blank=True, max_length=500)),
                ('extra', models.JSONField(blank=True, default=dict)),
                ('currency', models.CharField(default='NGN', max_length=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Gateway Config'},
        ),
    ]
