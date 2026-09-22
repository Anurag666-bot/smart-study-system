from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from studyapp.models import Task
from studyapp.services.priority import calculate_priority_score


class PriorityScoringTests(SimpleTestCase):
    def test_priority_engine_accounts_for_deadline_and_workload(self):
        today = date(2026, 9, 13)

        urgent_heavy = SimpleNamespace(
            title='Urgent heavy assignment',
            priority='High',
            status='In Progress',
            due_date=today + timedelta(days=1),
            estimated_minutes=300,
        )
        relaxed_light = SimpleNamespace(
            title='Relaxed light assignment',
            priority='High',
            status='In Progress',
            due_date=today + timedelta(days=20),
            estimated_minutes=60,
        )

        urgent_result = calculate_priority_score(urgent_heavy, today=today)
        relaxed_result = calculate_priority_score(relaxed_light, today=today)

        self.assertGreater(urgent_result['score'], relaxed_result['score'])
        self.assertEqual(urgent_result['factors']['days_until_deadline'], 1)
        self.assertEqual(urgent_result['factors']['estimated_hours'], 5.0)
        self.assertEqual(urgent_result['factors']['importance'], 'High')
        self.assertEqual(urgent_result['factors']['status'], 'In Progress')
        self.assertIn('Deadline is approaching', urgent_result['reasons'])
        self.assertIn('Estimated workload is high', urgent_result['reasons'])
        self.assertIn('Task is still pending', urgent_result['reasons'])

    def test_priority_engine_respects_importance_and_status(self):
        today = date(2026, 9, 13)

        important_pending = SimpleNamespace(
            title='Important task',
            priority='High',
            status='Pending',
            due_date=today + timedelta(days=5),
            estimated_minutes=90,
        )
        minor_pending = SimpleNamespace(
            title='Minor task',
            priority='Low',
            status='Pending',
            due_date=today + timedelta(days=5),
            estimated_minutes=90,
        )

        important_result = calculate_priority_score(important_pending, today=today)
        minor_result = calculate_priority_score(minor_pending, today=today)

        self.assertGreater(important_result['score'], minor_result['score'])
        self.assertNotEqual(important_result['factors']['importance'], minor_result['factors']['importance'])
        self.assertEqual(important_result['factors']['status'], 'Pending')
        self.assertIn('High importance', important_result['reasons'])


class PriorityScenarioTests(SimpleTestCase):
    def test_task_priority_handles_scenario_matrix_and_boundaries(self):
        today = date(2026, 9, 13)

        far_deadline = SimpleNamespace(
            title='Far deadline', priority='Low', status='Pending',
            due_date=today + timedelta(days=30), estimated_minutes=60,
        )
        near_deadline = SimpleNamespace(
            title='Near deadline', priority='Medium', status='Pending',
            due_date=today + timedelta(days=1), estimated_minutes=120,
        )
        overdue = SimpleNamespace(
            title='Overdue', priority='High', status='Pending',
            due_date=today - timedelta(days=2), estimated_minutes=180,
        )
        low_importance = SimpleNamespace(
            title='Low importance', priority='Low', status='Pending',
            due_date=today + timedelta(days=5), estimated_minutes=150,
        )
        high_importance = SimpleNamespace(
            title='High importance', priority='High', status='Pending',
            due_date=today + timedelta(days=5), estimated_minutes=150,
        )
        small_workload = SimpleNamespace(
            title='Small workload', priority='Medium', status='Pending',
            due_date=today + timedelta(days=3), estimated_minutes=20,
        )
        large_workload = SimpleNamespace(
            title='Large workload', priority='Medium', status='Pending',
            due_date=today + timedelta(days=3), estimated_minutes=300,
        )
        completed = SimpleNamespace(
            title='Completed', priority='High', status='Completed',
            due_date=today + timedelta(days=4), estimated_minutes=90,
        )
        cancelled = SimpleNamespace(
            title='Cancelled', priority='Medium', status='Cancelled',
            due_date=today + timedelta(days=4), estimated_minutes=90,
        )
        boundary = SimpleNamespace(
            title='Boundary', priority='High', status='Pending',
            due_date=today + timedelta(days=7), estimated_minutes=240,
        )

        far_result = calculate_priority_score(far_deadline, today=today)
        near_result = calculate_priority_score(near_deadline, today=today)
        overdue_result = calculate_priority_score(overdue, today=today)
        low_importance_result = calculate_priority_score(low_importance, today=today)
        high_importance_result = calculate_priority_score(high_importance, today=today)
        small_workload_result = calculate_priority_score(small_workload, today=today)
        large_workload_result = calculate_priority_score(large_workload, today=today)
        completed_result = calculate_priority_score(completed, today=today)
        cancelled_result = calculate_priority_score(cancelled, today=today)
        boundary_result = calculate_priority_score(boundary, today=today)

        self.assertGreater(near_result['score'], far_result['score'])
        self.assertGreater(overdue_result['score'], near_result['score'])
        self.assertGreater(high_importance_result['score'], low_importance_result['score'])
        self.assertGreater(large_workload_result['score'], small_workload_result['score'])
        self.assertEqual(completed_result['score'], 0)
        self.assertEqual(cancelled_result['score'], 0)
        self.assertEqual(boundary_result['factors']['days_until_deadline'], 7)
        self.assertEqual(boundary_result['factors']['estimated_hours'], 4.0)
        self.assertIn('Task was cancelled', cancelled_result['reasons'])

    def test_priority_engine_handles_null_and_boundary_deadline_values(self):
        today = date(2026, 9, 13)
        no_deadline = SimpleNamespace(
            title='No deadline', priority='Medium', status='Pending',
            due_date=None, estimated_minutes=0,
        )
        same_day = SimpleNamespace(
            title='Same day', priority='High', status='Pending',
            due_date=today, estimated_minutes=180,
        )

        no_deadline_result = calculate_priority_score(no_deadline, today=today)
        same_day_result = calculate_priority_score(same_day, today=today)

        self.assertEqual(no_deadline_result['factors']['days_until_deadline'], 0)
        self.assertEqual(no_deadline_result['score'], 37)
        self.assertGreater(same_day_result['score'], no_deadline_result['score'])


class PriorityViewTests(TestCase):
    def test_task_detail_page_displays_explanation(self):
        user = get_user_model().objects.create_user(username='priority-user', password='pass12345')
        task = Task.objects.create(
            user=user,
            title='Lab report',
            description='Draft the report before class.',
            priority='High',
            status='Pending',
            due_date=date.today() + timedelta(days=1),
            estimated_minutes=300,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('task_detail', args=[task.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Priority:')
        self.assertContains(response, 'Why?')
        self.assertContains(response, 'Deadline is approaching')
