"""
python manage.py update_trends

Schedule daily with cron:
  0 2 * * * /path/to/venv/bin/python /path/to/manage.py update_trends

What it does
  - Decay-weighted trend score for every Track and Artist
  - Picks Song of the Day (top scoring track, rotated daily)
  - Writes TrendingSnapshot rows (keeps 30 days of history)
  - Cleans up snapshots older than 30 days
"""
import math
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from music.models import Track, Artist, Album, TrendingSnapshot


def _decay(value, days_old, half_life=7):
    """Exponential half-life decay."""
    return float(value) * math.exp(-0.693 * max(0, days_old) / half_life)


class Command(BaseCommand):
    help = 'Recalculate music trend scores, set Song of the Day, update TrendingSnapshot'

    def handle(self, *args, **options):
        now   = timezone.now()
        today = now.date()

        self.stdout.write(self.style.MIGRATE_HEADING('📊 Updating music trends…'))

        # ── 1. Reset Song of the Day flag ────────────────────────────────────
        Track.objects.filter(is_published=True).update(is_song_of_day=False)

        # ── 2. Score every published track ───────────────────────────────────
        top_score = 0.0
        top_track = None
        tracks = list(Track.objects.filter(is_published=True))

        for t in tracks:
            age = (now - t.created_at).days
            score = (
                _decay(t.plays_count * 1.0, age, half_life=7) +
                _decay(t.downloads_count * 2.5, age, half_life=10) +
                _decay(t.likes_count * 3.0, age, half_life=5)
            )
            t.trend_score = round(score, 4)
            t.save(update_fields=['trend_score'])
            if score > top_score:
                top_score = score
                top_track = t

        if top_track:
            top_track.is_song_of_day = True
            top_track.save(update_fields=['is_song_of_day'])
            self.stdout.write(f'  🎵 Song of the Day → "{top_track.title}" by {top_track.artist.name}')

        # ── 3. Score every artist ────────────────────────────────────────────
        for a in Artist.objects.all():
            artist_score = sum(
                t.trend_score
                for t in a.tracks.filter(is_published=True)
            )
            recent_plays = (
                a.tracks.filter(
                    is_published=True,
                    updated_at__gte=now - timedelta(days=30),
                ).aggregate(total=Sum('plays_count'))['total'] or 0
            )
            a.trend_score       = round(artist_score, 4)
            a.monthly_listeners = recent_plays
            a.save(update_fields=['trend_score', 'monthly_listeners'])

        # ── 4. Clean old snapshots ───────────────────────────────────────────
        deleted, _ = TrendingSnapshot.objects.filter(
            snapshot_date__lt=today - timedelta(days=30)
        ).delete()
        if deleted:
            self.stdout.write(f'  🗑  Removed {deleted} old snapshot rows')

        # ── 5. Write today's snapshot ────────────────────────────────────────
        top_tracks  = Track.objects.filter(is_published=True).order_by('-trend_score')[:20]
        top_artists = Artist.objects.order_by('-trend_score')[:10]

        for rank, t in enumerate(top_tracks, 1):
            TrendingSnapshot.objects.update_or_create(
                content_type='track',
                object_id=t.pk,
                snapshot_date=today,
                defaults={'score': t.trend_score, 'rank': rank},
            )

        for rank, a in enumerate(top_artists, 1):
            TrendingSnapshot.objects.update_or_create(
                content_type='artist',
                object_id=a.pk,
                snapshot_date=today,
                defaults={'score': a.trend_score, 'rank': rank},
            )

        self.stdout.write(self.style.SUCCESS(
            f'✅  Done — {len(tracks)} tracks · {Artist.objects.count()} artists scored'
        ))
