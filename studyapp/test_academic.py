from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Achievement,
    AdminLog,
    Announcement,
    Attendance,
    Exam,
    ExamResult,
    EventReminder,
    Goal,
    Notification,
    PlannerEvent,
    Role,
    StudentSubject,
    StudyPlan,
    StudySession,
    Subject,
    SystemSetting,
    TeacherSubject,
    Topic,
    UserAchievement,
    UserRole,
)


class AcademicModelConstraintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='academic-model-user', password='safe-pass-123'
        )
        self.subject = Subject.objects.create(code='CS101', name='Computer Science')

    def test_subject_topic_and_enrollment_uniqueness(self):
        Topic.objects.create(subject=self.subject, name='Algorithms')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Topic.objects.create(subject=self.subject, name='Algorithms')

        StudentSubject.objects.create(student=self.user, subject=self.subject)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentSubject.objects.create(student=self.user, subject=self.subject)

    def test_subject_scoped_attendance_allows_multiple_classes_per_day(self):
        second_subject = Subject.objects.create(code='MATH101', name='Mathematics')
        Attendance.objects.create(
            user=self.user,
            subject=self.subject,
            date=timezone.localdate(),
            status='PRESENT',
        )
        Attendance.objects.create(
            user=self.user,
            subject=second_subject,
            date=timezone.localdate(),
            status='ABSENT',
        )
        self.assertEqual(
            Attendance.objects.filter(user=self.user, date=timezone.localdate()).count(),
            2,
        )

    def test_time_and_score_validation(self):
        started = timezone.now()
        with self.assertRaises(ValidationError):
            StudySession(
                user=self.user,
                started_at=started,
                ended_at=started,
            ).full_clean()

        with self.assertRaises(ValidationError):
            PlannerEvent(
                user=self.user,
                title='Invalid event',
                starts_at=started,
                ends_at=started,
            ).full_clean()

        with self.assertRaises(ValidationError):
            Goal(
                user=self.user,
                title='Invalid goal',
                target_date=timezone.localdate(),
                target_value=Decimal('0'),
            ).full_clean()

        exam = Exam.objects.create(
            subject=self.subject,
            title='Midterm',
            exam_date=timezone.localdate() + timedelta(days=7),
            max_score=Decimal('100'),
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            ExamResult(exam=exam, student=self.user, score=Decimal('101')).full_clean()

    def test_achievement_award_is_unique(self):
        achievement = Achievement.objects.create(
            code='first-session', name='First session', description='Study once.'
        )
        UserAchievement.objects.create(user=self.user, achievement=achievement)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserAchievement.objects.create(user=self.user, achievement=achievement)


class AcademicOwnershipAndCrudTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='academic-student', password='safe-pass-123'
        )
        self.other = User.objects.create_user(
            username='academic-other', password='safe-pass-123'
        )
        self.teacher = User.objects.create_user(
            username='academic-teacher', password='safe-pass-123'
        )
        self.admin = User.objects.create_user(
            username='academic-admin', password='safe-pass-123'
        )
        self._assign_role(self.teacher, 'teacher')
        self._assign_role(self.admin, 'administrator')
        self.subject = Subject.objects.create(code='DB101', name='Databases')
        self.other_subject = Subject.objects.create(code='OS101', name='Operating Systems')
        StudentSubject.objects.create(student=self.student, subject=self.subject)
        TeacherSubject.objects.create(teacher=self.teacher, subject=self.subject)

    def _assign_role(self, user, code):
        UserRole.objects.filter(profile=user.profile).delete()
        UserRole.objects.create(profile=user.profile, role=Role.objects.get(code=code))

    def _login(self, user):
        self.client.force_login(user)

    def test_student_subject_scope_and_enrollment_scope(self):
        self._login(self.student)
        response = self.client.get(reverse('subject_list'))
        self.assertContains(response, 'Databases')
        self.assertNotContains(response, 'Operating Systems')

        response = self.client.post(reverse('enrollment_list'), {
            'subject': self.other_subject.pk,
        })
        self.assertRedirects(response, reverse('enrollment_list'))
        self.assertTrue(
            StudentSubject.objects.filter(
                student=self.student, subject=self.other_subject, is_active=True
            ).exists()
        )

    def test_student_owned_crud_and_cross_user_denial(self):
        self._login(self.student)
        start = timezone.now().replace(second=0, microsecond=0)
        start_value = timezone.localtime(start).strftime('%Y-%m-%dT%H:%M')
        end_value = timezone.localtime(start + timedelta(minutes=45)).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post(reverse('study_session_list'), {
            'subject': self.subject.pk,
            'started_at': start_value,
            'ended_at': end_value,
            'duration_minutes': '45',
            'notes': 'Revision',
        })
        self.assertRedirects(response, reverse('study_session_list'))
        session = StudySession.objects.get(user=self.student)

        response = self.client.post(reverse('study_session_delete', args=[session.pk]))
        self.assertRedirects(response, reverse('study_session_list'))
        self.assertFalse(StudySession.objects.filter(pk=session.pk).exists())

        goal = Goal.objects.create(
            user=self.student,
            subject=self.subject,
            title='Finish normalization',
            target_date=timezone.localdate() + timedelta(days=14),
            target_value=Decimal('10'),
        )
        self._login(self.other)
        self.assertEqual(
            self.client.get(reverse('goal_edit', args=[goal.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('goal_delete', args=[goal.pk])).status_code,
            404,
        )

    def test_teacher_can_create_only_for_assigned_subject(self):
        self._login(self.teacher)
        response = self.client.post(reverse('exam_create'), {
            'subject': self.subject.pk,
            'title': 'Database midterm',
            'exam_date': (timezone.localdate() + timedelta(days=10)).isoformat(),
            'max_score': '100',
        })
        self.assertRedirects(response, reverse('exam_list'))
        exam = Exam.objects.get(title='Database midterm')
        self.assertEqual(exam.created_by_id, self.teacher.id)

        response = self.client.post(reverse('exam_create'), {
            'subject': self.other_subject.pk,
            'title': 'Unauthorized exam',
            'exam_date': (timezone.localdate() + timedelta(days=10)).isoformat(),
            'max_score': '100',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Exam.objects.filter(title='Unauthorized exam').exists())

    def test_student_can_record_result_for_enrolled_subject(self):
        exam = Exam.objects.create(
            subject=self.subject,
            title='Database final',
            exam_date=timezone.localdate() + timedelta(days=10),
            max_score=Decimal('50'),
            created_by=self.teacher,
        )
        self._login(self.student)
        response = self.client.post(reverse('exam_result_create', args=[exam.pk]), {
            'exam': exam.pk,
            'score': '42',
            'feedback': 'Good work',
        })
        self.assertRedirects(response, reverse('exam_list'))
        result = ExamResult.objects.get(exam=exam, student=self.student)
        self.assertEqual(result.percentage, 84.0)

    def test_notification_and_planner_event_are_owner_scoped(self):
        notification = Notification.objects.create(
            user=self.student,
            notification_type='SYSTEM',
            title='Private',
            message='Only for the student.',
        )
        event = PlannerEvent.objects.create(
            user=self.student,
            title='Revision block',
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self._login(self.other)
        self.assertEqual(
            self.client.post(reverse('notification_mark_read', args=[notification.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse('planner_event_edit', args=[event.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('planner_event_delete', args=[event.pk])).status_code,
            404,
        )

    def test_only_administrator_can_archive_subject(self):
        self._login(self.teacher)
        self.assertEqual(
            self.client.get(reverse('subject_delete', args=[self.subject.pk])).status_code,
            302,
        )
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)

        self._login(self.admin)
        response = self.client.post(reverse('subject_delete', args=[self.subject.pk]))
        self.assertRedirects(response, reverse('subject_list'))
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_active)

    def test_teacher_can_view_students_and_class_report(self):
        self._login(self.teacher)
        response = self.client.get(reverse('teacher_student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.username)
        self.assertEqual(
            self.client.get(reverse('teacher_progress_report')).status_code,
            200,
        )

    def test_teacher_can_enter_exam_result_for_enrolled_student(self):
        exam = Exam.objects.create(
            subject=self.subject,
            title='Teacher-managed exam',
            exam_date=timezone.localdate() + timedelta(days=3),
            max_score=Decimal('100'),
            created_by=self.teacher,
        )
        self._login(self.teacher)
        self.assertEqual(
            self.client.get(reverse('teacher_exam_results', args=[exam.pk])).status_code,
            200,
        )
        response = self.client.post(
            reverse('teacher_exam_result_edit', args=[exam.pk, self.student.pk]),
            {'student': self.student.pk, 'score': '88', 'feedback': 'Strong work'},
        )
        self.assertRedirects(response, reverse('teacher_student_list'))
        result = ExamResult.objects.get(exam=exam, student=self.student)
        self.assertEqual(result.score, Decimal('88'))

    def test_teacher_can_edit_and_archive_assigned_exam(self):
        exam = Exam.objects.create(
            subject=self.subject,
            title='Editable exam',
            exam_date=timezone.localdate() + timedelta(days=3),
            max_score=Decimal('100'),
            created_by=self.teacher,
        )
        self._login(self.teacher)
        response = self.client.post(reverse('exam_edit', args=[exam.pk]), {
            'subject': self.subject.pk,
            'title': 'Updated exam',
            'exam_date': (timezone.localdate() + timedelta(days=4)).isoformat(),
            'max_score': '90',
        })
        self.assertRedirects(response, reverse('exam_list'))
        exam.refresh_from_db()
        self.assertEqual(exam.title, 'Updated exam')
        self.assertEqual(exam.max_score, Decimal('90'))

        self.assertEqual(self.client.get(reverse('exam_delete', args=[exam.pk])).status_code, 200)
        response = self.client.post(reverse('exam_delete', args=[exam.pk]))
        self.assertRedirects(response, reverse('exam_list'))
        exam.refresh_from_db()
        self.assertTrue(exam.is_archived)
        self.assertEqual(
            self.client.post(reverse('exam_restore', args=[exam.pk])).status_code,
            302,
        )
        exam.refresh_from_db()
        self.assertFalse(exam.is_archived)

    def test_teacher_can_record_scoped_attendance(self):
        self._login(self.teacher)
        response = self.client.get(
            reverse('teacher_attendance'),
            {'subject': self.subject.pk},
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('teacher_attendance'), {
            'subject': self.subject.pk,
            'student': self.student.pk,
            'date': timezone.localdate().isoformat(),
            'status': 'LATE',
            'remarks': 'Arrived after bell',
        })
        self.assertRedirects(response, reverse('teacher_attendance'))
        attendance = self.student.attendance.get(date=timezone.localdate())
        self.assertEqual(attendance.status, 'LATE')
        self.assertTrue(attendance.is_present)

    def test_student_cannot_use_teacher_workflows(self):
        self._login(self.student)
        self.assertEqual(
            self.client.get(reverse('teacher_student_list')).status_code,
            302,
        )
        self.assertEqual(
            self.client.get(reverse('teacher_attendance')).status_code,
            302,
        )

    def test_student_can_preview_and_save_adaptive_plan(self):
        self._login(self.student)
        response = self.client.get(reverse('adaptive_planner'), {
            'days': 2,
            'available_minutes': 60,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adaptive Study Planner')
        response = self.client.post(reverse('adaptive_planner'), {
            'days': 1,
            'available_minutes': 60,
        })
        self.assertRedirects(response, reverse('planner'))
        self.assertTrue(StudyPlan.objects.filter(user=self.student).exists())

    def test_student_can_add_and_remove_event_reminder(self):
        self._login(self.student)
        starts_at = timezone.now().replace(second=0, microsecond=0) + timedelta(hours=3)
        event = PlannerEvent.objects.create(
            user=self.student,
            title='Revision block',
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
        )
        remind_at = starts_at - timedelta(hours=1)
        response = self.client.post(
            reverse('planner_event_reminder_add', args=[event.pk]),
            {'remind_at': timezone.localtime(remind_at).strftime('%Y-%m-%dT%H:%M')},
        )
        self.assertRedirects(response, reverse('planner_event_list'))
        reminder = EventReminder.objects.get(event=event)

        response = self.client.post(
            reverse('planner_event_reminder_delete', args=[reminder.pk]),
        )
        self.assertRedirects(response, reverse('planner_event_list'))
        self.assertFalse(EventReminder.objects.filter(pk=reminder.pk).exists())

    def test_administrator_can_manage_topics_and_teacher_assignments(self):
        self._login(self.admin)
        response = self.client.post(
            reverse('topic_create', args=[self.subject.pk]),
            {'subject': self.subject.pk, 'name': 'Relational algebra', 'description': ''},
        )
        self.assertRedirects(response, reverse('subject_list'))
        topic = self.subject.topics.get(name='Relational algebra')
        self.assertEqual(
            self.client.post(
                reverse('topic_delete', args=[topic.pk]),
            ).status_code,
            302,
        )

        response = self.client.post(
            reverse('teacher_assignment_list', args=[self.subject.pk]),
            {'teacher': self.teacher.pk},
        )
        self.assertRedirects(
            response,
            reverse('teacher_assignment_list', args=[self.subject.pk]),
        )
        self.assertTrue(
            TeacherSubject.objects.filter(
                teacher=self.teacher, subject=self.subject, is_active=True
            ).exists()
        )
        assignment = TeacherSubject.objects.get(
            teacher=self.teacher, subject=self.subject
        )
        response = self.client.post(
            reverse('teacher_assignment_delete', args=[assignment.pk])
        )
        self.assertRedirects(
            response,
            reverse('teacher_assignment_list', args=[self.subject.pk]),
        )
        self.assertFalse(TeacherSubject.objects.get(pk=assignment.pk).is_active)

    def test_admin_can_manage_roles_announcements_settings_and_audit(self):
        self._login(self.admin)
        teacher_role = Role.objects.get(code='teacher')
        response = self.client.post(reverse('manage_users'), {
            'user': self.student.pk,
            'role': teacher_role.pk,
        })
        self.assertRedirects(response, reverse('manage_users'))
        self.assertTrue(
            UserRole.objects.filter(
                profile=self.student.profile,
                role=teacher_role,
            ).exists()
        )

        response = self.client.post(reverse('announcements'), {
            'title': 'Exam week',
            'body': 'Review the published schedule.',
            'is_published': 'on',
        })
        self.assertRedirects(response, reverse('announcements'))
        announcement = Announcement.objects.get(title='Exam week')
        self.assertEqual(announcement.created_by, self.admin)

        response = self.client.post(reverse('admin_settings'), {
            'key': 'study.default_minutes',
            'value': '120',
        })
        self.assertRedirects(response, reverse('admin_settings'))
        self.assertEqual(
            SystemSetting.objects.get(key='study.default_minutes').value,
            120,
        )
        self.assertGreaterEqual(AdminLog.objects.count(), 3)
        self.assertEqual(self.client.get(reverse('admin_audit_logs')).status_code, 200)
