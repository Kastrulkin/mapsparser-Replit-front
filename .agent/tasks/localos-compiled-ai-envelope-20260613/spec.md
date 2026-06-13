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
Phase 4 of the remaining implementation: OpenClaw preview execution artifact.

Selected OpenClaw route contracts must participate in safe preview runtime, not remain metadata-only. Preview run must expose an observation artifact that proves:
- LocalOS recognized selected OpenClaw action handlers;
- the action plan is dry-run / preview-only;
- no external side effects were performed;
- activation observability can show the OpenClaw boundary result.

## Acceptance criteria
- AC1: Preview input includes `connector_action_handlers` and `openclaw_preview_routes` derived from selected route contracts.
- AC2: OpenClaw preview routes are merged into `openclaw_action_plan` even when version steps do not yet carry provider action refs.
- AC3: Safe preview run creates an `openclaw_preview_observations` artifact from selected OpenClaw route contracts.
- AC4: The observation artifact explicitly records `external_actions_executed: false` and preview side effects disabled.
- AC5: Runner does not call the orchestrator for this dry-run route observation; it remains a LocalOS preview artifact.
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
- Focused OpenClaw preview tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'preview_run_input_is_safe or openclaw_preview_observations or preview_run_and_activation' -x`
- Unit/integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- Frontend build: `npm --prefix frontend run build`
