# Task Spec: localos-compiled-ai-envelope-20260613

## Metadata
- Task ID: localos-compiled-ai-envelope-20260613
- Created: 2026-06-13T09:15:04+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- agents/autonomous_development_brief.md
- docs/LOCALOS_COMPILED_AI_ENVELOPE_OVER_OPENCLAW_V1.md
- docs/LOCALOS_AGENT_ARCHITECTURE_V1.md

## Original task statement
Сделать LocalOS product/policy envelope поверх OpenClaw: пользователь описывает агента обычным языком, система уточняет детали, понимает нужные сервисы, компилирует workflow в проверяемый executable plan, показывает подключения/стоимость/риски, требует approval и запускает safe preview перед активацией в рамках лимитов подписки.

## Current phase scope
Phase 2 of the remaining implementation: service/capability intelligence for the builder loop.

The builder must explicitly distinguish provider states before the user creates or activates an agent:
- already connected;
- can be connected through an allowed provider route;
- impossible or forbidden by LocalOS policy;
- multiple existing routes/connections require user choice.

This phase builds on Phase 1, where connector facts from the dialog became draft-safe and preflight-blocked until a real route/access is selected.

## Acceptance criteria
- AC1: Builder preview exposes a normalized `service_intelligence` artifact from existing feasibility/provider registry data.
- AC2: Google Sheets -> Telegram with one connected Telegram and no Google Sheets access reports Telegram as `already_connected` and Google Sheets as `connectable`.
- AC3: Multiple existing Telegram connections report `multiple_routes` and require explicit choice.
- AC4: Forbidden/impossible requests, for example unsafe Roscosmos computer access, report `impossible` and block draft creation.
- AC5: The UI shows a compact "Что возможно" panel using the normalized states before detailed connector/preflight panels.
- AC6: Agent-related tests and frontend production build pass.

## Constraints
- Do not introduce a second OpenClaw runtime or duplicate connector system.
- Do not allow external side effects from builder/compiler prompt text.
- Do not treat a sheet URL or Telegram target as credentials.
- Do not change production schema in this phase.
- Preserve existing dirty documentation changes from the Supergoal-inspired rules update.

## Non-goals
- Full LLM/OpenClaw live planner execution.
- Composio OAuth implementation.
- Real Google Sheets or Telegram network execution.
- Production deploy, unless explicitly requested after this phase.

## Verification plan
- Focused service intelligence tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'service_intelligence or required_connectors or forbidden' -x`
- Unit/integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- Frontend build: `npm --prefix frontend run build`
