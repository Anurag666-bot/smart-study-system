"""Deterministic, explainable task priority scoring for the smart study system."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping


PRIORITY_WEIGHTS = {
    'High': 25,
    'Medium': 17,
    'Low': 10,
}


def _safe_get(task: Any, name: str, default=None):
    if isinstance(task, Mapping):
        return task.get(name, default)
    return getattr(task, name, default)


def _deadline_score(due_date: date | None, today: date) -> int:
    if due_date is None:
        return 10

    delta_days = (due_date - today).days
    if delta_days < 0:
        overdue_days = abs(delta_days)
        return min(35, 20 + overdue_days * 2)
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
    difficulty = _safe_get(task, 'difficulty', 'Medium')

    score = 0
    if estimated_minutes > 0:
        score += min(18, estimated_minutes // 10)

    if difficulty == 'Hard':
        score += 7
    elif difficulty == 'Medium':
        score += 4
    else:
        score += 2

    return min(25, score)


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

    Format:
        {
            'score': 87,
            'level': 'high',
            'factors': {
                'deadline_score': 32,
                'importance_score': 25,
                'workload_score': 18,
                'status_score': 12,
            },
        }
    """
    if today is None:
        today = date.today()

    if task is None:
        return {'score': 0, 'level': 'low', 'factors': {
            'deadline_score': 0,
            'importance_score': 0,
            'workload_score': 0,
            'status_score': 0,
        }}

    deadline_score = _deadline_score(_safe_get(task, 'due_date', None), today)
    importance_score = _importance_score(_safe_get(task, 'priority', 'Medium'))
    workload_score = _workload_score(task)
    status_score = _status_score(_safe_get(task, 'status', 'Pending'))

    factors = {
        'deadline_score': deadline_score,
        'importance_score': importance_score,
        'workload_score': workload_score,
        'status_score': status_score,
    }

    score = sum(factors.values())
    score = max(0, min(100, score))

    return {
        'score': score,
        'level': _level_for_score(score),
        'factors': factors,
    }
