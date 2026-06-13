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
Phase 3 of the remaining implementation: real connector UX/action handler contract.

The builder must turn "можно подключить" into a concrete user action and persisted route contract:
- OpenClaw can be selected as a policy/execution boundary without user credentials;
- Maton can be selected only when a saved Maton key is bound;
- manual fallback remains draft-only/human-operated;
- selected routes produce typed action handler metadata that preflight/runtime can inspect.

## Acceptance criteria
- AC1: Selected provider routes are persisted as `agent_binding_provider_routes` and mirrored into `agent_binding_integrations`.
- AC2: Selected routes create `connector_action_handlers` with handler, credential source, preflight resolution, approval/audit and preview side-effect policy.
- AC3: OpenClaw route can be selected without external user credentials and remains inside LocalOS policy envelope.
- AC4: Maton route requires a saved `externalbusinessaccounts:maton` key; if exactly one is available, builder auto-binds it, otherwise API returns a route access error.
- AC5: The builder "Что возможно" panel can choose the recommended route directly, so intelligence becomes an action surface.
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
- Focused connector route tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'provider_routes or maton_route or action_handler or service_intelligence' -x`
- Unit/integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- Frontend build: `npm --prefix frontend run build`
