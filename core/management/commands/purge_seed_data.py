"""
Management command: python manage.py purge_seed_data

Removes ALL AI-generated, seeded, or test content from the database.
Only keeps content that was manually created by real admin/creator users.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete all AI-generated, seeded, and test content from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        if not options['yes']:
            confirm = input(
                '\n⚠️  This will permanently delete ALL AI-generated and seed data.\n'
                'Are you sure? Type "yes" to continue: '
            )
            if confirm.strip().lower() != 'yes':
                self.stdout.write(self.style.WARNING('Cancelled.'))
                return

        total = 0

        # 1. Content app — delete AI-generated Content objects
        try:
            from content.models import Content
            qs = Content.objects.filter(is_ai_generated=True)
            n = qs.count()
            qs.delete()
            self.stdout.write(f'  Deleted {n} AI-generated Content records')
            total += n
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Content: {e}'))

        # 2. Blog posts — delete AI-generated posts
        try:
            from blog.models import Post
            qs = Post.objects.filter(is_ai_generated=True)
            n = qs.count()
            qs.delete()
            self.stdout.write(f'  Deleted {n} AI-generated Blog posts')
            total += n
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Blog: {e}'))

        # 3. Delete any content created by the system/anonymous user
        try:
            from content.models import Content
            from accounts.models import User
            # Delete content with no creator
            qs = Content.objects.filter(creator__isnull=True)
            n = qs.count()
            qs.delete()
            self.stdout.write(f'  Deleted {n} orphaned Content records (no creator)')
            total += n
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Orphaned content: {e}'))

        # 4. AI-generated images (if images app has a flag)
        try:
            from images.models import Image
            if hasattr(Image, 'is_ai_generated'):
                qs = Image.objects.filter(is_ai_generated=True)
                n = qs.count()
                qs.delete()
                self.stdout.write(f'  Deleted {n} AI-generated Images')
                total += n
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Images: {e}'))

        # 5. Clear the homepage cache so fresh data shows immediately
        try:
            from django.core.cache import cache
            cache.delete('homepage_content_v3')
            cache.delete('platform_stats_v3')
            self.stdout.write('  Cleared homepage cache')
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Done! Deleted {total} seed/AI records total.'
        ))