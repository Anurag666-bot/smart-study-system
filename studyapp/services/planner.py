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


def generate_study_plan(user, start_date, end_date, available_hours, *, now=None):
    """Generate a bounded sequence of study-session suggestions for a date window.

    This public API is the service-level contract expected by the app during the
    planner milestone. It reuses the adaptive planner's logic and converts the
    requested total available hours into a per-day allocation across the date
    window.
    """
    if start_date is None or end_date is None:
        raise ValueError('start_date and end_date are required')
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError('start_date and end_date must be date objects')
    if start_date > end_date:
        raise ValueError('start_date must be on or before end_date')

    try:
        available_hours = float(available_hours)
    except (TypeError, ValueError) as exc:
        raise ValueError('available_hours must be numeric') from exc
    if available_hours <= 0:
        raise ValueError('available_hours must be greater than zero')

    day_count = (end_date - start_date).days + 1
    total_minutes = max(0, int(round(available_hours * 60)))
    if total_minutes == 0:
        return []

    per_day_minutes = max(30, int(round(total_minutes / day_count)))
    if per_day_minutes > 720:
        per_day_minutes = 720

    return build_adaptive_plan(
        user,
        start_date=start_date,
        days=day_count,
        available_minutes_per_day=per_day_minutes,
        now=now,
    )


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


def _subject_score(stats, start_date):
    urgency = max(
        _urgency(stats['task_dates'], start_date),
        _urgency(stats['exam_dates'], start_date),
    )
    weakness = 1.0 - stats['exam_average'] / 100 if stats['exam_average'] is not None else 0.5
    under_studied = max(0.0, 1.0 - min(stats['session_minutes'] / 180, 1.0))
    score = round((0.45 * urgency + 0.35 * weakness + 0.20 * under_studied) * 100, 2)
    reasons = []
    if any(due <= start_date for due in stats['task_dates'] + stats['exam_dates']):
        reasons.append('deadline-or-exam-imminent')
    elif urgency:
        reasons.append('upcoming-deadline')
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
    except (TypeError, ValueError) as exc:
        raise ValueError('days and available_minutes_per_day must be integers') from exc
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f'days must be between 1 and {MAX_DAYS}')
    if not 30 <= available_minutes_per_day <= 720:
        raise ValueError('available_minutes_per_day must be between 30 and 720')

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
    for offset in range(days):
        plan_date = start_date + timedelta(days=offset)
        if plan_date in blocked_dates:
            continue
        remaining = available_minutes_per_day
        while remaining >= 30 and candidates:
            chosen = max(
                candidates,
                key=lambda item: (
                    item['base_score'] / (1 + item['assignments']),
                    item['base_score'],
                    -len(item['reasons']),
                    item['subject'].name,
                ),
            )
            minutes = min(60, remaining)
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
