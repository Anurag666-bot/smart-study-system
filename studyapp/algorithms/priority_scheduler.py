"""
Priority Scheduler
==================

Ranks tasks by a weighted combination of:
  - importance  (how much the task matters — High / Medium / Low)
  - urgency     (how close the deadline is — grows continuously as the
                 due date approaches, and keeps growing the longer a
                 task sits overdue, instead of capping out)

score = importance_weight(task) * urgency(task)

Design notes
------------
- Weights are configurable (not hardcoded), so this can be tuned or
  A/B tested without touching the scoring logic.
- Urgency is a continuous function of days remaining, not a 3-step
  lookup table — a task due in 1 day and a task due in 6 days should
  not tie just because they both fall in the same bucket.
- Overdue tasks are ranked strictly above non-overdue tasks and keep
  climbing in urgency the longer they're ignored (with a sane ceiling
  so one 400-days-overdue task doesn't dominate everything forever).
- Ties are broken deterministically by due date, then by task id/name
  if available, so re-running the sort always gives the same order —
  important for tests and for user trust ("why did this reorder?").
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence, Any


DEFAULT_IMPORTANCE_WEIGHTS = {
    "High": 3.0,
    "Medium": 2.0,
    "Low": 1.0,
}


@dataclass(frozen=True)
class SchedulerConfig:
    importance_weights: dict = None
    default_importance_weight: float = 2.0   # used if priority label is missing/unrecognized
    urgency_floor: float = 1.0               # minimum urgency for a task with no due date
    urgency_ceiling: float = 20.0             # cap so extremely overdue tasks don't blow out the scale
    due_soon_window_days: int = 9             # over how many days urgency ramps from ceiling-ish to floor
    overdue_growth_per_day: float = 0.5       # how fast urgency keeps climbing once overdue

    def weight_for(self, priority: Optional[str]) -> float:
        weights = self.importance_weights or DEFAULT_IMPORTANCE_WEIGHTS
        return weights.get(priority, self.default_importance_weight)


DEFAULT_CONFIG = SchedulerConfig()


def _days_left(due_date: Optional[date], today: Optional[date] = None) -> Optional[int]:
    if due_date is None:
        return None
    today = today or date.today()
    return (due_date - today).days


def compute_urgency(
    due_date: Optional[date],
    today: Optional[date] = None,
    config: SchedulerConfig = DEFAULT_CONFIG,
) -> float:
    """
    Continuous urgency score.

    - No due date          -> low, constant urgency (config.urgency_floor)
    - Overdue               -> starts at ~10 and keeps climbing with days overdue,
                               capped at config.urgency_ceiling
    - Due in the future     -> linearly ramps down from ~10 (due today) to
                               config.urgency_floor at config.due_soon_window_days out
    """
    days_left = _days_left(due_date, today)

    if days_left is None:
        return config.urgency_floor

    if days_left < 0:
        overdue_days = -days_left
        urgency = 10.0 + overdue_days * config.overdue_growth_per_day
        return min(urgency, config.urgency_ceiling)

    # Linear ramp: 10 at "due today", floor at due_soon_window_days or later
    window = max(config.due_soon_window_days, 1)
    urgency = 10.0 - (10.0 - config.urgency_floor) * (days_left / window)
    return max(config.urgency_floor, urgency)


def calculate_priority_score(
    task: Any,
    today: Optional[date] = None,
    config: SchedulerConfig = DEFAULT_CONFIG,
) -> float:
    """Return a bounded 0–100 score; completed work is never active priority.

    The overdue branch starts at 70, while every non-overdue score is below 70.
    That explicit separation makes the important product rule (overdue work must
    outrank future work) hold regardless of the importance label.
    """
    if getattr(task, 'status', None) == 'Completed':
        return 0.0

    due_date = getattr(task, 'due_date', None)
    days_left = _days_left(due_date, today)
    urgency = compute_urgency(due_date, today, config)
    weights = config.importance_weights or DEFAULT_IMPORTANCE_WEIGHTS
    max_weight = max(weights.values()) or 1.0
    importance_ratio = config.weight_for(getattr(task, 'priority', None)) / max_weight

    if days_left is not None and days_left < 0:
        overdue_days = min(-days_left, 15)
        score = 70.0 + (overdue_days / 15.0) * 30.0
    else:
        urgency_ratio = min(1.0, urgency / max(config.urgency_ceiling, 1.0))
        # Non-overdue work stays strictly below the overdue band.
        score = (importance_ratio * 35.0) + (urgency_ratio * 34.0)

    return round(max(0.0, min(100.0, score)), 2)


def explain_score(task: Any, today: Optional[date] = None, config: SchedulerConfig = DEFAULT_CONFIG) -> dict:
    """Return score components and human-readable reason codes."""
    days_left = _days_left(getattr(task, 'due_date', None), today)
    urgency = compute_urgency(getattr(task, 'due_date', None), today, config)
    score = calculate_priority_score(task, today, config)
    reasons = []
    if getattr(task, 'status', None) == 'Completed':
        reasons.append('completed')
    elif days_left is not None and days_left < 0:
        reasons.append('overdue')
    elif days_left == 0:
        reasons.append('due-today')
    elif days_left is not None and days_left <= config.due_soon_window_days:
        reasons.append('due-soon')
    else:
        reasons.append('no-deadline' if days_left is None else 'future-deadline')
    priority = getattr(task, 'priority', None)
    if priority in {'High', 'Medium', 'Low'}:
        reasons.append(f'priority-{priority.lower()}')
    return {
        'priority': priority,
        'importance_weight': config.weight_for(priority),
        'days_left': days_left,
        'urgency': round(urgency, 2),
        'score': score,
        'reason_codes': reasons,
    }


def prioritize_tasks(
    tasks: Sequence[Any],
    today: Optional[date] = None,
    config: SchedulerConfig = DEFAULT_CONFIG,
) -> list:
    """
    Returns tasks sorted by descending priority score.

    Tie-breaking, in order:
      1. Higher score first
      2. Earlier due date first (None due dates sort last)
      3. Task name/id, alphabetically, as a final deterministic fallback
    """
    def sort_key(task: Any):
        score = calculate_priority_score(task, today, config)
        due_date = getattr(task, 'due_date', None)
        due_date_key = due_date if due_date is not None else date.max
        fallback = str(getattr(task, 'id', getattr(task, 'name', getattr(task, 'title', ''))))
        completed_last = getattr(task, 'status', None) == 'Completed'
        return (completed_last, -score, due_date_key, fallback)

    return sorted(tasks, key=sort_key)