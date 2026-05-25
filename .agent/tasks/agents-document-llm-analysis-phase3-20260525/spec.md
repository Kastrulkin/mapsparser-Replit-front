# Task Spec: agents-document-llm-analysis-phase3-20260525

## Metadata
- Task ID: agents-document-llm-analysis-phase3-20260525
- Created: 2026-05-25T19:03:28+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- agents/autonomous_development_brief.md

## Original task statement
Phase 3 Rima-like document agent LLM analysis: read Datahub-lite extracted text, summarize, extract risks/fields/facts, respect rules, no external dispatch, save provenance/result artifact.

## Acceptance criteria
- AC1: Document runner reads extracted Datahub-lite source text for document agents.
- AC2: Document analysis uses an LLM path to produce summary, risks, facts, fields, next questions, and rules applied.
- AC3: Agent setup rules and recent feedback are included in the LLM prompt.
- AC4: Provider failure falls back to deterministic analysis instead of breaking the run.
- AC5: Output artifact records provenance, analysis source, LLM usage flag, prompt version, and no external dispatch.
- AC6: Existing approval/final-result flow and feedback version loop still work.
- AC7: Backend guardrails, targeted unit tests, deploy, and server smoke pass.

## Constraints
- No external send/publish/dispatcher action from generic document agents.
- No schema migration for this phase.
- Existing AgentBlueprint API contracts remain compatible.
- Production data may only be touched through self-cleaning smoke fixtures.

## Non-goals
- Full Rima-style Datahub product.
- Email/table/review agent LLM flows.
- Browser UI redesign.
- Replacing GigaChat SSL workaround policy.

## Verification plan
- Build: no frontend build required; backend-only change.
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: `python /app/scripts/smoke_agent_blueprint_document_api.py` inside production `app` container.
- Lint: `scripts/lint_backend_baseline.sh`
- Deploy: `scripts/deploy_backend_src.sh`
