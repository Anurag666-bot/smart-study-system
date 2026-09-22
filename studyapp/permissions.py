"""Centralized role authorization helpers built on the existing UserRole model."""

from django.db import OperationalError, ProgrammingError

from .models import UserRole

ROLE_ALIASES = {
    'admin': 'administrator',
    'administrator': 'administrator',
    'teacher': 'teacher',
    'student': 'student',
}


def _usable_user(user):
    return bool(
        user is not None
        and getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_active', False)
    )


def _normalize_role_name(role_name):
    if role_name is None:
        return None
    if hasattr(role_name, 'code'):
        role_name = role_name.code
    if not isinstance(role_name, str):
        role_name = str(role_name)
    return ROLE_ALIASES.get(role_name.strip().lower(), role_name.strip().lower())


def user_has_role(user, role_name):
    """Return whether a user has the provided application role assignment."""
    normalized = _normalize_role_name(role_name)
    if not normalized or not _usable_user(user):
        return False
    if normalized == 'administrator' and getattr(user, 'is_superuser', False):
        return True
    try:
        return UserRole.objects.filter(
            profile__user_id=user.pk,
            role__code=normalized,
        ).exists()
    except (OperationalError, ProgrammingError):
        return False


def require_role(user, role_name):
    """Return True when the user satisfies the requested role boundary."""
    return user_has_role(user, role_name)


def is_student(user):
    return user_has_role(user, 'student')


def is_teacher(user):
    return user_has_role(user, 'teacher')


def is_admin(user):
    return user_has_role(user, 'administrator')
