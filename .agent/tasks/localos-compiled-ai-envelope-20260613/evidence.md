# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T17:10:47+03:00
- Current phase: Phase 10, OpenClaw planner loop + production action runtime contracts.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Builder preview now treats Google Sheets, Telegram, and Maton as route-required providers.
  - `tests/test_agent_blueprint_layer.py::test_agent_builder_session_preview_includes_feasibility_for_required_connectors`

### AC2
- Status: PASS
- Proof:
  - Google Sheets -> Telegram creation requires two provider route bindings and blocks create/preview flow until routes are selected and confirmed.
  - `tests/test_agent_blueprint_layer.py::test_agent_builder_api_requires_selected_provider_routes_for_required_bindings`
  - `tests/test_agent_blueprint_layer.py::test_compiled_agent_creation_contract_google_sheets_to_telegram`

### AC3
- Status: PASS
- Proof:
  - Preflight merges selected resource/credential config with `agent_binding_provider_routes`; without route it reports `provider_route_required`, with route it becomes ready.
  - `tests/test_agent_blueprint_layer.py::test_compiled_agent_creation_contract_google_sheets_to_telegram`
  - `tests/test_agent_blueprint_layer.py::test_agent_preflight_accepts_openclaw_provider_route_for_binding`

### AC4
- Status: PASS
- Proof:
  - Activation gate and post-create handoff now return `choose_provider_route` for route blockers instead of generic connection steps.
  - `tests/test_agent_blueprint_layer.py::test_compiled_agent_creation_contract_google_sheets_to_telegram`
  - `tests/test_agent_blueprint_layer.py::test_agent_preview_run_and_activation_endpoints_enforce_safe_gate`

### AC5
- Status: PASS
- Proof:
  - `/dashboard/agents` builder no longer auto-selects recommended routes; user must explicitly choose and confirm provider routes before draft creation.
  - Frontend production build passed.

### AC6
- Status: PASS
- Proof:
  - Full agent blueprint suite passed: 155 tests.
  - Production action output now includes `localos_production_action_contract_v1` with preflight, approval policy, ledger, limits, recovery, and side-effect flags.
  - No schema migration was added.
  - `git diff --check` passed.

### AC7
- Status: PASS
- Proof:
  - OpenClaw planner loop now emits blocking `openclaw_workflow_detail_missing` questions for missing Google Sheets target, Telegram target, schedule/trigger, and post format.
  - Builder setup flow refuses to create draft when these workflow details are missing.
  - `tests/test_agent_blueprint_layer.py::test_openclaw_planner_loop_requires_workflow_details_before_draft`
  - `tests/test_agent_blueprint_layer.py::test_agent_builder_blocks_empty_google_sheets_to_telegram_workflow`

### AC8
- Status: PASS
- Proof:
  - Maton delivery preview and finance transaction request steps expose the production action runtime contract.
  - `tests/test_agent_blueprint_layer.py::test_runner_creates_maton_delivery_preview_draft_without_dispatch`
  - `tests/test_agent_blueprint_layer.py::test_runner_passes_compiled_step_rows_to_next_capability_without_runtime_ai`

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- `git diff --check`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase9-connector-selection-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase9-connector-selection-frontend-build.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase9-connector-selection-diff-check.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase10-planner-loop-action-contract-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase10-diff-check.txt`

## Known gaps
- Full objective remains active: the builder still uses deterministic completeness heuristics for some workflow details; live OpenClaw/GigaChat planning should progressively replace/augment these rules.
- More provider-specific production handlers can be deepened, especially real Telegram post handoff, review publish provider handoff, and compile/preview/run billing ledger coverage.
