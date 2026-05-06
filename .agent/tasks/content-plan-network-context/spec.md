# Task Spec: content-plan-network-context

## Metadata
- Task ID: content-plan-network-context
- Created: 2026-05-03T20:13:48+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Fix content plan network parent context aggregation so parent network shows map links, services, SEO and usable network operating data

## Acceptance criteria
- AC1: For a network parent scope, content-plan context aggregates child locations plus the parent record instead of reading only the parent business id.
- AC2: Lukoil network parent context returns real map links and SEO keywords; map links must be greater than 0 and SEO keywords must be fuel/AZS-focused.
- AC3: Existing content-plan generation and policy tests pass.

## Constraints
- Backend-only fix; no DB schema changes.
- Do not mutate production business data during verification.

## Non-goals
- Filling missing services for Lukoil; current production data has no user services for the network.

## Verification plan
- Build: not required for backend-only Python service change.
- Unit tests: `python3 -m pytest -q tests/test_content_plan_generation.py tests/test_content_plan_policy.py`.
- Integration tests: live read-only API check for `/api/content-plans/context` on Lukoil network parent.
- Lint: `git diff --check`.
- Manual checks: verify production `/` returns HTTP 200 after restarting `app` and `worker`.
