"""
One-time repair for shorts imported before the escapejs data-payload bug was
fixed. That bug produced literal backslash-u-0-0-2-D sequences in place of
hyphens (very common in YouTube video IDs and CDN URLs), which broke
playback with a "This video is unavailable" YouTube error. This scans
existing rows for that literal sequence and un-escapes it back to a real
hyphen. Safe to run more than once — it's a no-op on rows that don't have
the corrupted sequence.

Usage: python manage.py fix_escaped_shorts
"""
from django.core.management.base import BaseCommand
from shorts.models import Short


class Command(BaseCommand):
    help = 'Repairs shorts whose video_url/description/title got corrupted by the escapejs data-payload bug (literal \\u002D instead of a hyphen).'

    def handle(self, *args, **options):
        BROKEN = '\\u002D'
        fixed = 0
        for s in Short.objects.all():
            changed = False
            if BROKEN in (s.video_url or ''):
                s.video_url = s.video_url.replace(BROKEN, '-')
                changed = True
            if BROKEN in (s.title or ''):
                s.title = s.title.replace(BROKEN, '-')
                changed = True
            if BROKEN in (s.description or ''):
                s.description = s.description.replace(BROKEN, '-')
                changed = True
            if changed:
                s.save(update_fields=['video_url', 'title', 'description'])
                fixed += 1
        if fixed:
            self.stdout.write(self.style.SUCCESS(f'Repaired {fixed} short(s).'))
        else:
            self.stdout.write('No corrupted shorts found — nothing to repair.')
