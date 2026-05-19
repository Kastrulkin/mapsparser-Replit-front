# Task Spec: p2-admin-business-types-dedupe-20260519

## Metadata
- Task ID: p2-admin-business-types-dedupe-20260519
- Created: 2026-05-19T06:21:40+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Autonomous P2 main.py decomposition: dedupe admin business-types routes by preserving active admin_growth_api ownership for GET/POST/DELETE, moving the currently main.py-only PUT behavior into admin_growth_api, removing stale main.py duplicates, and extending focused lint/tests.

## Acceptance criteria
- AC1: Admin business-type GET/POST/DELETE routes remain owned by `api.admin_growth_api`.
- AC2: The previously `main.py`-only PUT `/api/admin/business-types/<type_id>` behavior is moved to `api.admin_growth_api`.
- AC3: Stale admin business-type route declarations are removed from `src/main.py`; public `/api/business-types` remains untouched.
- AC4: Focused lint/tests and live route/runtime smoke pass after deployment.

## Constraints
- Preserve route URLs and method coverage.
- Do not modify production data.
- Keep the pass focused on admin business-type route ownership.

## Non-goals
- Do not rewrite growth schema or admin growth-stage business logic.
- Do not change public `/api/business-types` behavior.

## Verification plan
- Build: py_compile focused modules.
- Unit tests: focused pytest route/security/query baseline.
- Integration tests: import `main.app`, assert admin business-type route ownership and no stale main endpoints.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: server backup, partial sync, restart `app worker`, live route ownership, runtime smoke.
