# Security architecture

This project applies Django's default security model and a small custom RBAC layer to keep the application safe for a multi-user academic workflow.

## Authentication

Authentication is handled through Django's built-in user model and login flow. The application uses the standard `AuthenticationForm` plus the Django session framework to establish authenticated user state.

Key practices:
- login is required for protected pages and state-changing actions
- anonymous users are redirected to the login flow
- logout is POST-only and clears the session state
- username/password validation is enforced before session creation

This prevents weak or accidental anonymous access to protected dashboards, task lists, and study records.

## Authorization

Authorization is not based only on `is_staff` or `is_superuser`. The app separates the Django admin role from the application role system.

The project uses application roles stored through `Profile` and `UserRole`, with role checks provided in `studyapp/permissions.py` and policy enforcement in `studyapp/policies.py`.

Examples:
- students are restricted to their own study records and student workflows
- teachers may access assigned subjects, student lists, and exam management features
- administrators retain a break-glass policy for governed platform actions

This keeps permissions explicit and auditable instead of relying on implicit staff status.

## RBAC

The application implements a lightweight role-based access control model:

- Student: self-service academic workflows
- Teacher: subject-scoped academic management and student reporting
- Administrator: platform management, role assignment, and audit-facing actions

Permission checks are centralized through named policy keys, so new views can reuse the same access model instead of scattering ad hoc checks across the codebase.

Common enforcement pattern:
- `require_role(request.user, 'student')` for student-only routes
- `has_permission(request.user, 'admin.dashboard.view')` for admin-only views
- `permission_required(...)` decorators for policy-owned views

## Object-level access control

Object-level access control protects records when a user changes an ID in the URL.

The application uses ownership-aware queries such as:

- `get_object_or_404(Note, id=note_id, user=request.user)`
- `get_object_or_404(Task, pk=task_id, user=request.user)`
- `get_object_or_404(Goal, pk=goal_id, user=request.user)`
- `get_object_or_404(PlannerEvent, pk=event_id, user=request.user, is_deleted=False)`

This prevents IDOR-style access where one user can target another user's record simply by guessing a numeric primary key. For admin policy exceptions, the application still uses explicit authorization checks rather than allowing unrestricted access.

## CSRF

CSRF protection is deliberately kept enabled and is not disabled casually. The app relies on Django's middleware and the standard cookie/session pattern to protect state-changing requests.

Protection includes:
- `django.middleware.csrf.CsrfViewMiddleware`
- cookie and session hardening configuration
- POST-only state-changing actions such as logout, task updates, and note deletion

This matches Django's documented recommendation that CSRF should remain enabled unless there is a compelling reason to disable it for a narrowly justified deployment scenario.

## Input validation

User-controlled input is validated through Django forms and model validators before it reaches persistence.

Examples:
- registration enforces password validation and duplicate username/email checks
- task and note forms validate content and required fields
- exam and goal values enforce allowed bounds and positive constraints
- attachment upload checks file size and MIME type before saving

The project also uses transaction boundaries for import flows, so invalid bulk data is rejected without partially importing records.

## Session security

Session handling is hardened for secure deployment while remaining practical for local development.

Current settings include:
- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = 'Lax'`
- `CSRF_COOKIE_HTTPONLY = True`
- `CSRF_COOKIE_SAMESITE = 'Lax'`
- secure cookies switch on in production deployments via environment configuration

The project keeps secure cookie settings production-aware and does not assume HTTPS in local development, which avoids breaking local debugging while still supporting a secure production deployment when the environment is configured correctly.

## Testing strategy

Security behavior is validated with focused Django tests and the standard test runner.

Current coverage includes:
- unauthenticated access is redirected or denied
- role restrictions prevent teacher/student workflow leakage
- object ownership blocks cross-user access
- CSRF rejects unsafe POST requests without valid tokens
- invalid form data is rejected without side effects
- logout clears the authenticated session

The team also runs the full suite and the shuffled suite to catch ordering-sensitive assumptions:

- `python manage.py test`
- `python manage.py test --shuffle`

## Threat mitigation map

| Threat | Mitigation |
| --- | --- |
| Unauthorized access | RBAC and permission checks |
| IDOR | Ownership-aware model queries |
| CSRF | Django CSRF middleware and secure cookie configuration |
| Invalid input | Django forms, validators, and model constraints |
| Session abuse | HttpOnly + SameSite + secure session configuration |

## Remaining deployment assumptions

Some security controls remain environment-dependent and should be configured by the deployment operator:
- HTTPS redirect and HSTS in production
- ALLOWED_HOSTS and SECRET_KEY for production deployments
- secure media storage and email delivery configuration
- managed scheduling for background maintenance commands

The application makes these assumptions explicit so the production environment can be hardened without weakening the local development workflow.
