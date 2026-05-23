# Task Spec: p2-auth-routes-decomposition-20260523

## Metadata
- Task ID: p2-auth-routes-decomposition-20260523
- Created: 2026-05-23T19:52:54+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P2 auth/user routes decomposition: extract /api/auth/me, /api/auth/logout, /api/users/profile, /api/users/change-password from main.py into blueprint; add route ownership guardrail; commit push deploy before next step

## Acceptance criteria
- AC1: `/api/auth/me`, `/api/auth/logout`, and `/api/users/profile` are owned by a dedicated auth/user blueprint, not inline `main.py` route handlers.
- AC2: Existing URL paths, methods, response shapes, and auth failure behavior remain unchanged.
- AC3: Backend lint baseline has a route ownership guardrail for the extracted auth/user routes.
- AC4: The current backend checks pass locally before commit/deploy.

## Constraints
- Do not add new runtime behavior for `/api/users/change-password`; no matching backend route exists yet.
- Keep the change behavior-preserving and scoped to route decomposition.
- Do not change production data.

## Non-goals
- Full auth-system redesign.
- Superadmin/business decomposition; this is the next autonomous step after commit/push/deploy.
- Password-change endpoint implementation.

## Verification plan
- Build: `python3 -m py_compile src/main.py src/api/auth_user_api.py tests/test_auth_user_routes.py`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_auth_user_routes.py`
- Integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_security_runtime_config.py tests/test_auth_user_routes.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: inspect `main.app.url_map` ownership through focused tests and lint baseline.
