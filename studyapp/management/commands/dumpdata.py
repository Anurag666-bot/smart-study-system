from django.core.management.base import BaseCommand, CommandError
from django.core import serializers
from django.apps import apps
import json
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Dump data from the database for specified models or all models'

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
            '--exclude',
            action='append',
            default=[],
            help='Exclude specific models (app_label.ModelName format)'
        )
        parser.add_argument(
            '--include',
            action='append',
            default=[],
            help='Include only specific models (app_label.ModelName format)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Dump all models including those from other apps'
        )
        parser.add_argument(
            '--timestamp',
            action='store_true',
            help='Add timestamp to output filename'
        )

    def handle(self, *args, **options):
        format = options['format']
        output_file = options['output']
        indent = options['indent']
        exclude_list = options['exclude']
        include_list = options['include']
        dump_all = options['all']
        add_timestamp = options['timestamp']

        # Determine which models to dump
        if dump_all:
            # Get all models from all apps
            models_to_dump = []
            for model in apps.get_models():
                model_name = f"{model._meta.app_label}.{model._meta.model_name}"
                models_to_dump.append(model_name)
        else:
            # Default to studyapp models if not specified
            if not include_list:
                include_list = ['studyapp.' + model._meta.model_name
                              for model in apps.get_app_config('studyapp').get_models()]

            models_to_dump = include_list

        # Apply exclusions
        if exclude_list:
            models_to_dump = [model for model in models_to_dump
                            if model not in exclude_list]

        if not models_to_dump:
            raise CommandError('No models to dump after applying filters')

        self.stdout.write(
            self.style.SUCCESS(
                f'Dumping data for {len(models_to_dump)} model(s) in {format} format...'
            )
        )

        # Prepare output
        if output_file and add_timestamp:
            # Add timestamp to filename
            name, ext = os.path.splitext(output_file)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"{name}_{timestamp}{ext}"

        # Serialize data
        try:
            if output_file:
                with open(output_file, 'w') as f:
                    for model_string in models_to_dump:
                        try:
                            app_label, model_name = model_string.split('.')
                            model = apps.get_model(app_label, model_name)
                            data = serializers.serialize(
                                format,
                                model.objects.all().iterator(),
                                indent=indent if format == 'json' else None
                            )
                            f.write(data)
                            if format == 'json':
                                f.write('\n')  # Add newline between models
                            self.stdout.write(
                                f'  Dumped {model.objects.count()} records from {model_string}'
                            )
                        except LookupError:
                            raise CommandError(f'Unknown model: {model_string}')
                        except ValueError:
                            raise CommandError(f'Invalid model format: {model_string}. Use app_label.ModelName')

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully dumped data to {output_file}'
                    )
                )
            else:
                # Output to stdout
                for model_string in models_to_dump:
                    try:
                        app_label, model_name = model_string.split('.')
                        model = apps.get_model(app_label, model_name)
                        data = serializers.serialize(
                            format,
                            model.objects.all().iterator(),
                            indent=indent if format == 'json' else None
                        )
                        self.stdout.write(data)
                        if format == 'json':
                            self.stdout.write('')  # Add newline between models
                        self.stdout.write(
                            f'  Dumped {model.objects.count()} records from {model_string}',
                            stderr=True  # Send to stderr so it doesn't mix with serialized data
                        )
                    except LookupError:
                        raise CommandError(f'Unknown model: {model_string}')
                    except ValueError:
                        raise CommandError(f'Invalid model format: {model_string}. Use app_label.ModelName')

        except IOError as e:
            raise CommandError(f'Error writing to output file: {e}')