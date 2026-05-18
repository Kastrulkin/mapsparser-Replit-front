# Task Spec: p2-growth-blueprint-20260518

## Metadata
- Task ID: p2-growth-blueprint-20260518
- Created: 2026-05-18T19:48:58+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Autonomous P2 main.py decomposition: extract growth/wizard/sprint routes from main.py into a blueprint without changing URLs/responses, and extend backend lint baseline for route ownership, imports, and runtime SQL placeholder guardrails.

## Acceptance criteria
- AC1: Growth workflow runtime routes are extracted from `src/main.py` into a Flask blueprint without changing URL rules or endpoint behavior.
- AC2: Duplicate-priority-sensitive `business/stages` and `admin/growth-stages` routes are not moved in this iteration.
- AC3: Backend lint baseline has focused guardrails for the new blueprint: import smoke, route ownership, no route declarations in `main.py`, and no SQLite `?` placeholders in runtime SQL.
- AC4: Local focused tests and live route/runtime smoke pass after deployment.

## Constraints
- Keep URLs and JSON response shapes unchanged for moved routes.
- Do not change production data manually.
- Keep SQLite legacy-only; runtime SQL must use PostgreSQL `%s` placeholders.
- Avoid broad full-project lint cleanup.

## Non-goals
- Do not refactor admin growth stage duplication in this pass.
- Do not change sprint/wizard business logic or schema behavior.

## Verification plan
- Build: `python3 -m py_compile src/main.py src/api/growth_workflow_api.py tests/test_growth_workflow_routes.py`
- Unit tests: focused pytest for growth/report/security/query adapter checks.
- Integration tests: import `main.app` and assert route ownership.
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: server backup, partial sync, restart `app worker`, live route ownership, runtime smoke.
