# Task Spec: p2-superadmin-business-routes-decomposition-20260523

## Metadata
- Task ID: p2-superadmin-business-routes-decomposition-20260523
- Created: 2026-05-23T20:00:18+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P2 superadmin/business routes decomposition: extract /api/superadmin/businesses GET/POST/PUT/DELETE and related business credential/moderation endpoints from main.py into blueprint; add route ownership guardrail; commit push deploy before next step

## Acceptance criteria
- AC1: Superadmin business routes are owned by a dedicated `superadmin_business_api` blueprint, not inline `main.py` handlers.
- AC2: Existing route URLs, methods, auth checks, and response payloads remain compatible.
- AC3: Backend lint baseline has route ownership guardrails for the extracted superadmin business routes.
- AC4: Focused backend checks pass locally before commit/deploy.

## Constraints
- Do not change production data.
- Keep this decomposition scoped to business routes; leave superadmin user/proxy routes for later.
- Do not send emails during verification.

## Non-goals
- Superadmin user routes decomposition.
- Proxy/admin routes decomposition.
- Business model or database schema changes.

## Verification plan
- Build: `python3 -m py_compile src/main.py src/api/superadmin_business_api.py tests/test_superadmin_business_routes.py`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_superadmin_business_routes.py tests/test_auth_user_routes.py`
- Integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_security_runtime_config.py tests/test_superadmin_business_routes.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: live unauthenticated route smoke after deploy.
