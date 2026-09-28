from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

DEFAULT_PASSWORD = '12345678'


class Command(BaseCommand):
    help = 'Reset the password of every user account to a single known value.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default=DEFAULT_PASSWORD,
            help=f'Password to set for every user. Defaults to {DEFAULT_PASSWORD!r}.',
        )

    def handle(self, *args, **options):
        password = options['password']
        user_model = get_user_model()

        users = user_model.objects.all().order_by('pk')
        total = users.count()
        if not total:
            self.stdout.write(self.style.WARNING('No user accounts found.'))
            return

        # set_password re-hashes, so the raw value is never stored in the DB.
        for user in users:
            user.set_password(password)
            user.save(update_fields=['password'])

        self.stdout.write(self.style.SUCCESS(
            f'Done: reset the password of {total} user account(s) to {password!r}.'
        ))
