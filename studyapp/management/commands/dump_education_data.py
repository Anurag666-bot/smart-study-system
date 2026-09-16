from django.core.management.base import BaseCommand, CommandError
from django.core import serializers
from django.apps import apps
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Dump education-related data (subjects, students, tasks, notes, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            default='json',
            choices=['json', 'xml', 'yaml'],
            help='Format to serialize data (default: json)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='File to output the data to (default: stdout)'
        )
        parser.add_argument(
            '--indent',
            type=int,
            default=2,
            help='Indent level for JSON output (default: 2)'
        )
        parser.add_argument(
            '--timestamp',
            action='store_true',
            help='Add timestamp to output filename'
        )
        parser.add_argument(
            '--include-users',
            action='store_true',
            help='Include user/auth data along with educational data'
        )

    def handle(self, *args, **options):
        format = options['format']
        output_file = options['output']
        indent = options['indent']
        add_timestamp = options['timestamp']
        include_users = options['include_users']

        # Define the core educational models to dump
        educational_models = [
            'studyapp.Subject',
            'studyapp.Topic',
            'studyapp.StudentSubject',
            'studyapp.TeacherSubject',
            'studyapp.Task',
            'studyapp.TaskComment',
            'studyapp.TaskAttachment',
            'studyapp.Note',
            'studyapp.NoteAttachment',
            'studyapp.StudyPlan',
            'studyapp.StudySession',
            'studyapp.Goal',
            'studyapp.Exam',
            'studyapp.ExamResult',
            'studyapp.PlannerEvent',
            'studyapp.EventReminder',
        ]

        # Optionally include user/auth data
        if include_users:
            user_models = [
                'auth.User',
                'studyapp.Profile',
                'studyapp.Role',
                'studyapp.UserRole',
            ]
            educational_models.extend(user_models)

        # Add timestamp to filename if requested
        if output_file and add_timestamp:
            name, ext = os.path.splitext(output_file)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"{name}_{timestamp}{ext}"

        if not educational_models:
            raise CommandError('No models to dump')

        self.stdout.write(
            self.style.SUCCESS(
                f'Dumping education data for {len(educational_models)} model(s) in {format} format...'
            )
        )

        # Prepare output
        try:
            if output_file:
                with open(output_file, 'w') as f:
                    for model_string in educational_models:
                        try:
                            app_label, model_name = model_string.split('.')
                            model = apps.get_model(app_label, model_name)
                            count = model.objects.count()
                            if count > 0:  # Only write if there's data
                                data = serializers.serialize(
                                    format,
                                    model.objects.all().iterator(),
                                    indent=indent if format == 'json' else None
                                )
                                f.write(data)
                                if format == 'json':
                                    f.write('\n')  # Add newline between models
                                self.stdout.write(
                                    f'  Dumped {count} records from {model_string}'
                                )
                            else:
                                self.stdout.write(
                                    f'  Skipped {model_string} (no records)'
                                )
                        except LookupError:
                            raise CommandError(f'Unknown model: {model_string}')
                        except ValueError:
                            raise CommandError(f'Invalid model format: {model_string}. Use app_label.ModelName')

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully dumped education data to {output_file}'
                    )
                )
            else:
                # Output to stdout
                for model_string in educational_models:
                    try:
                        app_label, model_name = model_string.split('.')
                        model = apps.get_model(app_label, model_name)
                        count = model.objects.count()
                        if count > 0:  # Only output if there's data
                            data = serializers.serialize(
                                format,
                                model.objects.all().iterator(),
                                indent=indent if format == 'json' else None
                            )
                            self.stdout.write(data)
                            if format == 'json':
                                self.stdout.write('')  # Add newline between models
                            self.stdout.write(
                                f'  Dumped {count} records from {model_string}',
                                stderr=True  # Send to stderr so it doesn't mix with serialized data
                            )
                        else:
                            self.stdout.write(
                                f'  Skipped {model_string} (no records)',
                                stderr=True
                            )
                    except LookupError:
                        raise CommandError(f'Unknown model: {model_string}')
                    except ValueError:
                        raise CommandError(f'Invalid model format: {model_string}. Use app_label.ModelName')

        except IOError as e:
            raise CommandError(f'Error writing to output file: {e}')