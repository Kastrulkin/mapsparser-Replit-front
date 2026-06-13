# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T13:55:00+03:00
- Current phase: Phase 3, real connector UX/action handler contract.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/api/agent_builder_api.py::_apply_selected_provider_routes` persists selected routes into `agent_binding_provider_routes`, `agent_binding_integrations`, and `custom_process`.
  - `tests/test_agent_blueprint_layer.py::test_agent_builder_provider_routes_create_action_handler_contracts` asserts persisted OpenClaw and Maton routes.

### AC2
- Status: PASS
- Proof:
  - `src/api/agent_builder_api.py::_connector_action_handler_payload` creates `localos_connector_action_handler_v1` with handler, credential source, preflight resolution, approval/audit and preview side-effect policy.
  - Regression test asserts OpenClaw and Maton handlers.

### AC3
- Status: PASS
- Proof:
  - OpenClaw selected route stores `integration_id: openclaw_boundary`, `requires_external_credentials: false`, `execution_boundary: localos_policy_envelope`, and handler `openclaw_policy_boundary`.

### AC4
- Status: PASS
- Proof:
  - `src/api/agent_builder_api.py::_selected_provider_routes` auto-binds exactly one Maton external account from `externalbusinessaccounts`.
  - `src/api/agent_builder_api.py::_provider_route_selection_errors` returns `maton_key_required` when Maton is selected without a saved key.
  - Regression test covers both paths.

### AC5
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx::BuilderServiceIntelligencePanel` now receives `selectedProviderRoutes` and `onSelectProviderRoute`, and renders the route button directly in the "Что возможно" panel.

### AC6
- Status: PASS
- Proof:
  - Focused connector route tests passed: 5 tests.
  - Full agent blueprint suite passed: 148 tests.
  - Frontend production build passed.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'provider_routes or maton_route or action_handler or service_intelligence' -x`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- `npm --prefix frontend run build`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase3-connector-route-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase3-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase3-frontend-build.txt`

## Known gaps
- Full objective remains active: live OpenClaw planner clarification loop, real provider action execution beyond preflight contracts, billing ledger expansion, and cockpit simplification still require later phases.
