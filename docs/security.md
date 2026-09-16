# Security controls and remaining assumptions

- State-changing operations use POST and CSRF protection; logout is POST-only.
- New object views filter by owner, assigned subject, or explicit Administrator policy. Cross-user media downloads return 404.
- Deleted notes are not served by the normal media endpoint.
- Registration and password change use Django password validators. Duplicate registration responses do not reveal account existence.
- Imports enforce a byte/row limit, UTF-8 decoding, row validation, and all-or-nothing database transactions.
- Production settings require an explicit secret and allowed hosts and expose environment controls for secure cookies, HTTPS redirects, and HSTS.
- NLTK does not download data during application import.
- Admin logs use nullable actors so deleting a user does not erase audit history; retention and IP/user-agent privacy policy remain deployment responsibilities.
- `python-magic` requires the host `libmagic` package. HTTPS termination, email delivery, scheduled management commands, and private media storage must be configured by deployment operators. Run `venv/bin/python manage.py generate_notifications` and `venv/bin/python manage.py evaluate_achievements` from a scheduler at the chosen cadence; these commands are idempotent but are not started by Django automatically. Serve uploaded files only through the authenticated note/task attachment views, not a public `/media/` route.

The Django admin's `is_staff` gate is separate from the custom Administrator role. Superusers retain a documented break-glass path in the policy module.
