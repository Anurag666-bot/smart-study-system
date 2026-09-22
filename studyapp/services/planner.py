"""Deterministic adaptive study-plan suggestions.

The planner is a rule-based recommendation service. It previews allocations and
never writes a StudyPlan row unless a caller explicitly persists the result.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from ..models import Exam, ExamResult, PlannerEvent, StudentSubject, StudySession, Task


MAX_DAYS = 14
MAX_SUBJECTS = 100
MAX_ROWS_PER_KIND = 500


def generate_study_plan(
    user,
    start_date,
    end_date,
    available_hours,
    *,
    now=None,
    session_duration=60,
    daily_limit=180,
):
    """Generate study-session suggestions for a date window while honoring time caps.

    ``available_hours`` may be either a single numeric value for the whole window or
    a mapping of specific dates to available hours. Each day is limited by both the
    day-specific budget and the global ``daily_limit``.
    """
    if start_date is None or end_date is None:
        raise ValueError('start_date and end_date are required')
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError('start_date and end_date must be date objects')
    if start_date > end_date:
        raise ValueError('start_date must be on or before end_date')

    try:
        session_duration = int(session_duration)
    except (TypeError, ValueError) as exc:
        raise ValueError('session_duration must be an integer') from exc
    if session_duration <= 0:
        raise ValueError('session_duration must be greater than zero')

    try:
        daily_limit = int(daily_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError('daily_limit must be an integer') from exc
    if daily_limit <= 0:
        raise ValueError('daily_limit must be greater than zero')

    day_range = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
    if isinstance(available_hours, dict):
        normalized = {}
        for day_key, hours in available_hours.items():
            if isinstance(day_key, datetime):
                day_key = day_key.date()
            if not isinstance(day_key, date):
                raise ValueError('available_hours keys must be date values')
            try:
                hours_value = float(hours)
            except (TypeError, ValueError) as exc:
                raise ValueError('available_hours values must be numeric') from exc
            if hours_value < 0:
                raise ValueError('available_hours values must be non-negative')
            normalized[day_key] = hours_value
        for day in day_range:
            normalized.setdefault(day, 0.0)
    else:
        try:
            total_hours = float(available_hours)
        except (TypeError, ValueError) as exc:
            raise ValueError('available_hours must be numeric or a date-to-hour mapping') from exc
        if total_hours < 0:
            raise ValueError('available_hours must be non-negative')
        total_minutes = int(round(total_hours * 60))
        day_count = len(day_range) or 1
        per_day = max(0, int(round(total_minutes / day_count)))
        normalized = {day: max(0, per_day / 60) for day in day_range}

    suggestions = []
    for day in day_range:
        available_minutes = min(
            max(0, int(round(normalized.get(day, 0.0) * 60))),
            daily_limit,
        )
        if available_minutes <= 0:
            continue
        day_suggestions = build_adaptive_plan(
            user,
            start_date=day,
            days=1,
            available_minutes_per_day=available_minutes,
            now=now,
            session_duration=session_duration,
            daily_limit=daily_limit,
        )
        for item in day_suggestions:
            minutes = int(item['minutes'])
            if minutes > session_duration:
                minutes = session_duration
            item['minutes'] = minutes
            item['date'] = day
            suggestions.append(item)

    return suggestions


def _session_minutes(session):
    if session.duration_minutes:
        return int(session.duration_minutes)
    if session.ended_at and session.started_at:
        return max(0, int((session.ended_at - session.started_at).total_seconds() // 60))
    return 0


def _urgency(dates, start_date):
    if not dates:
        return 0.0
    return max(
        1.0 if due <= start_date else max(0.0, 1.0 - (due - start_date).days / 30)
        for due in dates
    )


def _priority_weight(priority):
    values = {'High': 1.0, 'Medium': 0.65, 'Low': 0.3}
    return values.get(priority, 0.5)


def _subject_score(stats, start_date):
    urgency = max(
        _urgency(stats['task_dates'], start_date),
        _urgency(stats['exam_dates'], start_date),
    )
    priority_average = stats['priority_weight'] / max(stats['task_count'], 1)
    workload_factor = min(1.0, stats['task_minutes'] / 180)
    weakness = 1.0 - stats['exam_average'] / 100 if stats['exam_average'] is not None else 0.5
    under_studied = max(0.0, 1.0 - min(stats['session_minutes'] / 180, 1.0))
    score = round(
        (0.50 * urgency + 0.25 * priority_average + 0.15 * workload_factor + 0.10 * weakness + 0.05 * under_studied) * 100,
        2,
    )
    reasons = []
    if any(due <= start_date for due in stats['task_dates'] + stats['exam_dates']):
        reasons.append('deadline-or-exam-imminent')
    elif urgency:
        reasons.append('upcoming-deadline')
    if priority_average >= 0.8:
        reasons.append('high-priority-workload')
    if stats['task_minutes'] >= 120:
        reasons.append('heavy-workload')
    if stats['exam_average'] is not None and stats['exam_average'] < 60:
        reasons.append('weak-exam-performance')
    elif stats['exam_average'] is None:
        reasons.append('no-exam-history')
    if stats['session_minutes'] < 60:
        reasons.append('low-recent-study-time')
    return score, reasons or ['balanced-practice']


def build_adaptive_plan(
    user,
    *,
    start_date=None,
    days=7,
    available_minutes_per_day=120,
    now=None,
    session_duration=60,
    daily_limit=None,
):
    """Return explainable daily allocations without mutating database rows.

    Only active subjects enrolled by ``user`` are considered. Pending task and
    upcoming exam dates drive urgency; recent sessions and exam averages drive
    balance. Planner events block a date when any active event overlaps it.
    Queries and generated slots are bounded for predictable request cost.
    """
    current_now = now or timezone.now()
    if start_date is None:
        start_date = timezone.localdate(current_now)
    if not isinstance(start_date, date):
        raise ValueError('start_date must be a date')
    try:
        days = int(days)
        available_minutes_per_day = int(available_minutes_per_day)
        session_duration = int(session_duration)
    except (TypeError, ValueError) as exc:
        raise ValueError('days, available_minutes_per_day, and session_duration must be integers') from exc
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f'days must be between 1 and {MAX_DAYS}')
    if session_duration <= 0:
        raise ValueError('session_duration must be greater than zero')
    if daily_limit is None:
        daily_limit = 720
    try:
        daily_limit = int(daily_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError('daily_limit must be an integer') from exc
    if not 30 <= available_minutes_per_day <= daily_limit:
        raise ValueError(f'available_minutes_per_day must be between 30 and {daily_limit}')

    enrollments = list(
        StudentSubject.objects.filter(
            student=user,
            is_active=True,
            subject__is_active=True,
        ).select_related('subject').order_by('subject__name')[:MAX_SUBJECTS]
    )
    if not enrollments:
        return []
    subject_ids = [enrollment.subject_id for enrollment in enrollments]
    stats = {
        subject_id: {
            'subject': enrollment.subject,
            'task_dates': [],
            'exam_dates': [],
            'session_minutes': 0,
            'exam_values': [],
            'exam_average': None,
            'priority_weight': 0.0,
            'task_minutes': 0,
            'task_count': 0,
            'assignments': 0,
        }
        for subject_id, enrollment in ((e.subject_id, e) for e in enrollments)
    }

    tasks = Task.objects.filter(
        user=user,
        subject_id__in=subject_ids,
    ).exclude(status='Completed').order_by('due_date', 'pk')[:MAX_ROWS_PER_KIND]
    for task in tasks:
        if task.subject_id and task.due_date:
            stats[task.subject_id]['task_dates'].append(task.due_date)
            stats[task.subject_id]['priority_weight'] += _priority_weight(getattr(task, 'priority', 'Medium'))
            stats[task.subject_id]['task_minutes'] += int(task.estimated_minutes or 0)
            stats[task.subject_id]['task_count'] += 1

    exams = list(
        Exam.objects.filter(
            subject_id__in=subject_ids,
            is_archived=False,
            exam_date__lte=start_date + timedelta(days=days),
        ).order_by('exam_date', 'pk')[:MAX_ROWS_PER_KIND]
    )
    exams_by_id = {exam.pk: exam for exam in exams}
    for exam in exams:
        stats[exam.subject_id]['exam_dates'].append(exam.exam_date)
    results = ExamResult.objects.filter(
        student=user,
        exam_id__in=exams_by_id,
    ).order_by('-graded_at')[:MAX_ROWS_PER_KIND]
    for result in results:
        exam = exams_by_id.get(result.exam_id)
        if exam:
            stats[exam.subject_id]['exam_values'].append(result.percentage)

    session_window_start = current_now - timedelta(days=30)
    sessions = StudySession.objects.filter(
        user=user,
        subject_id__in=subject_ids,
        started_at__gte=session_window_start,
    ).order_by('-started_at')[:MAX_ROWS_PER_KIND]
    for session in sessions:
        if session.subject_id:
            stats[session.subject_id]['session_minutes'] += _session_minutes(session)

    for subject_stats in stats.values():
        values = subject_stats['exam_values']
        subject_stats['exam_average'] = round(sum(values) / len(values), 2) if values else None
        subject_stats['base_score'], subject_stats['reasons'] = _subject_score(
            subject_stats, start_date
        )

    horizon_end = start_date + timedelta(days=days - 1)
    current_tz = timezone.get_current_timezone()
    horizon_start = timezone.make_aware(
        datetime.combine(start_date, time.min),
        current_tz,
    )
    horizon_limit = timezone.make_aware(
        datetime.combine(horizon_end + timedelta(days=1), time.min),
        current_tz,
    )
    blocked_dates = {
        timezone.localtime(event.starts_at).date()
        for event in PlannerEvent.objects.filter(
            user=user,
            is_deleted=False,
            starts_at__lt=horizon_limit,
            ends_at__gt=horizon_start,
        )[:MAX_ROWS_PER_KIND]
    }

    candidates = list(stats.values())
    allocations = []
    minimum_block = min(30, session_duration)
    for offset in range(days):
        plan_date = start_date + timedelta(days=offset)
        if plan_date in blocked_dates:
            continue
        remaining = available_minutes_per_day
        while remaining >= minimum_block and candidates:
            chosen = max(
                candidates,
                key=lambda item: (
                    item['base_score'] / (1 + item['assignments']),
                    item['base_score'],
                    -len(item['reasons']),
                    item['subject'].name,
                ),
            )
            minutes = min(session_duration, remaining)
            chosen['assignments'] += 1
            allocations.append({
                'date': plan_date,
                'subject': chosen['subject'],
                'minutes': minutes,
                'priority': round(
                    chosen['base_score'] / (1 + chosen['assignments'] - 1), 2
                ),
                'reasons': list(chosen['reasons']),
            })
            remaining -= minutes

    return allocations
