# Task Spec: agents-dialog-builder-phase1-20260525

## Metadata
- Task ID: agents-dialog-builder-phase1-20260525
- Created: 2026-05-25T12:06:10+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Phase 1 Rima-like dialog agent creation: AgentBuilderSession API, conversational UI preview, create document agent from one description with clarifying questions when needed

## Acceptance criteria
- AC1: AgentBuilderSession backend persists dialog sessions and exposes:
  - POST /api/agent-builder/sessions
  - POST /api/agent-builder/sessions/<id>/message
  - POST /api/agent-builder/sessions/<id>/create-blueprint
- AC2: User can create a document agent from one free-text description.
- AC3: If data/rules are incomplete, builder returns clarifying questions.
- AC4: UI shows a conversational builder with human preview before creation.
- AC5: Existing Agent Blueprints/manual wizard/runtime behavior remains compatible.

## Constraints
- Use Docker/Postgres runtime assumptions.
- Do not bypass existing Agent Blueprint creation boundaries.
- Do not perform external send/publish actions.
- Production schema change requires DB backup before deploy.

## Non-goals
- Full LLM-based autonomous planning.
- Full Rima-grade Datahub.
- Email/table/reviews generic agents.
- External dispatch from generic agents.

## Verification plan
- Build: frontend production build.
- Unit tests: targeted Agent Blueprint layer tests.
- Integration tests: API smoke for dialog builder session -> message -> create-blueprint.
- Lint: backend baseline guardrails.
- Manual checks: authenticated production UI smoke for modal dialog, preview, questions, create from preview.
