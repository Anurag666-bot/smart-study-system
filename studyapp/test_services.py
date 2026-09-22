from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import (
    Attendance,
    Exam,
    ExamResult,
    Notification,
    PlannerEvent,
    StudentSubject,
    StudySession,
    Subject,
    Task,
)
from .services.achievements import evaluate_user_achievements
from .services.analytics import get_student_analytics
from .services.attendance import calculate_attendance
from .services.notifications import generate_user_notifications
from .services.planner import build_adaptive_plan, generate_study_plan


class ServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='service-user', password='safe-pass-123'
        )
        self.subject = Subject.objects.create(code='AI101', name='Artificial Intelligence')
        self.tz = timezone.get_current_timezone()
        self.today = timezone.localdate()
        self.now = timezone.make_aware(
            datetime.combine(self.today, time(12, 0)), self.tz
        )

    def _at(self, day_offset, hour=10):
        day = self.today + timedelta(days=day_offset)
        return timezone.make_aware(datetime.combine(day, time(hour, 0)), self.tz)

    def test_analytics_is_bounded_explainable_and_streak_aware(self):
        for offset in (-2, -1, 0):
            StudySession.objects.create(
                user=self.user,
                subject=self.subject,
                started_at=self._at(offset),
                ended_at=self._at(offset, 11),
            )
        Attendance.objects.create(user=self.user, date=self.today, is_present=True)
        Attendance.objects.create(
            user=self.user,
            date=self.today - timedelta(days=1),
            is_present=False,
        )
        Task.objects.create(
            user=self.user,
            title='Completed task',
            status='Completed',
            due_date=self.today,
        )
        Task.objects.create(
            user=self.user,
            title='Pending task',
            status='Pending',
            due_date=self.today + timedelta(days=1),
        )
        exam = Exam.objects.create(
            subject=self.subject,
            title='AI exam',
            exam_date=self.today + timedelta(days=10),
            max_score=Decimal('100'),
            created_by=self.user,
        )
        ExamResult.objects.create(exam=exam, student=self.user, score=Decimal('80'))

        data = get_student_analytics(self.user, today=self.today, now=self.now)
        self.assertEqual(data['study_minutes_recent'], 180)
        self.assertEqual(data['current_streak'], 3)
        self.assertEqual(data['task_completion_percent'], 50.0)
        self.assertEqual(data['attendance_percent_recent'], 50.0)
        self.assertEqual(data['subject_performance'][0]['exam_average'], 80.0)

    def test_generate_study_plan_returns_suggestions_for_requested_window(self):
        self.subject = Subject.objects.create(code='BIO101', name='Biology')
        StudentSubject.objects.create(student=self.user, subject=self.subject)
        Task.objects.create(
            user=self.user,
            subject=self.subject,
            title='Revise cells',
            due_date=self.today + timedelta(days=1),
            status='Pending',
        )

        plan = generate_study_plan(
            self.user,
            start_date=self.today,
            end_date=self.today + timedelta(days=2),
            available_hours=3,
        )

        self.assertTrue(plan)
        self.assertTrue(all('date' in item for item in plan))
        self.assertTrue(all('subject' in item for item in plan))
        self.assertTrue(all('minutes' in item for item in plan))
        self.assertLessEqual(sum(item['minutes'] for item in plan), 180)

    def test_attendance_summary_excludes_excused_and_handles_target_boundaries(self):
        records = [
            Attendance(user=self.user, date=self.today, status='PRESENT'),
            Attendance(user=self.user, date=self.today - timedelta(days=1), status='LATE'),
            Attendance(user=self.user, date=self.today - timedelta(days=2), status='ABSENT'),
            Attendance(user=self.user, date=self.today - timedelta(days=3), status='EXCUSED'),
        ]
        summary = calculate_attendance(records)
        self.assertEqual(summary['scheduled_classes'], 3)
        self.assertEqual(summary['attended_classes'], 2)
        self.assertEqual(summary['EXCUSED'], 1)
        self.assertEqual(summary['percentage'], 66.67)
        self.assertEqual(summary['classes_needed'], 1)
        self.assertEqual(summary['safe_missed_classes'], 0)
        self.assertEqual(calculate_attendance([], target=0)['classes_needed'], 0)

    def test_attendance_summary_rejects_invalid_target(self):
        with self.assertRaises(ValueError):
            calculate_attendance([], target=1.1)

    def test_adaptive_plan_is_bounded_explainable_and_respects_events(self):
        second_subject = Subject.objects.create(code='DB101', name='Databases')
        StudentSubject.objects.create(student=self.user, subject=self.subject)
        StudentSubject.objects.create(student=self.user, subject=second_subject)
        Task.objects.create(
            user=self.user,
            subject=self.subject,
            title='Urgent revision',
            due_date=self.today,
        )
        PlannerEvent.objects.create(
            user=self.user,
            title='Existing commitment',
            starts_at=self._at(0, 8),
            ends_at=self._at(0, 9),
        )
        plan = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=2,
            available_minutes_per_day=90,
            now=self.now,
        )
        self.assertTrue(plan)
        self.assertTrue(all(item['date'] != self.today for item in plan))
        for day in {item['date'] for item in plan}:
            self.assertLessEqual(
                sum(item['minutes'] for item in plan if item['date'] == day),
                90,
            )
        self.assertTrue(all(0 <= item['priority'] <= 100 for item in plan))
        self.assertTrue(any('deadline-or-exam-imminent' in item['reasons'] for item in plan))

    def test_adaptive_plan_validates_bounds_and_empty_enrollment(self):
        self.assertEqual(
            build_adaptive_plan(self.user, start_date=self.today),
            [],
        )
        with self.assertRaises(ValueError):
            build_adaptive_plan(self.user, days=15)
        with self.assertRaises(ValueError):
            build_adaptive_plan(self.user, available_minutes_per_day=20)

    def test_deadline_and_event_notifications_are_idempotent(self):
        Task.objects.create(
            user=self.user,
            title='Submit assignment',
            due_date=self.today,
        )
        PlannerEvent.objects.create(
            user=self.user,
            title='Revision session',
            starts_at=self.now + timedelta(hours=1),
            ends_at=self.now + timedelta(hours=2),
        )
        first = generate_user_notifications(
            self.user, today=self.today, now=self.now, horizon_days=1
        )
        second = generate_user_notifications(
            self.user, today=self.today, now=self.now, horizon_days=1
        )
        self.assertEqual(len(first), 2)
        self.assertEqual(second, [])
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)

    def test_due_event_reminder_becomes_idempotent_notification(self):
        event = PlannerEvent.objects.create(
            user=self.user,
            title='Reminder event',
            starts_at=self.now + timedelta(hours=2),
            ends_at=self.now + timedelta(hours=3),
        )
        reminder = __import__('studyapp.models', fromlist=['EventReminder']).EventReminder.objects.create(
            event=event,
            remind_at=self.now - timedelta(minutes=1),
        )
        first = generate_user_notifications(self.user, today=self.today, now=self.now)
        self.assertEqual(len(first), 1)
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.sent_at)
        self.assertEqual(generate_user_notifications(self.user, today=self.today, now=self.now), [])

    def test_achievement_evaluation_is_idempotent(self):
        for offset in range(7):
            StudySession.objects.create(
                user=self.user,
                started_at=self._at(-offset),
                ended_at=self._at(-offset, 11),
            )
        for index in range(10):
            Task.objects.create(
                user=self.user,
                title=f'Completed {index}',
                status='Completed',
                due_date=self.today,
            )
        first = evaluate_user_achievements(self.user, today=self.today)
        second = evaluate_user_achievements(self.user, today=self.today)
        self.assertEqual(len(first), 3)
        self.assertEqual(second, [])
