from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0002_subscriptionplan_user_ai_credits_reset_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ViewHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_type', models.CharField(choices=[('movie', 'Movie'), ('episode', 'Episode'), ('track', 'Track'), ('image', 'Image'), ('short', 'Short')], max_length=20)),
                ('object_id', models.IntegerField()),
                ('title', models.CharField(blank=True, max_length=255)),
                ('thumbnail_url', models.CharField(blank=True, max_length=500)),
                ('url', models.CharField(blank=True, max_length=500)),
                ('viewed_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='view_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-viewed_at'],
                'unique_together': {('user', 'content_type', 'object_id')},
            },
        ),
    ]
