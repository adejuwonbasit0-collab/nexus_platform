from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('content', '0001_initial'),
    ]
    operations = [
        migrations.AddField(
            model_name='content',
            name='thumbnail_url',
            field=models.URLField(blank=True, help_text='External thumbnail URL for URL-uploaded content.'),
        ),
    ]
