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
Phase 6 of the remaining implementation: Google Sheets read / LocalOS finance handler wiring.

The project already had native capability handlers for:
- `google_sheets.read_rows`;
- `finance.transaction.create`.

This phase closes the runtime wiring gap: a plain `AgentBlueprintRunner` must default to the real capability map, so compiled workflows can execute reads and finance request creation through the same LocalOS ActionOrchestrator/policy/ledger boundary used by API and trigger runtime.

## Acceptance criteria
- AC1: Default `AgentBlueprintRunner()` uses `ActionOrchestrator(build_capability_handlers())`, not an empty orchestrator.
- AC2: Default runner exposes `google_sheets.read_rows` handler.
- AC3: Default runner exposes `finance.transaction.create` handler.
- AC4: Existing Google Sheets read handler still supports native provider read and inline rows without provider write.
- AC5: Existing finance handler still creates finance transaction requests/proposals without direct LocalOS write.
- AC6: Agent-related tests and frontend production build pass.

## Constraints
- Do not bypass ActionOrchestrator policy, ledger, billing, or approval checks.
- Do not introduce schema changes.
- Do not perform production data writes.
- Finance capability may create proposals/request payloads; actual finance apply remains behind approval/apply executor.

## Non-goals
- New Google OAuth UX.
- New finance import schema.
- Bulk finance auto-apply.
- Provider-specific Google Sheets read UI polish.

## Verification plan
- Focused handler wiring tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'default_runner_is_wired or google_sheets_read_rows_capability_uses_native_provider or finance_transaction_create_capability_normalizes_rows_without_localos_write or maton_delivery' -x`
- Unit/integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- Frontend build: `npm --prefix frontend run build`
