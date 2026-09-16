"""Code-owned RBAC policy contract for the first authorization slice."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, ProgrammingError
from django.shortcuts import redirect

from .models import UserRole

STUDENT = 'student'
TEACHER = 'teacher'
ADMINISTRATOR = 'administrator'

PERMISSIONS = {
    'study.self_service',
    'activity.read_own',
    'student_progress.read',
    'teacher.students.read',
    'teacher.reports.view',
    'exam_results.manage',
    'attendance.read_any',
    'attendance.manage_any',
    'admin.dashboard.view',
    'users.manage',
    'announcements.view',
    'activity.read_any',
    'roles.manage',
}

ROLE_PERMISSIONS = {
    STUDENT: frozenset({'study.self_service', 'activity.read_own'}),
    TEACHER: frozenset({
        'study.self_service',
        'activity.read_own',
        'student_progress.read',
        'teacher.students.read',
        'teacher.reports.view',
        'exam_results.manage',
        'attendance.read_any',
        'attendance.manage_any',
    }),
    ADMINISTRATOR: frozenset(PERMISSIONS),
}


def _usable_user(user):
    return bool(
        user is not None
        and getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_active', False)
    )


def has_role(user, role_code):
    """Return whether the user has an explicit active role assignment."""
    if not _usable_user(user):
        return False
    try:
        return UserRole.objects.filter(
            profile__user_id=user.pk,
            role__code=role_code,
        ).exists()
    except (OperationalError, ProgrammingError):
        # Fail closed while a rolling deployment is between migrations.
        return False


def assigned_roles(user):
    """Return explicit role codes without treating staff as a business role."""
    if not _usable_user(user):
        return set()
    try:
        return set(UserRole.objects.filter(
            profile__user_id=user.pk,
        ).values_list('role__code', flat=True))
    except (OperationalError, ProgrammingError):
        return set()


def has_permission(user, permission):
    """Check a policy key; superusers retain a documented break-glass path."""
    if permission not in PERMISSIONS or not _usable_user(user):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return any(
        permission in ROLE_PERMISSIONS.get(role_code, frozenset())
        for role_code in assigned_roles(user)
    )


def permission_required(permission):
    """Protect a view with a named policy permission and default deny."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not has_permission(request.user, permission):
                messages.error(request, 'You do not have permission to access that page.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
