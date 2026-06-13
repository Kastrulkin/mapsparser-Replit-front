# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T12:33:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `tests/test_agent_blueprint_layer.py::test_agent_builder_answer_resources_allow_draft_but_not_preview_without_provider_route` asserts `setup_flow.can_create_draft is True` for Google Sheets -> Telegram with sheet URL and Telegram target but no saved integrations.

### AC2
- Status: PASS
- Proof:
  - `src/api/agent_builder_api.py::_apply_answer_connection_bindings` now merges dialog answer config into `metadata["required_integration_bindings"]`, `agent_binding_integrations`, and `custom_process`.
  - `src/api/agent_builder_api.py::_apply_answer_bindings_to_version_payload` persists dialog resource facts into version `required_integration_bindings.default_config`.
  - The new regression test asserts `spreadsheet_id`, `sheet_name`, and `telegram_target` are present in metadata and version bindings.

### AC3
- Status: PASS
- Proof:
  - `src/services/agent_integration_preflight.py` now returns `builder_answer_needs_provider_route` when resource facts exist but no provider route, saved integration, or allowed fallback is selected.
  - Tests assert preflight remains blocked and `missing_config` is empty when the resource has already been supplied.

### AC4
- Status: PASS
- Proof:
  - `src/api/agent_builder_api.py::create_blueprint_from_agent_builder_session` no longer requires provider routes unless `enforce_provider_routes` is explicitly requested.
  - `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` sends `selected_provider_routes` only when `acceptedBuilderProviderRoutes` is true.
  - Frontend creation decision no longer blocks draft creation just because provider route confirmation is pending.

### AC5
- Status: PASS
- Proof:
  - Existing tests still pass for explicit connection choice, provider route acceptance, preview gate, activation gate, and missing integration blocking.
  - `tests/test_agent_blueprint_layer.py` full suite passed: 144 tests.

### AC6
- Status: PASS
- Proof:
  - `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x` passed: 144 tests.
  - `PYTHONPATH=src python3 -m pytest -q tests/test_agent_builder_billing.py -x` passed: 2 tests.
  - `npm --prefix frontend run build` passed.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'builder_answer_resources or builder_session or compiled_agent_creation_contract_google_sheets_to_telegram or integration_preflight' -x`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_builder_billing.py -x`
- `npm --prefix frontend run build`

## Known gaps
- Full objective remains active: live OpenClaw planning loop, deeper service intelligence, real action handlers, billing ledger expansion, and cockpit simplification still require later phases.
