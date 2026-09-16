from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from studyapp.services.achievements import evaluate_user_achievements


class Command(BaseCommand):
    help = 'Evaluate and award data-backed achievements idempotently.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int)

    def handle(self, *args, **options):
        user_model = get_user_model()
        users = user_model.objects.filter(is_active=True)
        if options.get('user_id'):
            users = users.filter(pk=options['user_id'])
        total = 0
        for user in users.iterator():
            total += len(evaluate_user_achievements(user))
        self.stdout.write(self.style.SUCCESS(f'Awarded {total} achievement(s).'))
