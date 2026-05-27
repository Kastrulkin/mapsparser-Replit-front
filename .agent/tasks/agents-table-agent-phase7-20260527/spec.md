# Task Spec: agents-table-agent-phase7-20260527

## Metadata
- Task ID: agents-table-agent-phase7-20260527
- Created: 2026-05-27T08:33:40+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Phase 7 Rima-like agents: make table agent useful end-to-end with LLM/fallback analysis, exceptions, rows_to_review, provenance, approval boundary, no external dispatch

## Acceptance criteria
- AC1: Table blueprint category creates a useful analysis result, not a static placeholder.
- AC2: Table result includes summary, exceptions, rows_to_review, recommendations, provenance, and LLM/fallback metadata.
- AC3: Table agent has no external send/publish/import side effects and stops at final approval.
- AC4: Run review journal exposes table-specific human details.
- AC5: Local tests, lint, build, production deploy, and production table smoke pass.

## Constraints
- No database schema changes.
- No direct external provider send/publish/import/dispatcher calls from generic table agents.
- Keep risky external actions behind existing approval/orchestrator boundaries.
- Do not change document/email/outreach behavior.

## Non-goals
- Spreadsheet editing/export.
- Automatic import into CRM/outreach.
- New reviews/outreach agent implementation in this phase.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: `scripts/smoke_agent_blueprint_table_api.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: production deploy health and app logs
