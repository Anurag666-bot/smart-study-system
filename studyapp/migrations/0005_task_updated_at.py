from django.db import migrations, models


def backfill_updated_at(apps, schema_editor):
    """Use creation time as a compatibility value for existing tasks."""
    Task = apps.get_model('studyapp', 'Task')
    for task in Task.objects.only('pk', 'created_at').iterator():
        Task.objects.filter(pk=task.pk).update(updated_at=task.created_at)


class Migration(migrations.Migration):
    dependencies = [
        ('studyapp', '0004_activitylog'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='updated_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(backfill_updated_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='task',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
