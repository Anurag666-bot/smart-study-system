"""
Study Recommendation Engine for Smart Study System
Provides personalized study recommendations based on user activity, tasks, and study patterns.
"""

from datetime import timedelta
from django.db.models import Count, Q
from collections import Counter
import json

from django.utils import timezone

from ..models import Note, Task, StudyPlan, ActivityLog


def get_study_recommendations(user, limit=5):
    """
    Generate personalized study recommendations for a user.

    Args:
        user: Django User object
        limit: Maximum number of recommendations to return

    Returns:
        List of recommendation dictionaries
    """
    recommendations = []

    # Get user's recent activity (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_activity = ActivityLog.objects.filter(
        user=user,
        timestamp__gte=week_ago
    ).values_list('model_name', 'action')

    # Get user's notes and tasks
    user_notes = Note.objects.filter(user=user)
    user_tasks = Task.objects.filter(user=user)
    user_study_plans = StudyPlan.objects.filter(user=user)

    # Recommendation 1: Based on recent activity patterns
    if recent_activity:
        activity_rec = _generate_activity_based_recommendation(
            user, recent_activity, user_notes, user_tasks
        )
        if activity_rec:
            recommendations.append(activity_rec)

    # Recommendation 2: Based on upcoming deadlines
    deadline_rec = _generate_deadline_based_recommendation(user_tasks)
    if deadline_rec:
        recommendations.append(deadline_rec)

    # Recommendation 3: Based on study plan consistency
    study_plan_rec = _generate_study_plan_recommendation(user_study_plans, user_notes)
    if study_plan_rec:
        recommendations.append(study_plan_rec)

    # Recommendation 4: Based on subject balance
    subject_rec = _generate_subject_balance_recommendation(user_notes, user_study_plans)
    if subject_rec:
        recommendations.append(subject_rec)

    # Recommendation 5: Based on task completion patterns
    completion_rec = _generate_completion_pattern_recommendation(user_tasks)
    if completion_rec:
        recommendations.append(completion_rec)

    # Remove duplicates and limit results
    seen = set()
    unique_recommendations = []
    for rec in recommendations:
        rec_key = rec.get('title', '') + rec.get('description', '')
        if rec_key not in seen:
            seen.add(rec_key)
            unique_recommendations.append(rec)

    return unique_recommendations[:limit]


def _generate_activity_based_recommendation(user, recent_activity, user_notes, user_tasks):
    """Generate recommendation based on recent user activity."""
    # Count activities by type
    model_counts = Counter([model for model, action in recent_activity])
    action_counts = Counter([action for model, action in recent_activity])

    # If user has been creating notes but not studying them recently
    if model_counts.get('Note', 0) > action_counts.get('UPDATE', 0):
        # Find notes that haven't been updated recently
        week_ago = timezone.now() - timedelta(days=3)
        stale_notes = user_notes.filter(updated_at__lt=week_ago)[:3]

        if stale_notes.exists():
            note_titles = [note.title for note in stale_notes]
            return {
                'type': 'review',
                'title': 'Review Your Recent Notes',
                'description': f"You've created {len(note_titles)} new note{'s' if len(note_titles) > 1 else ''} recently. Consider reviewing: {', '.join(note_titles[:2])}{'...' if len(note_titles) > 2 else ''}",
                'priority': 'medium',
                'action_url': '/notes/',
                'action_text': 'View All Notes',
                'icon': '📝'
            }

    # If user has been updating tasks but not completing them
    if action_counts.get('UPDATE', 0) > 3:
        incomplete_tasks = user_tasks.exclude(status='Completed')[:3]
        if incomplete_tasks.exists():
            task_titles = [task.title for task in incomplete_tasks]
            return {
                'type': 'task',
                'title': 'Focus on Pending Tasks',
                'description': f"You have {len(task_titles)} task{'s' if len(task_titles) > 1 else ''} in progress. Consider completing: {', '.join(task_titles[:2])}{'...' if len(task_titles) > 2 else ''}",
                'priority': 'high',
                'action_url': '/tasks/',
                'action_text': 'View Tasks',
                'icon': '✅'
            }

    return None


def _generate_deadline_based_recommendation(user_tasks):
    """Generate recommendation based on upcoming deadlines."""
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    three_days_later = today + timedelta(days=3)

    # Tasks due today or tomorrow (urgent)
    urgent_tasks = user_tasks.filter(
        due_date__in=[today, tomorrow],
        status__in=['Pending', 'In Progress']
    )

    if urgent_tasks.exists():
        task_titles = [task.title for task in urgent_tasks[:2]]
        return {
            'type': 'deadline',
            'title': 'Urgent Deadlines Approaching',
            'description': f"You have {urgent_tasks.count()} task{'s' if urgent_tasks.count() > 1 else ''} due today or tomorrow: {', '.join(task_titles)}{'...' if urgent_tasks.count() > 2 else ''}",
            'priority': 'high',
            'action_url': '/tasks/',
            'action_text': 'View Urgent Tasks',
            'icon': '⚠️'
        }

    # Tasks due in 3 days (upcoming)
    upcoming_tasks = user_tasks.filter(
        due_date=three_days_later,
        status__in=['Pending', 'In Progress']
    )

    if upcoming_tasks.exists():
        task_titles = [task.title for task in upcoming_tasks[:2]]
        return {
            'type': 'deadline',
            'title': 'Upcoming Deadlines',
            'description': f"You have {upcoming_tasks.count()} task{'s' if upcoming_tasks.count() > 1 else ''} due in 3 days: {', '.join(task_titles)}{'...' if upcoming_tasks.count() > 2 else ''}",
            'priority': 'medium',
            'action_url': '/tasks/',
            'action_text': 'View Upcoming Tasks',
            'icon': '📅'
        }

    return None


def _generate_study_plan_recommendation(user_study_plans, user_notes):
    """Generate recommendation based on study plan consistency."""
    if not user_study_plans.exists():
        return {
            'type': 'planning',
            'title': 'Create a Study Plan',
            'description': "You don't have any study plans yet. Creating a study plan can help you organize your learning goals and track your progress.",
            'priority': 'medium',
            'action_url': '/planner/',
            'action_text': 'Create Study Plan',
            'icon': '📚'
        }

    # Check if study plans have associated notes
    plans_without_notes = 0
    total_plans = user_study_plans.count()

    for plan in user_study_plans:
        # Simple check: look for notes containing the subject
        if not user_notes.filter(
            Q(title__icontains=plan.subject) |
            Q(content__icontains=plan.subject)
        ).exists():
            plans_without_notes += 1

    if plans_without_notes > total_plans * 0.5:  # More than half of plans lack notes
        return {
            'type': 'planning',
            'title': 'Enhance Your Study Plans with Notes',
            'description': f"You have {plans_without_notes} study plan{'s' if plans_without_notes > 1 else ''} that could benefit from detailed notes. Consider adding notes to reinforce your learning.",
            'priority': 'medium',
            'action_url': '/notes/upload/',
            'action_text': 'Create Study Notes',
            'icon': '📝'
        }

    return None


def _generate_subject_balance_recommendation(user_notes, user_study_plans):
    """Generate recommendation based on subject balance."""
    # Get subjects from notes
    note_subjects = []
    for note in user_notes:
        # Simple extraction: first few words or title as subject
        subject = note.title.split()[0] if note.title.split() else "General"
        note_subjects.append(subject)

    # Get subjects from study plans
    plan_subjects = list(user_study_plans.values_list('subject', flat=True))

    all_subjects = note_subjects + plan_subjects

    if not all_subjects:
        return None

    subject_counts = Counter(all_subjects)
    most_common_subject, count = subject_counts.most_common(1)[0]

    # If one subject dominates (>60% of activity)
    if count > len(all_subjects) * 0.6 and len(subject_counts) > 1:
        # Suggest exploring other subjects
        other_subjects = [sub for sub in subject_counts.keys() if sub != most_common_subject]
        if other_subjects:
            return {
                'type': 'balance',
                'title': 'Explore Other Subjects',
                'description': f"You've been focusing heavily on {most_common_subject}. Consider diversifying your study with: {', '.join(other_subjects[:3])}",
                'priority': 'low',
                'action_url': '/notes/upload/',
                'action_text': 'Create New Notes',
                'icon': '🔄'
            }

    return None


def _generate_completion_pattern_recommendation(user_tasks):
    """Generate recommendation based on task completion patterns."""
    completed_tasks = user_tasks.filter(status='Completed')
    total_tasks = user_tasks.count()

    if total_tasks == 0:
        return None

    completion_rate = completed_tasks.count() / total_tasks if total_tasks > 0 else 0

    # Low completion rate
    if completion_rate < 0.5 and total_tasks >= 3:
        # Find patterns in incomplete tasks
        incomplete_tasks = user_tasks.exclude(status='Completed')
        priority_counts = Counter([task.priority for task in incomplete_tasks])

        if priority_counts:
            most_common_priority = priority_counts.most_common(1)[0][0]
            return {
                'type': 'motivation',
                'title': 'Improve Task Completion',
                'description': f"You've completed {completion_rate:.0%} of your tasks. Many of your {most_common_priority.lower()} priority tasks are incomplete. Try breaking them into smaller steps.",
                'priority': 'medium',
                'action_url': '/tasks/',
                'action_text': 'View Tasks',
                'icon': '💪'
            }

    # High completion rate - suggest challenge
    elif completion_rate > 0.8 and total_tasks >= 5:
        return {
            'type': 'challenge',
            'title': 'Challenge Yourself',
            'description': f"You're completing {completion_rate:.0%} of your tasks! Consider adding some stretch goals or more challenging topics to your study plan.",
            'priority': 'low',
            'action_url': '/planner/',
            'action_text': 'Create Study Plan',
            'icon': '🌟'
        }

    return None


def get_recommendation_summary(user):
    """
    Get a summary of recommendations for dashboard display.

    Args:
        user: Django User object

    Returns:
        Dictionary with recommendation summary
    """
    recommendations = get_study_recommendations(user, limit=3)

    return {
        'count': len(recommendations),
        'recommendations': recommendations,
        'has_urgent': any(rec.get('priority') == 'high' for rec in recommendations),
        'categories': list(set([rec.get('type') for rec in recommendations if rec.get('type')]))
    }