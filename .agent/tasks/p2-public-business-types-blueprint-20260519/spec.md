# Task Spec: p2-public-business-types-blueprint-20260519

## Metadata
- Task ID: p2-public-business-types-blueprint-20260519
- Created: 2026-05-19T06:32:11+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Autonomous cleanup and P2 main.py decomposition: verify generated artifact hygiene, keep committed proof bundles as evidence, extract public /api/business-types route from main.py into a blueprint without changing URL or response behavior, and extend focused lint/tests plus live smoke.

## Acceptance criteria
- AC1: Generated artifact hygiene is checked; ignored cache artifacts are removed and committed `.agent/tasks` bundles remain the evidence strategy.
- AC2: `/api/business-types` is moved from `src/main.py` to a dedicated blueprint without changing URL, auth requirement, or response shape.
- AC3: Focused lint and route ownership tests guard the new blueprint and prevent route ownership regression back to `main.py`.
- AC4: Local checks and live route/runtime smoke pass after deployment.

## Constraints
- Preserve existing behavior for `/api/business-types`, including Bearer auth and `{"types": ...}` response.
- Do not modify production data.
- Keep decomposition small and scoped.

## Non-goals
- Do not change admin business-type behavior.
- Do not globally ignore `.agent/tasks`.
- Do not broaden lint to the whole project.

## Verification plan
- Build: py_compile focused modules.
- Unit tests: focused pytest route/security/query baseline.
- Integration tests: import `main.app`, assert public business-types ownership and absence of stale main endpoint.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: server backup, partial sync, restart `app worker`, live route ownership, runtime smoke.
