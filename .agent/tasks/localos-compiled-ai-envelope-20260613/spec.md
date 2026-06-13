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
Phase 1 of the remaining implementation: make the builder loop draft-first for connector work.

When LocalOS understands the agent workflow but required external services are not connected yet, the user must be able to create a draft compiled agent. The draft must preserve resource facts from the dialog, then block preview/activation at preflight until a provider route, saved integration, or allowed fallback is selected.

## Acceptance criteria
- AC1: A Google Sheets -> Telegram request with a concrete sheet URL and Telegram target can create a draft even when no saved integrations exist.
- AC2: The compiler/builder persists dialog resource facts into blueprint metadata and version required bindings, not only preview text.
- AC3: Preflight does not treat dialog resource facts as credentials or a live external connection; it returns a blocked state with a clear provider-route/access reason.
- AC4: Provider route selection is optional before draft creation. If a route is selected, it must still be explicitly accepted before being sent to the API.
- AC5: Existing safety gates remain: activation still requires preflight/preview/approval, and connection choice among multiple existing integrations is still explicit.
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
- Unit/integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- Billing tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_builder_billing.py -x`
- Frontend build: `npm --prefix frontend run build`
