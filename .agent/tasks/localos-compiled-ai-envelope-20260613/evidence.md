# Evidence Bundle: localos-compiled-ai-envelope-20260613

## Summary
- Overall status: PASS for current phase scope.
- Last updated: 2026-06-13T15:08:00+03:00
- Current phase: Phase 6, Google Sheets read / LocalOS finance handler wiring.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/agent_blueprint_runner.py::AgentBlueprintRunner.__init__` now defaults to `ActionOrchestrator(build_capability_handlers())`.

### AC2
- Status: PASS
- Proof:
  - `tests/test_agent_blueprint_layer.py::test_default_runner_is_wired_to_real_google_sheets_and_finance_handlers` asserts `google_sheets.read_rows` exists in the default runner handler map.

### AC3
- Status: PASS
- Proof:
  - The same regression asserts `finance.transaction.create` exists in the default runner handler map.

### AC4
- Status: PASS
- Proof:
  - Existing `test_google_sheets_read_rows_capability_uses_native_provider` still passes.
  - Handler returns `provider_read_performed` for native reads and supports inline rows without provider write.

### AC5
- Status: PASS
- Proof:
  - Existing `test_finance_transaction_create_capability_normalizes_rows_without_localos_write` still passes.
  - Handler creates proposals/request state and records `localos_write_performed: false`.

### AC6
- Status: PASS
- Proof:
  - Focused sheets/finance/Maton tests passed: 5 tests.
  - Full agent blueprint suite passed: 152 tests.
  - Frontend production build passed.

## Commands run
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'default_runner_is_wired or google_sheets_read_rows_capability_uses_native_provider or finance_transaction_create_capability_normalizes_rows_without_localos_write or maton_delivery' -x`
- `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- `npm --prefix frontend run build`

## Raw artifacts
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase6-sheets-finance-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase6-agent-blueprint-tests.txt`
- `.agent/tasks/localos-compiled-ai-envelope-20260613/raw/phase6-frontend-build.txt`

## Known gaps
- Full objective remains active: provider UX for choosing real Google credentials, finance apply UI, billing ledger expansion, and additional provider handlers still require later phases.
