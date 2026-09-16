#!/usr/bin/env python3
import os
import sys
import django
from django.conf import settings

# Add the project directory to the path
sys.path.append('/home/anurag/Desktop/smart_study_system')

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Setup Django
django.setup()

from studyapp import models
from django.apps import apps

# Get the studyapp app config
app_config = apps.get_app_config('studyapp')

# Get all models in the app
app_models = app_config.get_models()

# We'll output a markdown table for each model
print("# Database Schema Design for Smart Study System\n")
print("This schema is derived from the Django models in `studyapp/models.py`.\n")

for model in app_models:
    table_name = model._meta.db_table
    print(f"## Table: `{table_name}`")
    print(f"*Model: {model.__name__}*\n")

    print("| Column | Type | Null | Key | Default | Extra |")
    print("|--------|------|------|-----|---------|-------|")

    # Get local fields (not including inherited ones from abstract base classes unless concrete)
    for field in model._meta.get_fields():
        if field.auto_created and not field.concrete:
            # Skip reverse foreign keys and many-to-many fields for now
            continue
        if field.is_relation and field.many_to_many:
            # Skip many-to-many fields (they have a separate table)
            continue

        # Get field attributes
        col_name = field.name
        # Determine SQL type (simplified mapping)
        if hasattr(field, 'get_internal_type'):
            internal_type = field.get_internal_type()
        else:
            internal_type = field.__class__.__name__

        # Map Django field types to generic SQL types (simplified)
        # We'll handle special cases for parameters
        if internal_type == 'CharField':
            col_type = f"VARCHAR({field.max_length})"
        elif internal_type == 'TextField':
            col_type = 'TEXT'
        elif internal_type == 'IntegerField':
            col_type = 'INT'
        elif internal_type == 'BigIntegerField':
            col_type = 'BIGINT'
        elif internal_type == 'FloatField':
            col_type = 'FLOAT'
        elif internal_type == 'BooleanField':
            col_type = 'BOOLEAN'
        elif internal_type == 'DateField':
            col_type = 'DATE'
        elif internal_type == 'DateTimeField':
            col_type = 'DATETIME'
        elif internal_type == 'TimeField':
            col_type = 'TIME'
        elif internal_type == 'DecimalField':
            col_type = f"DECIMAL({field.max_digits},{field.decimal_places})"
        elif internal_type == 'ForeignKey':
            col_type = 'INT'  # Simplified, should reference another table
        elif internal_type == 'OneToOneField':
            col_type = 'INT'
        elif internal_type == 'FileField':
            col_type = f"VARCHAR({field.max_length})"
        elif internal_type == 'JSONField':
            col_type = 'JSON'
        elif internal_type == 'AutoField':
            col_type = 'INT AUTO_INCREMENT'
        elif internal_type == 'BigAutoField':
            col_type = 'BIGINT AUTO_INCREMENT'
        else:
            # Fallback
            col_type = internal_type

        # Nullability
        null = "NO" if not field.null else "YES"

        # Key
        key = ""
        if field.primary_key:
            key = "PRI"
        elif field.unique:
            key = "UNI"

        # Default
        default = ""
        if not field.null and field.has_default() and field.default is not None:
            # Handle callable defaults, etc. - simplified
            if callable(field.default):
                default = "<callable>"
            else:
                default = str(field.default)
        elif field.null:
            default = "NULL"

        # Extra
        extra = ""
        if field.auto_created and not field.primary_key:
            # This is a bit tricky: auto_created is True for fields that Django creates implicitly (like the id field in a OneToOneField that is the primary key?)
            # We'll just not add auto_increment here; we already set it in col_type for AutoField/B
            pass
        if field.primary_key and ('AUTO_INCREMENT' in col_type or 'auto_increment' in col_type.lower()):
            extra = "auto_increment"
        if field.unique and not field.primary_key:
            extra += " unique" if extra else "unique"

        print(f"| {col_name} | {col_type} | {null} | {key} | {default} | {extra} |")

    # Print foreign key relationships
    print("\n**Relationships:**")
    for field in model._meta.get_fields():
        if field.is_relation and field.related_model and field.concrete and not field.auto_created:
            if field.one_to_one or field.many_to_one:
                related_table = field.related_model._meta.db_table
                print(f"- {field.name} → {related_table}.{field.target_field.name}")
            elif field.one_to_many:
                related_table = field.related_model._meta.db_table
                print(f"- {field.name} ← {related_table}.{field.field.name}")

    # Print constraints if any
    constraints = model._meta.constraints
    if constraints:
        print("\n**Constraints:**")
        for constraint in constraints:
            print(f"- {constraint.name}: {constraint.__class__.__name__}")

    # Print indexes if any
    indexes = model._meta.indexes
    if indexes:
        print("\n**Indexes:**")
        for index in indexes:
            print(f"- {index.name}: {index.fields}")

    print("\n---\n")