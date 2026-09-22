from datetime import date, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase

from .algorithms.priority_scheduler import (
    calculate_priority_score,
    explain_score,
    prioritize_tasks,
)
from .algorithms.textrank_summary import textrank_summary
from .algorithms.tfidf_search import tfidf_search
from .services.priority import calculate_priority_score as service_calculate_priority_score


class PrioritySchedulerTests(SimpleTestCase):
    def test_overdue_work_always_outranks_future_work_and_completed_is_last(self):
        today = date(2026, 9, 13)
        overdue_low = SimpleNamespace(
            id=1, title='Overdue', priority='Low', status='Pending',
            due_date=today - timedelta(days=1),
        )
        future_high = SimpleNamespace(
            id=2, title='Future', priority='High', status='Pending',
            due_date=today + timedelta(days=1),
        )
        completed_overdue = SimpleNamespace(
            id=3, title='Done', priority='High', status='Completed',
            due_date=today - timedelta(days=30),
        )
        self.assertGreater(
            calculate_priority_score(overdue_low, today),
            calculate_priority_score(future_high, today),
        )
        ordered = prioritize_tasks(
            [completed_overdue, future_high, overdue_low], today=today
        )
        self.assertEqual(ordered[:2], [overdue_low, future_high])
        self.assertEqual(explain_score(overdue_low, today)['reason_codes'][0], 'overdue')
        self.assertLessEqual(calculate_priority_score(overdue_low, today), 100)


class ServicePriorityTests(SimpleTestCase):
    def test_priority_service_returns_deterministic_explained_score(self):
        today = date(2026, 9, 13)
        task = SimpleNamespace(
            title='Project defense prep',
            priority='High',
            status='In Progress',
            due_date=today + timedelta(days=1),
            estimated_minutes=180,
            difficulty='Hard',
        )

        result = service_calculate_priority_score(task, today=today)

        self.assertIn('score', result)
        self.assertIn('level', result)
        self.assertIn('factors', result)
        self.assertEqual(result['score'], sum(result['factors'].values()))
        self.assertIn(result['level'], {'high', 'medium', 'low'})
        self.assertGreater(result['score'], 0)


class SearchAndSummaryTests(SimpleTestCase):
    def test_tfidf_rejects_misaligned_inputs_and_invalid_top_k(self):
        with self.assertRaises(ValueError):
            tfidf_search('study', ['study notes'], [1, 2])
        with self.assertRaises(ValueError):
            tfidf_search('study', ['study notes'], [1], top_k=-1)

    def test_tfidf_and_summary_handle_empty_input(self):
        self.assertEqual(tfidf_search('', [], [], top_k=5), [])
        self.assertEqual(textrank_summary('', num_sentences=1), '')
        with self.assertRaises(ValueError):
            textrank_summary('A sufficiently long sentence for testing.', num_sentences=0)
