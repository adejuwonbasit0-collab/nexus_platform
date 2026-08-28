from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0009_fix_escaped_unicode_genre_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='track',
            name='cover_image_url',
            field=models.URLField(blank=True, max_length=500, help_text='Direct link to cover art. Used automatically when no uploaded/downloaded cover_image is set — the visitor\'s browser loads it straight from this URL, so it works even when the server itself cannot download the image.'),
        ),
    ]
