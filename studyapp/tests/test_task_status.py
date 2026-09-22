from datetime import date, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase

from studyapp.services.task_status import (
    classify_task,
    task_status_css_class,
    task_status_label,
    task_status_summary,
)


class TaskStatusTests(SimpleTestCase):
    def test_classify_overdue_due_today_due_tomorrow_and_upcoming(self):
        today = date(2026, 9, 13)

        overdue = SimpleNamespace(status='Pending', due_date=today - timedelta(days=1))
        due_today = SimpleNamespace(status='Pending', due_date=today)
        due_tomorrow = SimpleNamespace(status='Pending', due_date=today + timedelta(days=1))
        upcoming = SimpleNamespace(status='Pending', due_date=today + timedelta(days=5))
        completed = SimpleNamespace(status='Completed', due_date=today - timedelta(days=10))

        self.assertEqual(classify_task(overdue, today=today), 'overdue')
        self.assertEqual(classify_task(due_today, today=today), 'due_today')
        self.assertEqual(classify_task(due_tomorrow, today=today), 'due_tomorrow')
        self.assertEqual(classify_task(upcoming, today=today), 'upcoming')
        self.assertEqual(classify_task(completed, today=today), 'completed')

        self.assertEqual(task_status_label(overdue, today=today), 'Overdue')
        self.assertEqual(task_status_label(due_today, today=today), 'Due Today')
        self.assertEqual(task_status_label(due_tomorrow, today=today), 'Due Tomorrow')
        self.assertEqual(task_status_label(completed, today=today), 'Completed')

    def test_status_summary_has_css_class_for_every_state(self):
        today = date(2026, 9, 13)

        overdue = SimpleNamespace(status='Pending', due_date=today - timedelta(days=1))
        due_today = SimpleNamespace(status='Pending', due_date=today)
        due_tomorrow = SimpleNamespace(status='Pending', due_date=today + timedelta(days=1))
        upcoming = SimpleNamespace(status='Pending', due_date=today + timedelta(days=5))
        completed = SimpleNamespace(status='Completed', due_date=today - timedelta(days=2))

        self.assertEqual(task_status_css_class(overdue, today=today), 'task-status-overdue')
        self.assertEqual(task_status_css_class(due_today, today=today), 'task-status-due-today')
        self.assertEqual(task_status_css_class(due_tomorrow, today=today), 'task-status-due-tomorrow')
        self.assertEqual(task_status_css_class(upcoming, today=today), 'task-status-upcoming')
        self.assertEqual(task_status_css_class(completed, today=today), 'task-status-completed')

        summary = task_status_summary(upcoming, today=today)
        self.assertEqual(summary['status'], 'upcoming')
        self.assertEqual(summary['label'], 'Upcoming')
        self.assertEqual(summary['css_class'], 'task-status-upcoming')
