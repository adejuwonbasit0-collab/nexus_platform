# Generated for content slug support

from django.db import migrations, models


def populate_slugs(apps, schema_editor):
    Content = apps.get_model('content', 'Content')
    from django.utils.text import slugify
    seen = set(
        Content.objects.exclude(slug='').values_list('slug', flat=True)
    )
    for obj in Content.objects.filter(slug=''):
        base = slugify(obj.title) or f'content-{obj.pk}'
        slug = base
        i = 1
        while slug in seen:
            i += 1
            slug = f'{base}-{i}'
        seen.add(slug)
        obj.slug = slug
        obj.save(update_fields=['slug'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0002_content_is_published'),
    ]

    operations = [
        migrations.AddField(
            model_name='content',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=220),
        ),
        migrations.RunPython(populate_slugs, noop),
        migrations.AlterField(
            model_name='content',
            name='slug',
            field=models.SlugField(blank=True, max_length=220, unique=True),
        ),
    ]