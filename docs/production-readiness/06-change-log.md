# Production-readiness change log

## SEC-AUTH-01 — Inactive session revocation

Status: **FIX_PROVEN locally**, independent review passed. Not deployed in this audit.

- Central `verify_session` rejects inactive users by default before a protected route can mutate state.
- `/api/auth/me` uses a narrow diagnostic opt-in and retains `403 account_blocked`; normal guards retain their 401 denial. Login's blocked-account contract is preserved.
- Normalize boolean/legacy `False`, `0`, `"0"` once for both guard and returned payload. Independent review caught a first-patch inconsistency for text `"0"`; a real `/auth/me` regression test reproduced it before correction.
- No schema, password, session row or production data mutation. Active-session behavior stays covered.

Evidence:

- Initial red builder reproduction: 2 failed / 12 passed, inactive bearer could execute a protected mutation.
- Review regression red: 1 failed / 2 passed (`legacy_inactive_values`), then 3 passed after normalization. JSON evidence in task `raw/sec-auth-01-legacy-zero-{red,green}.json`.
- Root rerun: `venv/bin/python -m pytest -q tests/test_auth_email_case_insensitive.py tests/test_auth_user_routes.py tests/test_browser_session_security.py tests/test_network_member_access.py` → **42 passed in 5.21 s** (7.391 s captured command wall time).
- Independent reviewer: three principal files, **40 passed**, previous finding closed, no additional blocker in the scoped package.
- Focused Ruff F821 and `git diff --check` pass.

Limits: full backend/PostgreSQL suite and deployed behavior not yet verified. This fix does not close the separate role/tenant audit. Source rollback is possible but would reopen revoked-session access and therefore is not a recommended security mitigation.
