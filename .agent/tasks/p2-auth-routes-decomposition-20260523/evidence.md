# Evidence Bundle: p2-auth-routes-decomposition-20260523

## Summary
- Overall status: PASS
- Last updated: 2026-05-23T20:15:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/api/auth_user_api.py` with dedicated blueprint routes for `/api/auth/me`, `/api/auth/logout`, and `/api/users/profile`.
  - Removed the matching inline `@app.route(...)` handlers from `src/main.py`.
  - `tests/test_auth_user_routes.py` confirms ownership maps to `auth_user_api.*`.
- Gaps:
  - `/api/users/change-password` was not moved because no backend route currently exists.

### AC2
- Status: PASS
- Proof:
  - The extracted handlers preserve the same URL paths, HTTP methods, Russian error messages, auth token handling, and response payload shapes.
  - `src/main.py` only imports/registers the new blueprint.
- Gaps:
  - Live unauthenticated smoke will be run after deploy.

### AC3
- Status: PASS
- Proof:
  - `scripts/lint_backend_baseline.sh` now compiles/imports `auth_user_api`, checks route ownership, and fails if auth/user route markers return to `main.py`.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `raw/build.txt`: Python compile passed.
  - `raw/test-unit.txt`: `2 passed`.
  - `raw/test-integration.txt`: `5 passed`.
  - `raw/lint.txt`: backend lint baseline passed.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/main.py src/api/auth_user_api.py tests/test_auth_user_routes.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_auth_user_routes.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_security_runtime_config.py tests/test_auth_user_routes.py`
- `scripts/lint_backend_baseline.sh`
- `git diff --check`

## Raw artifacts
- .agent/tasks/p2-auth-routes-decomposition-20260523/raw/build.txt
- .agent/tasks/p2-auth-routes-decomposition-20260523/raw/test-unit.txt
- .agent/tasks/p2-auth-routes-decomposition-20260523/raw/test-integration.txt
- .agent/tasks/p2-auth-routes-decomposition-20260523/raw/lint.txt
- .agent/tasks/p2-auth-routes-decomposition-20260523/raw/screenshot-1.png

## Known gaps
- Password-change route remains a product/API gap; it was not introduced in this behavior-preserving decomposition.
