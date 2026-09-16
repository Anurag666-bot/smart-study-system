# Role-based access control

Application roles are explicit rows in `Role` and `UserRole`; Django's `is_staff` flag remains a technical gate for Django Admin and is not treated as a business role.

| Capability | Student | Teacher | Administrator |
|---|---:|---:|---:|
| Own notes, tasks, plans, sessions, goals | Yes | Yes | Yes |
| View own notifications, exams, results | Yes | Yes | Yes |
| View assigned subjects and enrolled progress | No | Yes | Yes |
| View enrolled students and class reports | No | Yes | Yes |
| Create exams for assigned subjects | No | Yes | Yes |
| Enter results for enrolled students | No | Yes | Yes |
| Record attendance for an assigned subject | No | Yes | Yes |
| Manage global subjects and settings | No | No | Yes |
| Use custom administration panel | No | No | Yes |
| Read global activity/audit data | No | No | Yes |

Authorization is enforced by `studyapp.policies` and owner/subject-scoped querysets. Navigation only improves discoverability; it is never the security boundary. Anonymous and inactive users fail closed. Existing users are provisioned as Student unless they were already staff/superusers, which are bootstrapped as Administrator; no existing account is guessed to be a Teacher.

Administrators can assign explicit roles through the custom user-management page. Role assignments, announcement changes, and system-setting changes are recorded in the append-only `AdminLog` model and shown through the read-only audit page. Announcements are authored by Administrators and published to student dashboards; settings accept JSON values and are never used as an authorization shortcut.
