# Task Spec: agents-run-detail-human-journal-phase5-20260527

## Metadata
- Task ID: agents-run-detail-human-journal-phase5-20260527
- Created: 2026-05-27T07:48:29+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Phase 5 Rima-like agent run detail: make run detail a readable journal with inputs, extraction, rules, result, approvals, and technical journal collapsed

## Acceptance criteria
- AC1: Backend review endpoint returns a human-readable `journal` for the latest run.
- AC2: Journal entries cover inputs, extraction/processing, result, and approvals.
- AC3: UI shows "Журнал запуска" by default and keeps IDs/full payloads under "Технический журнал".
- AC4: Document-agent smoke validates the new journal contract and keeps external dispatch disabled.
- AC5: Local checks, production deploy, and live sanity checks pass.

## Constraints
- Do not change existing AgentBlueprint API behavior outside additive review/journal fields.
- Do not introduce schema changes in this phase.
- Keep generic document agents safe: no external send/publish/dispatcher side effects.
- Do not touch unrelated dirty/untracked work.

## Non-goals
- New agent types beyond the existing document path.
- Full authenticated browser smoke under a real production user.
- Visual redesign of the Agents dashboard.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: `scripts/smoke_agent_blueprint_document_api.py` locally/production
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: deploy verification, live `/dashboard/agents` browser route sanity
