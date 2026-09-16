# Migration and release runbook

The live SQLite database and migrations `0001`–`0004` are preserved. New schema changes are forward-only (`0005` onward). The current release includes `0005`–`0016`; `0016` adds persisted announcements and replaces the legacy daily attendance uniqueness rule with scoped general/subject-day constraints.

## Before applying to a deployment

1. Stop writes or use an approved maintenance window.
2. Copy `db.sqlite3`, any `-wal`/`-shm` sidecars, `media/`, and application logs to protected backup storage.
3. Hash the backup and record row counts, primary-key ranges, ownership counts, and every `Note.file` path.
4. Run `manage.py check`, `manage.py check --deploy`, `makemigrations --check --dry-run`, and the complete test suite.
5. Restore the backup to a disposable clone and run `manage.py migrate --noinput` there.
6. Run SQLite `PRAGMA integrity_check` and `PRAGMA foreign_key_check`; compare IDs, counts, ownership, and file paths with the pre-migration census.
7. Run authenticated smoke checks for `/dashboard/`, `/planner/adaptive/`, `/subjects/`, `/study-sessions/`, `/notifications/`, and the administrator panel. Confirm that each response is rendered from the migrated clone before touching the approved database.

## Apply

Only after the clone rehearsal and backup review:

```text
DJANGO_DB_NAME=/path/to/approved/database.sqlite3 venv/bin/python manage.py migrate --noinput
```

The project does not switch databases automatically and does not delete or flush the live database. Migration `0005` backfills `Task.updated_at` from `created_at`; this is a compatibility value, not a claim about historical edit time. Migration `0006` seeds explicit roles and provisions existing users. Migration `0007` creates the normalized academic tables without rewriting legacy rows.

## Rollback posture

Do not reverse migrations blindly on a live database. Stop the release, preserve the database and logs, and restore the verified backup only through the project's approved data-recovery process. Investigate forward fixes where possible. Uploaded files are not deleted by schema migrations.
