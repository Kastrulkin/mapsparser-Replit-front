# Task Spec: agents-reviews-agent-phase8-20260527

## Metadata
- Task ID: agents-reviews-agent-phase8-20260527
- Created: 2026-05-27T08:45:24+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Phase 8 Rima-like agents: make reviews agent useful end-to-end with LLM/fallback reply drafts, review reasons, provenance, approval boundary, no publish

## Acceptance criteria
- AC1: Reviews agent creates useful reply drafts from review text/internal sources.
- AC2: Result includes manual review reasons, checklist, provenance, and LLM/fallback metadata.
- AC3: Reviews agent performs no publish/send/dispatch capability and stops at final approval.
- AC4: Run review journal exposes human labels for reply drafts, manual review reasons, and publication state.
- AC5: Local checks, production deploy, and targeted production API smoke pass.

## Constraints
- Runtime DB remains PostgreSQL.
- No schema migration for this phase.
- No external publish, send, provider write, dispatcher start, or destructive side effect.
- Risky external actions remain outside generic reviews agent scope.

## Non-goals
- Publishing review replies.
- Editing third-party review providers.
- Building the full UI flow for review publication.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: `scripts/smoke_agent_blueprint_reviews_api.py` inside production app container
- Lint: `scripts/lint_backend_baseline.sh`
- Manual checks: server `docker compose ps`, app logs, `curl -I http://localhost:8000`
