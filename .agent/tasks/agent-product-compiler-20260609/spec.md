# Task Spec: agent-product-compiler-20260609

## Metadata
- Task ID: agent-product-compiler-20260609
- Created: 2026-06-09T09:35:08+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этапы 2-3: единая продуктовая сущность Agent поверх AgentBlueprint + optional AIAgents persona; persona_agent_id реально используется; Agent Compiler превращает текст коммуникационного агента в blueprint communications с trigger, audience, data sources, steps, capabilities, approval policy, limits и output schema на основе existing agent_builder_session.py и agent_blueprint_draft_builder.py.

## Acceptance criteria
- AC1: Backend exposes a logical product Agent without a new physical table: blueprint plus optional persona.
- AC2: `persona_agent_id` in blueprint versions is used as the link to `AIAgents`, and old `AIAgents` are treated as voice/persona rather than a separate product agent.
- AC3: Agent Compiler v1 turns a communications reminder prompt into a typed `communications` blueprint payload with trigger, audience, data sources, steps, capabilities, approval policy, limits, and output schema.
- AC4: Existing builder/session endpoints remain backward compatible while using compiler semantics.
- AC5: UI can display the attached agent voice in the agents workspace.
- AC6: Architecture doc records the implemented backend contract and remaining follow-ups.

## Constraints
- No production data changes.
- No schema migration for this stage; product Agent layer is logical first.
- Do not delete `AIAgents`, Telegram/WhatsApp chat flows, or legacy settings.
- Communication is a blueprint category, not a separate entity.

## Non-goals
- Implementing actual communications sending capability in ActionOrchestrator.
- Migrating existing production `AIAgents` rows into blueprints.
- Removing legacy business-level `ai_agent_*` settings.
- Full deploy.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: API route import coverage in `test_agent_blueprint_layer.py`
- Lint: `git diff --check`
- Manual checks: inspect changed files and `git status --short --branch`
