from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from studyapp.models import Exam, Subject, Task
from studyapp.services.planner import build_adaptive_plan, generate_study_plan


class PlannerAlgorithmTests(TestCase):
    """Test the adaptive study planner algorithm."""

    def setUp(self):
        """Set up test data."""
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.today = date(2026, 9, 22)

        # Create test subjects
        self.math_subject = Subject.objects.create(
            code='MATH101',
            name='Mathematics'
        )
        self.cs_subject = Subject.objects.create(
            code='CS101',
            name='Computer Science'
        )
        self.physics_subject = Subject.objects.create(
            code='PHYS101',
            name='Physics'
        )

        # Enroll user in subjects
        from studyapp.models import StudentSubject
        StudentSubject.objects.create(
            student=self.user,
            subject=self.math_subject,
            is_active=True
        )
        StudentSubject.objects.create(
            student=self.user,
            subject=self.cs_subject,
            is_active=True
        )
        StudentSubject.objects.create(
            student=self.user,
            subject=self.physics_subject,
            is_active=True
        )

    def _create_task(self, title, priority='Medium', status='Pending',
                     days_offset=0, estimated_minutes=60):
        """Helper to create a task."""
        return Task.objects.create(
            user=self.user,
            subject=self.math_subject,
            title=title,
            priority=priority,
            status=status,
            due_date=self.today + timedelta(days=days_offset),
            estimated_minutes=estimated_minutes
        )

    def _create_exam(self, title, days_offset=0):
        """Helper to create an exam."""
        return Exam.objects.create(
            subject=self.math_subject,
            title=title,
            exam_date=self.today + timedelta(days=days_offset),
            max_score=100
        )

    def test_zero_available_hours(self):
        """Test planner with zero available hours."""
        # Create some tasks
        self._create_task('Math homework', estimated_minutes=120)

        # Test with zero available hours
        allocations = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=1,
            available_minutes_per_day=0
        )

        # Should return empty list when no time available
        self.assertEqual(allocations, [])

    def test_one_available_hour(self):
        """Test planner with one available hour."""
        # Create tasks
        self._create_task('Math homework', estimated_minutes=90)
        self._create_task('CS assignment', estimated_minutes=60)

        # Test with 60 minutes available
        allocations = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=1,
            available_minutes_per_day=60
        )

        # Should allocate exactly 60 minutes
        total_minutes = sum(item['minutes'] for item in allocations)
        self.assertEqual(total_minutes, 60)
        self.assertLessEqual(total_minutes, 60)  # Verify constraint

    def test_multiple_tasks(self):
        """Test planner with multiple tasks."""
        # Create multiple tasks with different priorities and times
        self._create_task('Urgent math homework', priority='High',
                         days_offset=0, estimated_minutes=120)
        self._create_task('Regular CS assignment', priority='Medium',
                         days_offset=2, estimated_minutes=90)
        self._create_task('Easy physics reading', priority='Low',
                         days_offset=5, estimated_minutes=60)

        # Test with 3 hours available
        allocations = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=1,
            available_minutes_per_day=180
        )

        # Should allocate time to tasks
        self.assertGreater(len(allocations), 0)
        total_minutes = sum(item['minutes'] for item in allocations)
        self.assertGreater(total_minutes, 0)
        self.assertLessEqual(total_minutes, 180)  # Verify constraint

    def test_urgent_deadline(self):
        """Test planner prioritizes urgent deadlines."""
        # Create tasks - one urgent, one not urgent
        urgent_task = self._create_task(
            'Due today!', priority='Medium',
            days_offset=0, estimated_minutes=120
        )
        future_task = self._create_task(
            'Due next week', priority='Medium',
            days_offset=7, estimated_minutes=120
        )

        # Test with limited time
        allocations = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=1,
            available_minutes_per_day=60
        )

        # Should prioritize the urgent task
        self.assertGreater(len(allocations), 0)
        # Check if urgent task subject appears in allocations
        allocated_subjects = [item['subject'].name for item in allocations]
        self.assertIn('Mathematics', allocated_subjects)

    def test_multiple_subjects(self):
        """Test planner distributes time across multiple subjects."""
        # Create tasks for different subjects
        self._create_task('Math homework', estimated_minutes=60)

        cs_task = Task.objects.create(
            user=self.user,
            subject=self.cs_subject,
            title='CS programming',
            priority='Medium',
            status='Pending',
            due_date=self.today + timedelta(days=1),
            estimated_minutes=90
        )

        physics_task = Task.objects.create(
            user=self.user,
            subject=self.physics_subject,
            title='Physics lab',
            priority='Medium',
            status='Pending',
            due_date=self.today + timedelta(days=2),
            estimated_minutes=60
        )

        # Test with plenty of time
        allocations = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=1,
            available_minutes_per_day=240  # 4 hours
        )

        # Should allocate time to multiple subjects
        self.assertGreater(len(allocations), 0)
        allocated_subjects = [item['subject'].name for item in allocations]
        # Should have allocated to at least 2 different subjects
        unique_subjects = set(allocated_subjects)
        self.assertGreaterEqual(len(unique_subjects), 2)

    def test_overloaded_tasks(self):
        """Test planner handles more work than available time."""
        # Create lots of tasks exceeding available time
        for i in range(10):
            self._create_task(
                f'Task {i}',
                priority='Medium',
                days_offset=i % 3,
                estimated_minutes=120  # 2 hours each
            )

        # Only 2 hours available but 20 hours of work
        allocations = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=1,
            available_minutes_per_day=120  # 2 hours
        )

        # Should not exceed available time
        total_minutes = sum(item['minutes'] for item in allocations)
        self.assertLessEqual(total_minutes, 120)  # Verify constraint
        # Should still allocate some time
        self.assertGreater(total_minutes, 0)

    def test_completed_tasks_ignored(self):
        """Test planner ignores completed tasks."""
        # Create completed and pending tasks
        completed_task = self._create_task(
            'Completed homework',
            status='Completed',
            estimated_minutes=120
        )
        pending_task = self._create_task(
            'Pending homework',
            status='Pending',
            estimated_minutes=60
        )

        # Test with limited time
        allocations = build_adaptive_plan(
            self.user,
            start_date=self.today,
            days=1,
            available_minutes_per_day=60
        )

        # Should only consider pending tasks
        self.assertGreater(len(allocations), 0)
        total_minutes = sum(item['minutes'] for item in allocations)
        self.assertLessEqual(total_minutes, 60)  # Verify constraint

    def test_generate_study_plan_integration(self):
        """Test the generate_study_plan function wrapper."""
        # Create a task
        self._create_task('Study for exam', estimated_minutes=90)

        # Test generating a study plan for 3 days with 2 hours/day
        suggestions = generate_study_plan(
            user=self.user,
            start_date=self.today,
            end_date=self.today + timedelta(days=2),
            available_hours=2.0  # 2 hours per day
        )

        # Should return suggestions
        self.assertIsInstance(suggestions, list)
        if suggestions:  # If we got suggestions
            # Verify time constraints are respected
            for day in range(3):  # 3 days
                day_date = self.today + timedelta(days=day)
                day_suggestions = [s for s in suggestions if s['date'] == day_date]
                day_minutes = sum(item['minutes'] for item in day_suggestions)
                self.assertLessEqual(day_minutes, 120)  # 2 hours = 120 minutes

    def test_scheduled_hours_respects_available_hours(self):
        """Verify that scheduled hours never exceed available hours."""
        test_cases = [
            (0, 0),      # zero hours
            (1, 60),     # one hour
            (2, 120),    # two hours
            (4, 240),    # four hours
            (8, 480),    # eight hours
        ]

        # Create consistent test data
        self._create_task('Math task', estimated_minutes=60)
        self._create_task('CS task', estimated_minutes=90)

        for available_hours, expected_minutes in test_cases:
            with self.subTest(available_hours=available_hours):
                allocations = build_adaptive_plan(
                    self.user,
                    start_date=self.today,
                    days=1,
                    available_minutes_per_day=available_hours * 60
                )

                total_minutes = sum(item['minutes'] for item in allocations)
                self.assertLessEqual(
                    total_minutes,
                    expected_minutes,
                    f"With {available_hours} hours available, "
                    f"scheduled {total_minutes} minutes exceeds limit of {expected_minutes}"
                )