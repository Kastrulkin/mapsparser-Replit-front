# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T16:45:00+03:00
- Current phase: Phase 9, real connector selection UX.

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
  - Full agent blueprint suite passed: 153 tests.
  - Frontend production build passed.
  - No schema migration was added.
  - `git diff --check` passed.

## Commands run
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `npm run build` from `frontend/`
- `git diff --check`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase9-connector-selection-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase9-connector-selection-frontend-build.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase9-connector-selection-diff-check.txt`

## Known gaps
- Full objective remains active: live provider-specific selection screens can still be polished, more production provider write handlers remain later phases, and billing ledger coverage for compile/preview/run should continue.
