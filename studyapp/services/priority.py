"""Deterministic, explainable task priority scoring for the smart study system."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping


PRIORITY_WEIGHTS = {
    'High': 35,
    'Medium': 22,
    'Low': 10,
}


def _safe_get(task: Any, name: str, default=None):
    if isinstance(task, Mapping):
        return task.get(name, default)
    return getattr(task, name, default)


def _deadline_score(due_date: date | None, today: date) -> int:
    if due_date is None:
        return 0

    delta_days = (due_date - today).days
    if delta_days < 0:
        return 40 + min(20, abs(delta_days) * 2)
    if delta_days == 0:
        return 35
    if delta_days <= 2:
        return 30
    if delta_days <= 7:
        return 22
    if delta_days <= 14:
        return 15
    return 8


def _importance_score(priority: Any) -> int:
    return PRIORITY_WEIGHTS.get(priority, PRIORITY_WEIGHTS['Medium'])


def _workload_score(task: Any) -> int:
    estimated_minutes = _safe_get(task, 'estimated_minutes', 0) or 0
    estimated_hours = estimated_minutes / 60.0
    difficulty = _safe_get(task, 'difficulty', 'Medium')

    workload = min(25, int(estimated_hours * 5))
    if difficulty == 'Hard':
        workload += 8
    elif difficulty == 'Medium':
        workload += 5
    else:
        workload += 2
    return min(35, workload)


def _status_score(status: Any) -> int:
    if status == 'Completed':
        return 0
    if status == 'In Progress':
        return 15
    if status == 'Pending':
        return 10
    return 5


def _level_for_score(score: int) -> str:
    if score >= 70:
        return 'high'
    if score >= 40:
        return 'medium'
    return 'low'


def calculate_priority_score(task: Any, *, today: date | None = None) -> dict:
    """Return a deterministic explanation object for a task's priority.

    The factors are intentionally explicit so a task with a short deadline and a
    large workload is scored differently from a task with a long runway and a
    smaller workload. The service keeps the output stable and explainable.
    """
    if today is None:
        today = date.today()

    if task is None:
        return {
            'score': 0,
            'level': 'low',
            'factors': {
                'days_until_deadline': 0,
                'estimated_hours': 0.0,
                'importance': 'Medium',
                'status': 'Pending',
                'deadline_score': 0,
                'importance_score': 0,
                'workload_score': 0,
                'status_score': 0,
            },
        }

    due_date = _safe_get(task, 'due_date', None)
    days_until_deadline = (due_date - today).days if due_date is not None else 0
    estimated_minutes = _safe_get(task, 'estimated_minutes', 0) or 0
    estimated_hours = round(estimated_minutes / 60.0, 2)
    importance = _safe_get(task, 'priority', 'Medium')
    status = _safe_get(task, 'status', 'Pending')

    deadline_score = _deadline_score(due_date, today)
    importance_score = _importance_score(importance)
    workload_score = _workload_score(task)
    status_score = _status_score(status)

    factors = {
        'days_until_deadline': days_until_deadline,
        'estimated_hours': estimated_hours,
        'importance': importance,
        'status': status,
        'deadline_score': deadline_score,
        'importance_score': importance_score,
        'workload_score': workload_score,
        'status_score': status_score,
    }

    score = deadline_score + importance_score + workload_score + status_score
    score = max(0, min(100, score))

    return {
        'score': score,
        'level': _level_for_score(score),
        'factors': factors,
    }
