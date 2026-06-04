"""python manage.py set_admin <username>"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Set a user as admin'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)

    def handle(self, *args, **options):
        from accounts.models import User
        username = options['username']
        try:
            user = User.objects.get(username=username)
            user.role     = 'admin'
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'✅ {username} is now an admin.'))
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" not found.')
