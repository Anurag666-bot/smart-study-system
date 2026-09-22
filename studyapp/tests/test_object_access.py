from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from studyapp.models import (
    Goal,
    Note,
    PlannerEvent,
    Role,
    StudentSubject,
    StudySession,
    Subject,
    Task,
    UserRole,
)


class ObjectAccessControlTests(TestCase):
    def setUp(self):
        self.student_a = User.objects.create_user(username='student-a', password='safe-pass-123')
        self.student_b = User.objects.create_user(username='student-b', password='safe-pass-123')
        self.teacher = User.objects.create_user(username='teacher-a', password='safe-pass-123')
        self.admin = User.objects.create_user(username='admin-access', password='safe-pass-123', is_staff=True)

        self.subject = Subject.objects.create(code='BIO101', name='Biology')
        StudentSubject.objects.create(student=self.student_a, subject=self.subject, is_active=True)
        StudentSubject.objects.create(student=self.student_b, subject=self.subject, is_active=True)

        self._assign_role(self.student_a, 'student')
        self._assign_role(self.student_b, 'student')
        self._assign_role(self.teacher, 'teacher')
        self._assign_role(self.admin, 'administrator')

        self.note = Note.objects.create(user=self.student_a, title='Private note', content='Keep this safe.')
        self.task = Task.objects.create(
            user=self.student_a,
            subject=self.subject,
            title='Finish lab prep',
            description='Prepare for the experiment.',
            due_date=timezone.localdate() + timedelta(days=3),
        )
        self.event = PlannerEvent.objects.create(
            user=self.student_a,
            title='Revision block',
            description='Read the chapter',
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.goal = Goal.objects.create(
            user=self.student_a,
            subject=self.subject,
            title='Complete biology notes',
            target_date=timezone.localdate() + timedelta(days=7),
            target_value=Decimal('10'),
        )
        self.session = StudySession.objects.create(
            user=self.student_a,
            subject=self.subject,
            started_at=timezone.now() - timedelta(hours=2),
            ended_at=timezone.now() - timedelta(hours=1),
            duration_minutes=60,
            notes='Focused reading session.',
        )

    def _assign_role(self, user, code):
        UserRole.objects.filter(profile=user.profile).delete()
        UserRole.objects.create(profile=user.profile, role=Role.objects.get(code=code))

    def test_owner_can_access_own_record_routes(self):
        self.client.force_login(self.student_a)
        self.assertEqual(self.client.get(reverse('note_detail', args=[self.note.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('task_detail', args=[self.task.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('planner_event_edit', args=[self.event.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('goal_edit', args=[self.goal.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('study_session_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('attendance')).status_code, 200)
        self.assertEqual(self.client.get(reverse('attendance_report')).status_code, 200)

    def test_other_student_is_denied_access_to_owner_records(self):
        self.client.force_login(self.student_b)
        self.assertEqual(self.client.get(reverse('note_detail', args=[self.note.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('task_detail', args=[self.task.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('planner_event_edit', args=[self.event.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('goal_edit', args=[self.goal.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('study_session_delete', args=[self.session.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('note_file', args=[self.note.pk])).status_code, 404)

    def test_anonymous_users_are_denied(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('note_detail', args=[self.note.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse('task_detail', args=[self.task.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse('planner_event_edit', args=[self.event.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse('goal_edit', args=[self.goal.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse('attendance')).status_code, 302)

    def test_teacher_only_accesses_authorized_subject_records(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse('task_detail', args=[self.task.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('goal_edit', args=[self.goal.pk])).status_code, 404)

        # Teacher can still manage their own assigned subject pages without leaking unrelated objects.
        response = self.client.get(reverse('teacher_attendance'))
        self.assertEqual(response.status_code, 200)

    def test_admin_is_permitted_by_policy(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('note_detail', args=[self.note.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('task_detail', args=[self.task.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('planner_event_edit', args=[self.event.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('goal_edit', args=[self.goal.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 200)
