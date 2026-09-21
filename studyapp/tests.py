from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from .forms import AttendanceForm, StudyPlanForm
from .models import (
    ActivityLog,
    Attendance,
    Note,
    PlannerEvent,
    Profile,
    Role,
    StudyPlan,
    Task,
    UserRole,
)
from .policies import has_permission, has_role
from .views import RegisterForm


class NoteModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.note = Note.objects.create(
            user=self.user,
            title='Test Note',
            content='This is a test note content.'
        )

    def test_note_creation(self):
        self.assertEqual(self.note.title, 'Test Note')
        self.assertEqual(self.note.user.username, 'testuser')


class P0ModelRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='model-user', password='safe-pass-123')

    def test_task_has_callable_overdue_method_and_updated_timestamp(self):
        task = Task.objects.create(
            user=self.user,
            title='Past task',
            due_date=timezone.localdate() - timedelta(days=1),
        )

        self.assertTrue(task.is_overdue())
        self.assertIsNotNone(task.updated_at)
        self.assertGreaterEqual(task.updated_at, task.created_at)

        task.status = 'Completed'
        task.save()
        self.assertFalse(task.is_overdue())

    def test_study_plan_hours_must_be_positive(self):
        form = StudyPlanForm(data={
            'subject': 'Math',
            'hours': '0',
            'date': timezone.localdate().isoformat(),
            'notes': '',
        })
        self.assertFalse(form.is_valid())


class AuthenticationAndRouteRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='route-user', password='Old-safe-pass-123', email='route@example.test'
        )

    def test_registration_uses_django_password_validators(self):
        form = RegisterForm(data={
            'username': 'new-user',
            'email': 'new@example.test',
            'password': '12345678',
            'confirm_password': '12345678',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_registration_rejects_duplicate_username(self):
        form = RegisterForm(data={
            'username': 'route-user',
            'email': 'different@example.test',
            'password': 'Strong-password-456!',
            'confirm_password': 'Strong-password-456!',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_registration_rejects_duplicate_email(self):
        form = RegisterForm(data={
            'username': 'different-user',
            'email': 'route@example.test',
            'password': 'Strong-password-456!',
            'confirm_password': 'Strong-password-456!',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_registration_rejects_password_mismatch(self):
        form = RegisterForm(data={
            'username': 'new-register-user',
            'email': 'new-register@example.test',
            'password': 'Strong-password-456!',
            'confirm_password': 'Different-password-456!',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('confirm_password', form.errors)

    def test_registration_normalizes_email(self):
        form = RegisterForm(data={
            'username': 'new-register-user',
            'email': 'New-Register@Example.TEST',
            'password': 'Strong-password-456!',
            'confirm_password': 'Strong-password-456!',
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['email'],
            'new-register@example.test'
        )

    def test_login_with_invalid_credentials_fails(self):
        response = self.client.post(
            reverse('login'),
            {
                'username': 'route-user',
                'password': 'wrong-password',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_successful_registration_creates_hashed_password(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'brand-new-user',
                'email': 'brand-new@example.test',
                'password': 'Strong-password-456!',
                'confirm_password': 'Strong-password-456!',
            },
        )

        self.assertRedirects(response, reverse('dashboard'))

        user = User.objects.get(username='brand-new-user')

        self.assertNotEqual(
            user.password,
            'Strong-password-456!'
        )
        self.assertTrue(
            user.check_password('Strong-password-456!')
        )

    def test_calendar_instructions_uses_existing_template(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar_instructions'))
        self.assertEqual(response.status_code, 200)

    def test_logout_requires_authenticated_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_anonymous_logout_is_safe(self):
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ActivityLog.objects.exists())

    def test_authenticated_password_change(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('password_change'), {
            'old_password': 'Old-safe-pass-123',
            'new_password1': 'New-safe-pass-456',
            'new_password2': 'New-safe-pass-456',
        })
        self.assertRedirects(response, reverse('password_change_done'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-safe-pass-456'))


class AttendanceRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='attendance-user', password='safe-pass-123')
        self.client.force_login(self.user)

    def test_get_attendance_is_read_only(self):
        self.assertEqual(Attendance.objects.count(), 0)
        response = self.client.get(reverse('attendance'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_valid_post_creates_then_updates_one_row(self):
        response = self.client.post(reverse('attendance'), {
            'is_present': 'on',
            'remarks': 'Attended online',
        })
        self.assertRedirects(response, reverse('attendance'))
        self.assertEqual(Attendance.objects.count(), 1)
        record = Attendance.objects.get()
        self.assertTrue(record.is_present)

        self.client.post(reverse('attendance'), {
            'remarks': 'Updated remark',
        })
        self.assertEqual(Attendance.objects.count(), 1)
        record.refresh_from_db()
        self.assertFalse(record.is_present)
        self.assertEqual(record.remarks, 'Updated remark')

    def test_invalid_remarks_do_not_write(self):
        response = self.client.post(reverse('attendance'), {
            'is_present': 'on',
            'remarks': 'x' * 101,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)
        self.assertFalse(AttendanceForm(data={
            'is_present': 'on', 'remarks': 'x' * 101,
        }).is_valid())

    def test_invalid_report_parameters_return_bad_request(self):
        response = self.client.get(reverse('attendance_report'), {
            'month': 'foo', 'year': 'bar',
        })
        self.assertEqual(response.status_code, 400)

        response = self.client.get(reverse('attendance_report'), {
            'month': '13', 'year': '2026',
        })
        self.assertEqual(response.status_code, 400)


class OwnershipAndImportRegressionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='safe-pass-123')
        self.other = User.objects.create_user(username='other', password='safe-pass-123')

    def test_note_file_route_is_owner_scoped(self):
        note = Note.objects.create(
            user=self.owner,
            title='Private note',
            content='Private content',
        )
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('note_file', args=[note.pk])).status_code, 404)

        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('note_file', args=[note.pk])).status_code, 404)

    def test_invalid_task_import_is_all_or_nothing(self):
        payload = (
            'Title,Description,Priority,Status,Due Date\n'
            'Valid task,,High,Pending,2026-09-20\n'
            'Invalid task,,Urgent,Pending,not-a-date\n'
        ).encode()
        upload = SimpleUploadedFile('tasks.csv', payload, content_type='text/csv')
        self.client.force_login(self.owner)
        response = self.client.post(reverse('import_tasks'), {'import_file': upload})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Task.objects.filter(user=self.owner).count(), 0)

    def test_valid_task_import_assigns_current_owner(self):
        payload = (
            'Title,Description,Priority,Status,Due Date\n'
            'Valid task,Read chapter,High,Pending,2026-09-20\n'
        ).encode()
        upload = SimpleUploadedFile('tasks.csv', payload, content_type='text/csv')
        self.client.force_login(self.owner)
        response = self.client.post(reverse('import_tasks'), {'import_file': upload})
        self.assertEqual(response.status_code, 200)
        task = Task.objects.get()
        self.assertEqual(task.user_id, self.owner.id)
        self.assertEqual(task.title, 'Valid task')


class NoteCrudRegressionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='note-edit-owner', password='safe-pass-123'
        )
        self.other = User.objects.create_user(
            username='note-edit-other', password='safe-pass-123'
        )
        self.note = Note.objects.create(
            user=self.owner,
            title='Original title',
            content='Original content with enough words to summarize safely.',
        )

    def test_owner_can_edit_note_and_summary_is_recomputed(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('edit_note', args=[self.note.pk]),
            {
                'title': 'Updated title',
                'content': 'Updated content with enough words to produce a new summary.',
            },
        )
        self.assertRedirects(response, reverse('note_detail', args=[self.note.pk]))
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, 'Updated title')
        self.assertEqual(self.note.content, 'Updated content with enough words to produce a new summary.')
        self.assertTrue(self.note.summary)

    def test_other_user_cannot_edit_note(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse('edit_note', args=[self.note.pk])).status_code,
            404,
        )


class StudyPlanCrudRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='study-plan-user', password='safe-pass-123'
        )
        self.other = User.objects.create_user(
            username='study-plan-other', password='safe-pass-123'
        )
        self.plan = StudyPlan.objects.create(
            user=self.user,
            subject='Databases',
            hours=2,
            date=timezone.localdate(),
            notes='Indexes',
        )
        self.client.force_login(self.user)

    def test_owner_can_edit_archive_and_restore_plan(self):
        response = self.client.post(
            reverse('study_plan_edit', args=[self.plan.pk]),
            {
                'subject': 'Databases',
                'hours': '3',
                'date': timezone.localdate().isoformat(),
                'notes': 'Transactions',
            },
        )
        self.assertRedirects(response, reverse('planner'))
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.hours, 3.0)

        response = self.client.post(reverse('study_plan_delete', args=[self.plan.pk]))
        self.assertRedirects(response, reverse('planner'))
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.is_deleted)
        self.assertIsNotNone(self.plan.deleted_at)

        response = self.client.post(reverse('study_plan_restore', args=[self.plan.pk]))
        self.assertRedirects(response, reverse('planner'))
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.is_deleted)
        self.assertIsNone(self.plan.deleted_at)

    def test_other_user_cannot_edit_or_archive_plan(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse('study_plan_edit', args=[self.plan.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('study_plan_delete', args=[self.plan.pk])).status_code,
            404,
        )


class CalendarExportRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calendar-user', password='safe-pass-123'
        )
        self.client.force_login(self.user)

    def test_ical_export_escapes_text_uses_numeric_priority_and_exports_events(self):
        Task.objects.create(
            user=self.user,
            title='Review \\ commas, semicolons; and\nlines',
            description='Description with \\ and, punctuation; plus\nline break',
            priority='High',
            due_date=timezone.localdate(),
        )
        StudyPlan.objects.create(
            user=self.user,
            subject='Math, Algebra',
            hours=2,
            date=timezone.localdate(),
            notes='Bring; notes',
        )
        start = timezone.now().replace(second=0, microsecond=0) + timedelta(hours=2)
        PlannerEvent.objects.create(
            user=self.user,
            title='Live revision',
            description='Online session',
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        PlannerEvent.objects.create(
            user=self.user,
            title='Archived event',
            starts_at=start + timedelta(days=1),
            ends_at=start + timedelta(days=1, hours=1),
            is_deleted=True,
        )

        response = self.client.get(reverse('export_calendar_ical'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertEqual(response['Content-Type'], 'text/calendar')
        self.assertIn('PRIORITY:1', content)
        self.assertIn(r'SUMMARY:Review \\ commas\, semicolons\; and\nlines', content)
        self.assertIn(r'DESCRIPTION:Description with \\ and\, punctuation\; plus\nline break', content)
        self.assertIn(r'SUMMARY:Study: Math\, Algebra', content)
        self.assertIn(r'DESCRIPTION:Study 2.0 hours for Math\, Algebra. Bring\; notes', content)
        self.assertIn('UID:planner-', content)
        self.assertNotIn('Archived event', content)
        self.assertNotIn('PRIORITY:HIGH', content)
        self.assertNotIn('PRIORITY:MEDIUM', content)
        self.assertNotIn('PRIORITY:LOW', content)
        self.assertNotIn('SUMMARY:Review \\ commas, semicolons; and\nlines', content)
        self.assertIn('\\r\\n', repr(content))


class RbacRegressionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student-role', password='safe-pass-123'
        )
        self.teacher = User.objects.create_user(
            username='teacher-role', password='safe-pass-123'
        )
        self.admin = User.objects.create_user(
            username='role-admin', password='safe-pass-123'
        )
        self.teacher_role = Role.objects.get(code='teacher')
        self.admin_role = Role.objects.get(code='administrator')

        UserRole.objects.filter(profile=self.teacher.profile).delete()
        UserRole.objects.filter(profile=self.admin.profile).delete()
        UserRole.objects.create(profile=self.teacher.profile, role=self.teacher_role)
        UserRole.objects.create(profile=self.admin.profile, role=self.admin_role)

    def test_role_permission_matrix_defaults_to_deny(self):
        self.assertTrue(has_role(self.student, 'student'))
        self.assertTrue(has_permission(self.student, 'study.self_service'))
        self.assertTrue(has_permission(self.student, 'activity.read_own'))
        self.assertFalse(has_permission(self.student, 'admin.dashboard.view'))
        self.assertFalse(has_permission(self.student, 'activity.read_any'))

        self.assertTrue(has_role(self.teacher, 'teacher'))
        self.assertTrue(has_permission(self.teacher, 'student_progress.read'))
        self.assertTrue(has_permission(self.teacher, 'attendance.read_any'))
        self.assertFalse(has_permission(self.teacher, 'users.manage'))
        self.assertFalse(has_permission(self.teacher, 'roles.manage'))

        self.assertTrue(has_permission(self.admin, 'admin.dashboard.view'))
        self.assertTrue(has_permission(self.admin, 'users.manage'))
        self.assertTrue(has_permission(self.admin, 'roles.manage'))

    def test_role_only_administrator_can_use_custom_admin_panel(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('manage_users')).status_code, 200)
        self.assertEqual(self.client.get(reverse('announcements')).status_code, 200)

    def test_legacy_staff_flag_change_does_not_grant_role(self):
        self.student.is_staff = True
        self.student.save()
        self.assertTrue(has_role(self.student, 'student'))
        self.assertFalse(has_permission(self.student, 'admin.dashboard.view'))
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 302)

    def test_user_role_constraint_and_role_protection(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserRole.objects.create(
                    profile=self.student.profile,
                    role=Role.objects.get(code='student'),
                )

        teacher_role = Role.objects.get(code='teacher')
        with self.assertRaises(ProtectedError):
            teacher_role.delete()

    def test_new_user_is_provisioned_once(self):
        user = User.objects.create_user(username='new-provisioned', password='safe-pass-123')
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.user_id, user.id)
        self.assertEqual(UserRole.objects.filter(profile=profile).count(), 1)
        user.save()
        self.assertEqual(UserRole.objects.filter(profile=profile).count(), 1)
