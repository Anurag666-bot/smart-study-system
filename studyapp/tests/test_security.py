from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from studyapp.models import (
    Goal,
    Note,
    PlannerEvent,
    Role,
    StudentSubject,
    Subject,
    Task,
    UserRole,
)

User = get_user_model()


class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='security-student', password='safe-pass-123')
        self.other = User.objects.create_user(username='security-other', password='safe-pass-123')
        self.teacher = User.objects.create_user(username='security-teacher', password='safe-pass-123')
        self.admin = User.objects.create_user(
            username='security-admin', password='safe-pass-123', is_staff=True
        )

        self.subject = Subject.objects.create(code='SEC101', name='Security')
        StudentSubject.objects.create(student=self.student, subject=self.subject, is_active=True)

        self._assign_role(self.student, 'student')
        self._assign_role(self.other, 'student')
        self._assign_role(self.teacher, 'teacher')
        self._assign_role(self.admin, 'administrator')

        self.note = Note.objects.create(user=self.student, title='Private note', content='Sensitive details.')
        self.task = Task.objects.create(
            user=self.student,
            subject=self.subject,
            title='Practice security review',
            description='Review authentication flows.',
            due_date=timezone.localdate() + timedelta(days=2),
        )
        self.event = PlannerEvent.objects.create(
            user=self.student,
            title='Security study block',
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.goal = Goal.objects.create(
            user=self.student,
            subject=self.subject,
            title='Complete security checklist',
            target_date=timezone.localdate() + timedelta(days=7),
            target_value=Decimal('5'),
        )

    def _assign_role(self, user, code):
        UserRole.objects.filter(profile=user.profile).delete()
        UserRole.objects.create(profile=user.profile, role=Role.objects.get(code=code))

    def test_unauthenticated_access_requires_login(self):
        protected_urls = [
            reverse('dashboard'),
            reverse('task_list'),
            reverse('notes_list'),
            reverse('teacher_attendance'),
            reverse('planner_event_list'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, (302, 403))
            self.assertIn('/login/', response['Location']) if response.status_code == 302 else None

    def test_role_restrictions_block_student_from_teacher_workflows(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('teacher_student_list')).status_code, 302)
        self.assertEqual(self.client.get(reverse('teacher_attendance')).status_code, 302)
        self.assertEqual(self.client.get(reverse('teacher_progress_report')).status_code, 302)

        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse('study_session_list')).status_code, 302)

    def test_object_ownership_prevents_cross_user_access(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('note_detail', args=[self.note.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('task_detail', args=[self.task.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('planner_event_edit', args=[self.event.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('goal_edit', args=[self.goal.pk])).status_code, 404)

    def test_csrf_protected_post_requires_token(self):
        self.client.force_login(self.student)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.student)
        response = csrf_client.post(reverse('logout'))
        self.assertEqual(response.status_code, 403)

    def test_invalid_form_data_is_rejected_without_side_effects(self):
        response = self.client.post(reverse('login'), {
            'username': 'does-not-exist',
            'password': 'wrong-password',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password.')

        response = self.client.post(reverse('register'), {
            'username': 'new-user',
            'email': 'not-an-email',
            'password': 'short',
            'confirm_password': 'different',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid email address')
        self.assertFalse(User.objects.filter(username='new-user').exists())

    def test_session_logout_clears_authentication(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(self.client.session.get('_auth_user_id'))
