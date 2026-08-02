from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0008_movie_fetch_source_movie_is_fetched'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='cast_json',
            field=models.TextField(blank=True, help_text='JSON list of cast members: [{"name","character","photo_url"}, ...] — populated automatically from TMDB on import/fetch.'),
        ),
    ]
