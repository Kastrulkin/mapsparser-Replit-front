# Task Spec: p2-growth-route-dedupe-20260518

## Metadata
- Task ID: p2-growth-route-dedupe-20260518
- Created: 2026-05-18T20:01:53+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Autonomous P2 main.py decomposition: remove duplicate growth stages and admin growth-stages route handlers from main.py while preserving active blueprint route ownership; extend backend lint baseline and tests to guard against duplicate route ownership.

## Acceptance criteria
- AC1: Duplicate growth stage handlers are removed from `src/main.py`.
- AC2: Active route ownership remains unchanged: business stages stay on `api.growth_api`, admin growth-stages stay on `api.admin_growth_api`.
- AC3: Backend lint baseline and focused tests guard against stale `main.py` duplicate endpoints.
- AC4: Local checks and live route/runtime smoke pass after deployment.

## Constraints
- Do not change URLs or response behavior.
- Do not touch production data.
- Avoid broad refactors outside route ownership cleanup.

## Non-goals
- Do not rewrite `api.growth_api` or `api.admin_growth_api` business logic.
- Do not address unrelated duplicate admin business-type routes in this pass.

## Verification plan
- Build: py_compile focused files.
- Unit tests: focused pytest route/security/query baseline.
- Integration tests: import `main.app`, assert active route ownership and no stale main endpoints.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: server backup, partial sync, restart `app worker`, live route ownership, runtime smoke.
