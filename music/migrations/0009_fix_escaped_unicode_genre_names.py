import re
from django.db import migrations


def fix_escaped_unicode(apps, schema_editor):
    Genre = apps.get_model('music', 'Genre')
    Track = apps.get_model('music', 'Track')

    def clean(s):
        if not s or '\\u' not in s:
            return s
        def repl(m):
            try:
                return chr(int(m.group(1), 16))
            except Exception:
                return m.group(0)
        return re.sub(r'\\u([0-9a-fA-F]{4})', repl, s)

    for g in Genre.objects.all():
        cleaned = clean(g.name)
        if cleaned != g.name:
            # Avoid unique-constraint collisions if the cleaned name
            # already exists as a separate genre row.
            if Genre.objects.filter(name=cleaned).exclude(pk=g.pk).exists():
                continue
            g.name = cleaned
            g.save(update_fields=['name'])

    for t in Track.objects.filter(is_fetched=True):
        new_title = clean(t.title)
        if new_title != t.title:
            t.title = new_title
            t.save(update_fields=['title'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0008_track_banner_image_track_fetch_source_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_escaped_unicode, noop),
    ]
