from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def bootstrap_roles_and_assignments(apps, schema_editor):
    Role = apps.get_model('studyapp', 'Role')
    Profile = apps.get_model('studyapp', 'Profile')
    UserRole = apps.get_model('studyapp', 'UserRole')
    user_app, user_model = settings.AUTH_USER_MODEL.split('.', 1)
    User = apps.get_model(user_app, user_model)

    role_defaults = {
        'student': {
            'name': 'Student',
            'description': 'Self-service study and personal academic records.',
        },
        'teacher': {
            'name': 'Teacher',
            'description': 'Scoped teaching and read-only student progress access.',
        },
        'administrator': {
            'name': 'Administrator',
            'description': 'Application administration and audit access.',
        },
    }
    roles = {
        code: Role.objects.get_or_create(code=code, defaults=defaults)[0]
        for code, defaults in role_defaults.items()
    }

    for user in User.objects.all().iterator():
        profile, _ = Profile.objects.get_or_create(user_id=user.pk)
        role_code = 'administrator' if (user.is_staff or user.is_superuser) else 'student'
        UserRole.objects.get_or_create(
            profile_id=profile.pk,
            role_id=roles[role_code].pk,
        )


def leave_assignments_untouched(apps, schema_editor):
    """Role data is additive; reverse migration intentionally does not delete it."""
    return None


class Migration(migrations.Migration):
    dependencies = [
        ('studyapp', '0005_task_updated_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=32, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_roles', to='studyapp.profile')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='user_roles', to='studyapp.role')),
            ],
            options={
                'indexes': [models.Index(fields=['profile', 'role'], name='idx_userrole_profile_role')],
                'constraints': [models.UniqueConstraint(fields=('profile', 'role'), name='uniq_profile_role')],
            },
        ),
        migrations.RunPython(bootstrap_roles_and_assignments, leave_assignments_untouched),
    ]
