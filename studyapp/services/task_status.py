"""Task deadline classification for overdue, near-term, and completed work."""

from __future__ import annotations

from datetime import date
from typing import Any


_TASK_STATUS_LABELS = {
    'overdue': 'Overdue',
    'due_today': 'Due Today',
    'due_tomorrow': 'Due Tomorrow',
    'upcoming': 'Upcoming',
    'completed': 'Completed',
}


_TASK_STATUS_CLASSES = {
    'overdue': 'task-status-overdue',
    'due_today': 'task-status-due-today',
    'due_tomorrow': 'task-status-due-tomorrow',
    'upcoming': 'task-status-upcoming',
    'completed': 'task-status-completed',
}


def classify_task(task: Any, *, today: date | None = None) -> str:
    """Return a coarse deadline status for a task."""
    today = today or date.today()
    if task is None:
        return 'upcoming'

    status = getattr(task, 'status', None)
    if status == 'Completed':
        return 'completed'

    due_date = getattr(task, 'due_date', None)
    if due_date is None:
        return 'upcoming'

    delta_days = (due_date - today).days
    if delta_days < 0:
        return 'overdue'
    if delta_days == 0:
        return 'due_today'
    if delta_days == 1:
        return 'due_tomorrow'
    return 'upcoming'


def task_status_label(task: Any, *, today: date | None = None) -> str:
    return _TASK_STATUS_LABELS.get(classify_task(task, today=today), 'Upcoming')


def task_status_css_class(task: Any, *, today: date | None = None) -> str:
    return _TASK_STATUS_CLASSES.get(classify_task(task, today=today), 'task-status-upcoming')


def task_status_summary(task: Any, *, today: date | None = None) -> dict:
    key = classify_task(task, today=today)
    return {
        'status': key,
        'label': _TASK_STATUS_LABELS.get(key, 'Upcoming'),
        'css_class': _TASK_STATUS_CLASSES.get(key, 'task-status-upcoming'),
    }
