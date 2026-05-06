# Task Spec: content-plan-network-readiness-ux

## Metadata
- Task ID: content-plan-network-readiness-ux
- Created: 2026-05-04T06:07:55+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Polish content plan readiness UX for network parent contexts with maps and SEO but missing services

## Acceptance criteria
- AC1: Network parent content-plan readiness treats "maps + SEO present, services missing" as a usable search-plan foundation instead of a generic incomplete-data warning.
- AC2: Copy distinguishes network menu/products/services from single-business services and gives the user a clear next action.
- AC3: Frontend build and content-plan tests pass.
- AC4: Frontend-only production rollout is verified against live assets.

## Constraints
- Frontend-only change.
- No DB schema changes.
- Do not mutate production business data during verification.

## Non-goals
- Do not change backend readiness semantics or content generation.
- Do not populate missing services for Lukoil.

## Verification plan
- Build: `cd frontend && npm run build`.
- Unit tests: `source venv/bin/activate && python3 -m pytest -q tests/test_content_plan_generation.py tests/test_content_plan_policy.py`.
- Integration tests: not required for frontend-only copy/state polish.
- Lint: `git diff --check`.
- Manual checks: deploy frontend dist and verify live JS chunk contains new network readiness copy.
