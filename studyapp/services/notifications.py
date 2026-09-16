"""Idempotent notification generation kept outside model save signals."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from ..models import Attendance, EventReminder, Goal, Notification, PlannerEvent, Task


ACTIVE_TASK_STATUSES = ('Pending', 'In Progress')


def create_notification(*, user, notification_type, title, message, dedup_key=None):
    """Create one notification and return ``(notification, created)``.

    A stable key makes repeated scheduler runs safe.  A caller that wants every
    occurrence can omit the key, while deadline/reminder jobs should provide one.
    """
    if dedup_key is None:
        return Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
        ), True
    try:
        with transaction.atomic():
            notification, created = Notification.objects.get_or_create(
                user=user,
                dedup_key=dedup_key,
                defaults={
                    'notification_type': notification_type,
                    'title': title,
                    'message': message,
                },
            )
    except IntegrityError:
        notification = Notification.objects.get(user=user, dedup_key=dedup_key)
        created = False
    return notification, created


def generate_user_notifications(user, *, today=None, now=None, horizon_days=1):
    """Generate deadline and planner reminders for one user.

    The query is bounded to the requested horizon and every generated item has
    a deterministic key, so this function is suitable for cron/management jobs.
    """
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    horizon_days = max(0, min(int(horizon_days), 30))
    generated = []

    tasks = Task.objects.filter(
        user=user,
        status__in=ACTIVE_TASK_STATUSES,
        due_date__lte=today + timedelta(days=horizon_days),
    ).order_by('due_date', 'pk')[:500]
    for task in tasks:
        if task.due_date < today:
            kind = 'overdue'
            title = 'Task overdue'
            message = f'“{task.title}” was due on {task.due_date}.'
        else:
            kind = 'deadline'
            title = 'Task deadline approaching'
            message = f'“{task.title}” is due on {task.due_date}.'
        notification, created = create_notification(
            user=user,
            notification_type='DEADLINE',
            title=title,
            message=message,
            dedup_key=f'task-{kind}-{task.pk}-{task.due_date.isoformat()}',
        )
        if created:
            generated.append(notification)

    due_reminders = EventReminder.objects.filter(
        event__user=user,
        event__is_completed=False,
        event__is_deleted=False,
        sent_at__isnull=True,
        remind_at__lte=now,
    ).select_related('event').order_by('remind_at', 'pk')[:500]

    # An explicitly scheduled reminder replaces the generic event notice.
    events = PlannerEvent.objects.filter(
        user=user,
        is_completed=False,
        is_deleted=False,
        starts_at__gte=now,
        starts_at__lte=now + timedelta(days=horizon_days + 1),
    ).exclude(reminders__isnull=False).order_by('starts_at', 'pk')[:500]
    for event in events:
        notification, created = create_notification(
            user=user,
            notification_type='REMINDER',
            title='Upcoming planner event',
            message=f'“{event.title}” starts at {event.starts_at:%Y-%m-%d %H:%M}.',
            dedup_key=f'event-{event.pk}-{event.starts_at.isoformat()}',
        )
        if created:
            generated.append(notification)

    for reminder in due_reminders:
        notification, created = create_notification(
            user=user,
            notification_type='REMINDER',
            title='Planner reminder',
            message=f'“{reminder.event.title}” starts at {reminder.event.starts_at:%Y-%m-%d %H:%M}.',
            dedup_key=f'event-reminder-{reminder.pk}',
        )
        reminder.sent_at = now
        reminder.save(update_fields=['sent_at'])
        if created:
            generated.append(notification)

    attendance = Attendance.objects.filter(
        user=user,
        date__gte=today - timedelta(days=29),
        date__lte=today,
    )
    attendance_total = attendance.count()
    attendance_present = attendance.filter(
        Q(status__in=['PRESENT', 'LATE']) | Q(is_present=True)
    ).distinct().count()
    if attendance_total >= 3 and attendance_present / attendance_total < 0.75:
        notification, created = create_notification(
            user=user,
            notification_type='ATTENDANCE',
            title='Attendance needs attention',
            message=(
                f'Attendance is {attendance_present / attendance_total:.0%} over '
                'the last 30 days. Review your attendance plan.'
            ),
            dedup_key=f'attendance-low-{today:%Y-%m}',
        )
        if created:
            generated.append(notification)

    goals = Goal.objects.filter(
        user=user,
        status='ACTIVE',
        target_date__lte=today + timedelta(days=horizon_days),
    ).order_by('target_date', 'pk')[:100]
    for goal in goals:
        if goal.current_value >= goal.target_value:
            continue
        notification, created = create_notification(
            user=user,
            notification_type='GOAL',
            title='Goal deadline approaching',
            message=f'“{goal.title}” is due on {goal.target_date}.',
            dedup_key=f'goal-{goal.pk}-{goal.target_date.isoformat()}',
        )
        if created:
            generated.append(notification)

    return generated
