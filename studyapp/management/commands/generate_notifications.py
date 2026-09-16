from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from studyapp.services.notifications import generate_user_notifications


class Command(BaseCommand):
    help = 'Generate idempotent deadline and planner notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int)
        parser.add_argument('--horizon-days', type=int, default=1)

    def handle(self, *args, **options):
        user_model = get_user_model()
        users = user_model.objects.filter(is_active=True)
        if options.get('user_id'):
            users = users.filter(pk=options['user_id'])
        total = 0
        for user in users.iterator():
            generated = generate_user_notifications(
                user,
                horizon_days=options['horizon_days'],
            )
            total += len(generated)
        self.stdout.write(self.style.SUCCESS(f'Generated {total} notification(s).'))
