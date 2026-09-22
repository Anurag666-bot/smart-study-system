from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from studyapp.models import Task
from studyapp.services.analytics import get_task_analytics


class TaskAnalyticsTests(TestCase):
    def test_task_analytics_returns_completion_and_overdue_metrics(self):
        user = get_user_model().objects.create_user(username='analytics-user', password='pass12345')
        today = date(2026, 9, 13)

        Task.objects.create(
            user=user,
            title='Done task',
            priority='High',
            status='Completed',
            due_date=today - timedelta(days=3),
            estimated_minutes=120,
            completed_at=None,
        )
        Task.objects.create(
            user=user,
            title='Pending task',
            priority='Medium',
            status='Pending',
            due_date=today - timedelta(days=1),
            estimated_minutes=90,
        )
        Task.objects.create(
            user=user,
            title='Upcoming task',
            priority='Low',
            status='In Progress',
            due_date=today + timedelta(days=5),
            estimated_minutes=60,
        )

        analytics = get_task_analytics(user, today=today)

        self.assertEqual(analytics['total_tasks'], 3)
        self.assertEqual(analytics['completed_tasks'], 1)
        self.assertEqual(analytics['pending_tasks'], 1)
        self.assertEqual(analytics['overdue_tasks'], 1)
        self.assertEqual(analytics['completion_percentage'], 33.33)
        self.assertGreaterEqual(analytics['average_completion_time_hours'], 0)
