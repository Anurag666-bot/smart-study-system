from .policies import has_permission


def role_navigation(request):
    """Expose role-aware navigation flags without trusting presentation for auth."""
    user = getattr(request, 'user', None)
    return {
        'can_access_admin_panel': has_permission(user, 'admin.dashboard.view'),
        'can_manage_academics': has_permission(user, 'admin.dashboard.view'),
        'is_teacher': has_permission(user, 'student_progress.read'),
    }
