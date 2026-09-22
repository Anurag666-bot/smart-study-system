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
