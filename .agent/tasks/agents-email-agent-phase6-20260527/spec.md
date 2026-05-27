# Task Spec: agents-email-agent-phase6-20260527

## Metadata
- Task ID: agents-email-agent-phase6-20260527
- Created: 2026-05-27T08:06:54+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Phase 6 Rima-like agents: make email agent useful end-to-end with LLM/fallback draft, provenance, approval boundary, no external dispatch

## Acceptance criteria
- AC1: Email blueprint category creates a real draft result, not a static placeholder.
- AC2: Email draft includes subject, body, checklist, missing information, provenance, and LLM/fallback metadata.
- AC3: Email agent has no external send/publish side effects and stops at final approval.
- AC4: Run review journal exposes email-specific human details while keeping technical payload collapsible.
- AC5: Local tests, lint, build, production deploy, and production email smoke pass.

## Constraints
- No database schema changes.
- No direct provider send/publish/dispatcher calls from generic email agents.
- Keep all risky external actions behind existing approval/orchestrator boundaries.
- Do not change document/outreach behavior.

## Non-goals
- Email sending.
- Inbox connection or SMTP/provider integration.
- Full UI redesign for email-specific settings.
- New table/review/outreach agent implementation in this phase.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: `scripts/smoke_agent_blueprint_email_api.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: production deploy health and app logs
