"""Idempotent achievement evaluation from real study activity."""

from datetime import timedelta

from django.utils import timezone

from ..models import Achievement, StudySession, Task, UserAchievement


ACHIEVEMENT_DEFINITIONS = (
    {
        'code': 'first-session',
        'name': 'First Study Session',
        'description': 'Record your first completed study session.',
        'points': 10,
    },
    {
        'code': 'ten-completed-tasks',
        'name': 'Task Finisher',
        'description': 'Complete ten study tasks.',
        'points': 25,
    },
    {
        'code': 'seven-day-streak',
        'name': 'Seven Day Streak',
        'description': 'Study on seven consecutive calendar days.',
        'points': 50,
    },
)


def ensure_achievement_definitions():
    """Create stable catalogue rows without duplicating existing achievements."""
    achievements = {}
    for definition in ACHIEVEMENT_DEFINITIONS:
        achievement, _ = Achievement.objects.get_or_create(
            code=definition['code'],
            defaults=definition,
        )
        achievements[achievement.code] = achievement
    return achievements


def _has_seven_day_streak(user, today):
    dates = set(
        StudySession.objects.filter(
            user=user,
            started_at__date__gte=today - timedelta(days=6),
            started_at__date__lte=today,
        ).values_list('started_at__date', flat=True)
    )
    return all(today - timedelta(days=offset) in dates for offset in range(7))


def evaluate_user_achievements(user, *, today=None):
    """Award all currently satisfied achievements and return new awards."""
    today = today or timezone.localdate()
    catalogue = ensure_achievement_definitions()
    satisfied = set()
    if StudySession.objects.filter(user=user).exists():
        satisfied.add('first-session')
    if Task.objects.filter(user=user, status='Completed').count() >= 10:
        satisfied.add('ten-completed-tasks')
    if _has_seven_day_streak(user, today):
        satisfied.add('seven-day-streak')

    awarded = []
    for code in sorted(satisfied):
        user_achievement, created = UserAchievement.objects.get_or_create(
            user=user,
            achievement=catalogue[code],
        )
        if created:
            awarded.append(user_achievement)
    return awarded
