# Task Spec: agents-outreach-journal-phase9-20260527

## Metadata
- Task ID: agents-outreach-journal-phase9-20260527
- Created: 2026-05-27T09:03:15+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Phase 9 Rima-like agents: make supervised outreach run review product-readable with sourcing, shortlist, drafts, queue state, approvals, and no dispatcher

## Acceptance criteria
- AC1: Outreach run review journal shows product stages for sourcing, shortlist, drafts, and queue.
- AC2: Journal details are human-readable and include source, counts, filters, channels, queue state, and external-send boundary.
- AC3: Existing supervised outreach path still uses prospectingleads, approval gates, drafts, queue, and no dispatcher.
- AC4: Local tests, lint baseline, frontend build, partial production deploy, and production smoke pass.

## Constraints
- Do not change database schema.
- Do not change external sending behavior.
- Do not deploy unrelated local `src/main.py` changes.
- Dispatcher remains a separate contour.

## Non-goals
- Starting dispatcher.
- Sending external messages.
- Rebuilding the whole outreach data model.
- UI redesign in this phase.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: production `scripts/smoke_agent_blueprint_outreach_api.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: server `docker compose ps`, app logs, `curl -I http://localhost:8000`
