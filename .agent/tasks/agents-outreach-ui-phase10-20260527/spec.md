# Task Spec: agents-outreach-ui-phase10-20260527

## Metadata
- Task ID: agents-outreach-ui-phase10-20260527
- Created: 2026-05-27T10:25:44+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Phase 10 Rima-like agents: make /dashboard/agents show supervised outreach run stages as a product-readable progress overview using sourcing, shortlist, drafts, queue journal data

## Acceptance criteria
- AC1: `/dashboard/agents` shows a supervised outreach progress overview in saved results.
- AC2: The overview uses existing journal/review data and does not expose raw JSON or IDs as primary UI.
- AC3: Frontend build, backend baseline lint, and Agent Blueprint tests pass.
- AC4: Production frontend is deployed and an authenticated smoke verifies the outreach results view.
- AC5: Production smoke fixture is removed after verification.

## Constraints
- Do not change backend contracts or runtime side-effect boundaries.
- Do not start the outreach dispatcher.
- Keep external send state visibly queued/not dispatched.

## Non-goals
- No new database schema.
- No new outreach pipeline behavior.
- No generic redesign outside the outreach run visibility polish.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: production smoke fixture via `scripts/smoke_agent_blueprint_outreach_api.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: authenticated browser smoke on `https://localos.pro/dashboard/agents`
