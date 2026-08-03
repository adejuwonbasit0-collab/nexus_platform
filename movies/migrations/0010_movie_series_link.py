import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0009_movie_cast_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='series',
            field=models.ForeignKey(blank=True, help_text='Optional — link this movie to a Series so it shows up on that Series page (for franchises/collections, separate from Season/Episode content).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movies', to='movies.series'),
        ),
        migrations.AddField(
            model_name='movie',
            name='series_order',
            field=models.IntegerField(default=0, help_text='Display order within the series (e.g. 1 for the first film).'),
        ),
    ]
