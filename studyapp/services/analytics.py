"""Bounded, explainable student analytics derived from persisted activity."""

from collections import defaultdict
from datetime import timedelta

from django.db import OperationalError
from django.utils import timezone

from ..models import Attendance, Exam, ExamResult, Goal, StudentSubject, StudySession, Task
from .attendance import calculate_attendance


RECENT_DAYS = 30


def _session_minutes(session):
    if session.duration_minutes:
        return int(session.duration_minutes)
    if session.ended_at and session.started_at:
        return max(0, int((session.ended_at - session.started_at).total_seconds() // 60))
    return 0


def _consecutive_session_days(sessions, today):
    """Count a streak ending today; an absent current day intentionally gives 0."""
    dates = {timezone.localtime(session.started_at).date() for session in sessions}
    streak = 0
    current = today
    while current in dates:
        streak += 1
        current -= timedelta(days=1)
    return streak


def _percentage(numerator, denominator):
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _get_student_analytics(user, *, today=None, now=None, recent_days=RECENT_DAYS):
    """Return deterministic dashboard metrics for one user.

    The service only reads a bounded recent window for session/attendance trends;
    task and result totals remain scoped to the user's own rows.
    """
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    window_start = now - timedelta(days=max(1, recent_days))
    sessions = list(
        StudySession.objects.filter(
            user=user,
            started_at__gte=window_start,
            started_at__lte=now,
        ).select_related('subject').order_by('started_at')[:500]
    )
    attendance = Attendance.objects.filter(
        user=user,
        date__gte=today - timedelta(days=max(1, recent_days) - 1),
        date__lte=today,
    )
    tasks = Task.objects.filter(user=user)
    results = ExamResult.objects.filter(
        student=user,
    ).select_related('exam__subject').order_by('-graded_at')[:500]

    subject_minutes = defaultdict(int)
    subject_result_values = defaultdict(list)
    for session in sessions:
        key = session.subject.name if session.subject else 'General'
        subject_minutes[key] += _session_minutes(session)
    for result in results:
        subject_result_values[result.exam.subject.name].append(result.percentage)

    subject_performance = [
        {
            'subject': subject,
            'study_minutes': minutes,
            'exam_average': round(sum(subject_result_values.get(subject, [])) / len(subject_result_values[subject]), 2)
            if subject in subject_result_values else None,
        }
        for subject, minutes in sorted(subject_minutes.items())
    ]
    # Include result-only subjects so a result is never silently omitted.
    for subject, values in sorted(subject_result_values.items()):
        if subject not in subject_minutes:
            subject_performance.append({
                'subject': subject,
                'study_minutes': 0,
                'exam_average': round(sum(values) / len(values), 2),
            })

    attendance_summary = calculate_attendance(attendance)
    attendance_total = attendance_summary['scheduled_classes']
    attendance_present = attendance_summary['attended_classes']
    completed_tasks = tasks.filter(status='Completed').count()
    total_tasks = tasks.count()
    goals = Goal.objects.filter(user=user, status='ACTIVE')
    goal_progress = [
        {
            'title': goal.title,
            'percent': min(100.0, round(float(goal.current_value / goal.target_value * 100), 2)),
        }
        for goal in goals[:100]
    ]

    return {
        'subjects': StudentSubject.objects.filter(student=user, is_active=True).count(),
        'pending_tasks': tasks.exclude(status='Completed').count(),
        'completed_tasks': completed_tasks,
        'total_tasks': total_tasks,
        'task_completion_percent': _percentage(completed_tasks, total_tasks),
        'study_minutes_recent': sum(_session_minutes(session) for session in sessions),
        'study_sessions_recent': len(sessions),
        'attendance_total_recent': attendance_total,
        'attendance_present_recent': attendance_present,
        'attendance_percent_recent': _percentage(attendance_present, attendance_total),
        'current_streak': _consecutive_session_days(sessions, today),
        'subject_performance': subject_performance,
        'goal_progress': goal_progress,
        'window_days': recent_days,
    }


def _legacy_analytics(user, *, today, recent_days):
    """Keep dashboard reads usable during a rolling migration deployment."""
    attendance = Attendance.objects.filter(
        user=user,
        date__gte=today - timedelta(days=max(1, recent_days) - 1),
        date__lte=today,
    )
    tasks = Task.objects.filter(user=user)
    completed = tasks.filter(status='Completed').count()
    total = tasks.count()
    attendance_summary = calculate_attendance(attendance)
    present = attendance_summary['attended_classes']
    total_attendance = attendance_summary['scheduled_classes']
    return {
        'subjects': 0,
        'pending_tasks': tasks.exclude(status='Completed').count(),
        'completed_tasks': completed,
        'total_tasks': total,
        'task_completion_percent': _percentage(completed, total),
        'study_minutes_recent': 0,
        'study_sessions_recent': 0,
        'attendance_total_recent': total_attendance,
        'attendance_present_recent': present,
        'attendance_percent_recent': _percentage(present, total_attendance),
        'current_streak': 0,
        'subject_performance': [],
        'goal_progress': [],
        'window_days': recent_days,
    }


def get_subject_progress(user, *, recent_days=RECENT_DAYS):
    """Return per-subject progress signals for planning and prioritization."""
    enrollments = StudentSubject.objects.filter(student=user, is_active=True).select_related('subject')
    recent_window = timezone.now() - timedelta(days=max(1, recent_days))
    progress = []

    for enrollment in enrollments:
        subject = enrollment.subject
        exam_results = list(
            ExamResult.objects.filter(
                student=user,
                exam__subject=subject,
            ).select_related('exam')
        )
        exam_scores = [result.percentage for result in exam_results]
        average_score = round(sum(exam_scores) / len(exam_scores), 2) if exam_scores else None
        recent_minutes = sum(
            _session_minutes(session)
            for session in StudySession.objects.filter(
                user=user,
                subject=subject,
                started_at__gte=recent_window,
            )
        )
        progress_score = (
            max(0.0, 100.0 - average_score) / 100.0 if average_score is not None else 0.5
        )
        progress.append({
            'subject': subject.name,
            'subject_id': subject.pk,
            'average_score': average_score,
            'progress_score': progress_score,
            'recent_minutes': recent_minutes,
        })

    return sorted(progress, key=lambda item: (item['progress_score'], item['subject']))


def get_student_analytics(user, *, today=None, now=None, recent_days=RECENT_DAYS):
    """Return analytics while tolerating an un-migrated rolling deployment."""
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    try:
        return _get_student_analytics(
            user, today=today, now=now, recent_days=recent_days
        )
    except OperationalError:
        return _legacy_analytics(user, today=today, recent_days=recent_days)


def get_task_analytics(user, *, today=None):
    """Return a compact summary for a user's task workload."""
    today = today or timezone.localdate()
    tasks = Task.objects.filter(user=user)

    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='Completed').count()
    overdue_tasks = tasks.filter(status__in=['Pending', 'In Progress']).filter(
        due_date__lt=today
    ).count()
    pending_tasks = tasks.filter(status='Pending').count()

    completion_percentage = round(
        (completed_tasks / total_tasks) * 100,
        2,
    ) if total_tasks else 0.0

    completed_task_times = []
    for task in tasks.filter(status='Completed').only('created_at', 'completed_at'):
        if task.completed_at and task.created_at:
            completed_task_times.append(
                (task.completed_at - task.created_at).total_seconds() / 3600
            )

    average_completion_time_hours = (
        round(sum(completed_task_times) / len(completed_task_times), 2)
        if completed_task_times
        else 0.0
    )

    return {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks,
        'completion_percentage': completion_percentage,
        'task_completion_percent': completion_percentage,
        'average_completion_time_hours': average_completion_time_hours,
    }
