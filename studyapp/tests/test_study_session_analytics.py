from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from studyapp.models import StudySession, Subject
from studyapp.services.analytics import get_study_session_analytics


class StudySessionAnalyticsTests(TestCase):
    """Tests for study session analytics measurements."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='study-user', password='pass12345')
        self.subject_math = Subject.objects.create(name='Mathematics', code='MATH101')
        self.subject_physics = Subject.objects.create(name='Physics', code='PHY101')
        self.subject_english = Subject.objects.create(name='English', code='ENG101')
        self.today = date(2026, 9, 20)  # Sunday
        self.now = timezone.make_aware(datetime.combine(self.today, datetime.min.time()))

    def test_today_study_time_calculation(self):
        """Test that today's study time is correctly calculated."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Create sessions for today
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_math,
            started_at=today_start + timedelta(hours=8),
            duration_minutes=60,
        )
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_physics,
            started_at=today_start + timedelta(hours=14),
            duration_minutes=45,
        )
        # Create session for yesterday (should not be included)
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_english,
            started_at=today_start - timedelta(days=1, hours=2),
            duration_minutes=30,
        )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        self.assertEqual(analytics['today_study_time_minutes'], 105)  # 60 + 45
        self.assertEqual(analytics['today_sessions_count'], 2)

    def test_weekly_study_time_calculation(self):
        """Test that weekly study time spans the week correctly."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        # today is Sunday (2026-09-20), so week starts Monday 2026-09-14
        week_start = today_start - timedelta(days=today_start.weekday())

        # Create sessions throughout the week
        for i in range(7):
            day_offset = timedelta(days=i)
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_math,
                started_at=week_start + day_offset + timedelta(hours=9),
                duration_minutes=30 + (i * 5),  # Vary durations
            )

        # Create session from previous week (should not be included)
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_physics,
            started_at=week_start - timedelta(days=1),
            duration_minutes=45,
        )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        # Expected: 30+35+40+45+50+55+60 = 315
        expected_weekly = sum(30 + (i * 5) for i in range(7))
        self.assertEqual(analytics['weekly_study_time_minutes'], expected_weekly)
        self.assertEqual(analytics['week_sessions_count'], 7)

    def test_monthly_study_time_calculation(self):
        """Test that monthly study time spans the entire month correctly."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Create sessions throughout the month
        for day in range(1, 21):
            session_date = month_start.replace(day=day)
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_math if day % 2 == 0 else self.subject_physics,
                started_at=session_date + timedelta(hours=10),
                duration_minutes=45,
            )

        # Create session from next month (should not be included)
        next_month_start = month_start.replace(day=1) + timedelta(days=32)
        next_month_start = next_month_start.replace(day=1)
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_english,
            started_at=next_month_start,
            duration_minutes=50,
        )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        expected_monthly = 45 * 20
        self.assertEqual(analytics['monthly_study_time_minutes'], expected_monthly)
        self.assertEqual(analytics['sessions_completed'], 20)

    def test_average_session_duration_calculation(self):
        """Test that average session duration is correctly calculated."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Create sessions with varying durations
        durations = [30, 45, 60, 75, 90]
        for duration in durations:
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_math,
                started_at=month_start + timedelta(hours=duration % 24),
                duration_minutes=duration,
            )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        expected_average = sum(durations) / len(durations)
        self.assertEqual(analytics['average_session_duration_minutes'], round(expected_average, 2))

    def test_average_session_duration_with_started_ended_times(self):
        """Test average session duration calculation using started_at and ended_at."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Create sessions with started_at and ended_at (no duration_minutes)
        for i in range(3):
            start = month_start + timedelta(hours=i*2)
            end = start + timedelta(minutes=50)
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_math,
                started_at=start,
                ended_at=end,
                duration_minutes=None,
            )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        # Average should be 50 minutes
        self.assertEqual(analytics['average_session_duration_minutes'], 50.0)

    def test_sessions_completed_count(self):
        """Test that sessions completed count includes all sessions in the month."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Create exactly 15 sessions in current month
        for i in range(15):
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_math,
                started_at=month_start + timedelta(hours=i),
                duration_minutes=30,
            )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        self.assertEqual(analytics['sessions_completed'], 15)

    def test_most_studied_subject_identification(self):
        """Test that the most studied subject is correctly identified."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Math: 3 sessions × 60 min = 180 min
        for i in range(3):
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_math,
                started_at=month_start + timedelta(hours=i),
                duration_minutes=60,
            )

        # Physics: 2 sessions × 90 min = 180 min
        for i in range(2):
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_physics,
                started_at=month_start + timedelta(hours=10 + i),
                duration_minutes=90,
            )

        # English: 2 sessions × 50 min = 100 min
        for i in range(2):
            StudySession.objects.create(
                user=self.user,
                subject=self.subject_english,
                started_at=month_start + timedelta(hours=20 + i),
                duration_minutes=50,
            )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        # Math and Physics are tied at 180; should return one of them
        self.assertIn(analytics['most_studied_subject'], ['Mathematics', 'Physics'])

    def test_most_studied_subject_with_general_sessions(self):
        """Test handling of sessions with no subject (General)."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Create named subject session
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_math,
            started_at=month_start,
            duration_minutes=30,
        )

        # Create general (no subject) sessions
        for i in range(2):
            StudySession.objects.create(
                user=self.user,
                subject=None,
                started_at=month_start + timedelta(hours=1 + i),
                duration_minutes=40,
            )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        # General should have 80 minutes, Mathematics should have 30
        self.assertEqual(analytics['most_studied_subject'], 'General')

    def test_subject_breakdown_report(self):
        """Test that subject breakdown correctly aggregates time by subject."""
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Create sessions for different subjects
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_math,
            started_at=month_start,
            duration_minutes=120,
        )
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_math,
            started_at=month_start + timedelta(hours=2),
            duration_minutes=90,
        )
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_physics,
            started_at=month_start + timedelta(hours=4),
            duration_minutes=100,
        )

        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        self.assertEqual(analytics['subject_breakdown']['Mathematics'], 210)
        self.assertEqual(analytics['subject_breakdown']['Physics'], 100)

    def test_empty_analytics_for_no_sessions(self):
        """Test that analytics returns zeros when no sessions exist."""
        analytics = get_study_session_analytics(self.user, today=self.today, now=self.now)

        self.assertEqual(analytics['today_study_time_minutes'], 0)
        self.assertEqual(analytics['weekly_study_time_minutes'], 0)
        self.assertEqual(analytics['monthly_study_time_minutes'], 0)
        self.assertEqual(analytics['average_session_duration_minutes'], 0.0)
        self.assertEqual(analytics['sessions_completed'], 0)
        self.assertIsNone(analytics['most_studied_subject'])
        self.assertEqual(analytics['subject_breakdown'], {})

    def test_analytics_for_different_users(self):
        """Test that analytics are isolated per user."""
        other_user = get_user_model().objects.create_user(username='other-user', password='pass12345')
        today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Create sessions for both users in the same month
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_math,
            started_at=month_start,
            duration_minutes=100,
        )
        StudySession.objects.create(
            user=other_user,
            subject=self.subject_math,
            started_at=month_start + timedelta(hours=1),
            duration_minutes=200,
        )

        analytics_user1 = get_study_session_analytics(self.user, today=self.today, now=self.now)
        analytics_user2 = get_study_session_analytics(other_user, today=self.today, now=self.now)

        self.assertEqual(analytics_user1['monthly_study_time_minutes'], 100)
        self.assertEqual(analytics_user2['monthly_study_time_minutes'], 200)

    def test_analytics_across_month_boundaries(self):
        """Test that analytics correctly handle month boundaries."""
        # August 31, 2026 is the last day of August
        august_31 = timezone.make_aware(datetime(2026, 8, 31, 10, 0))
        september_1 = timezone.make_aware(datetime(2026, 9, 1, 10, 0))

        StudySession.objects.create(
            user=self.user,
            subject=self.subject_math,
            started_at=august_31,
            duration_minutes=60,
        )
        StudySession.objects.create(
            user=self.user,
            subject=self.subject_physics,
            started_at=september_1,
            duration_minutes=45,
        )

        # Analytics for September 1st should only include September sessions
        analytics = get_study_session_analytics(
            self.user,
            today=september_1.date(),
            now=september_1
        )

        self.assertEqual(analytics['monthly_study_time_minutes'], 45)
        self.assertEqual(analytics['sessions_completed'], 1)
