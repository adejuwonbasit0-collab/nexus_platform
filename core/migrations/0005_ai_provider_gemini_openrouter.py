from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_emailconfig_password_alter_gatewayconfig_extra'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiprovidersettings',
            name='provider',
            field=models.CharField(choices=[('openai', 'OpenAI (DALL-E / GPT)'), ('anthropic', 'Anthropic (Claude)'), ('gemini', 'Google Gemini (2.5 Pro / Flash / Image)'), ('openrouter', 'OpenRouter (gateway to 100+ models)'), ('stability', 'Stability AI')], max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name='aiprovidersettings',
            name='model_name',
            field=models.CharField(blank=True, help_text='e.g. dall-e-3, claude-sonnet-4-5, gemini-2.5-flash, gemini-2.5-flash-image, openai/gpt-4o (OpenRouter model id)', max_length=100),
        ),
        migrations.AddField(
            model_name='aiprovidersettings',
            name='last_test_ok',
            field=models.BooleanField(blank=True, null=True, help_text='Result of the last "Test connection" click in admin.'),
        ),
        migrations.AddField(
            model_name='aiprovidersettings',
            name='last_test_message',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='aiprovidersettings',
            name='last_tested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
