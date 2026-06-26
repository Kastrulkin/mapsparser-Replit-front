# Evidence Bundle: google-sheets-reference-agent-20260626

## Summary
- Overall status: PASS
- Last updated: 2026-06-26T09:18:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/google_business_auth.py` now includes `https://www.googleapis.com/auth/spreadsheets`.
  - `tests/test_agent_blueprint_layer.py::test_google_oauth_requests_sheets_scope_for_agent_runtime` passed.
- Gaps:
  - Existing Google OAuth accounts must reconnect to receive the new scope.

### AC2
- Status: PASS
- Proof:
  - `src/api/agent_blueprints_api.py` resolves missing Google Sheets `auth_ref` from active `google_sheets` or `google_business` external accounts with encrypted auth.
  - `tests/test_agent_blueprint_layer.py::test_google_sheets_integration_auto_binds_google_business_auth_ref` passed.
- Gaps:
  - Production currently has a Google Sheets integration without auth_ref; it needs user OAuth reconnect/save.

### AC3
- Status: PASS
- Proof:
  - `src/services/agent_integration_preflight.py` allows native Google Sheets read only when config is complete and an `auth_ref` is bound.
  - Existing no-auth route-required behavior is preserved by `test_sync_blueprint_integration_metadata_records_selected_binding`.
  - New ready path is covered by `test_agent_preflight_allows_google_sheets_native_read_when_auth_ref_bound`.
- Gaps:
  - Live provider read remains blocked until OAuth is reconnected with Sheets scope.

### AC4
- Status: PASS
- Proof:
  - Added `scripts/smoke_google_sheets_reference_agent.py`.
  - Added docs at `docs/agents/google-sheets-reference-agent.md`.
  - Script compiles via py_compile.
- Gaps:
  - Full PASS requires real OAuth credentials with Sheets scope; without that the smoke returns a blocked runtime state.

## Commands run
- `python3 -m py_compile src/google_business_auth.py src/api/agent_blueprints_api.py src/services/agent_integration_preflight.py src/services/agent_google_sheets_adapter.py scripts/smoke_google_sheets_reference_agent.py`
- `venv/bin/python -m pytest -q tests/test_agent_blueprint_layer.py -k "google_oauth_requests_sheets_scope or google_sheets_integration_auto_binds_google_business_auth_ref or agent_preflight_allows_google_sheets_native_read_when_auth_ref_bound or sync_blueprint_integration_metadata_records_selected_binding or google_sheets_adapter_loads_active_agent_integration_credentials or google_sheets_read_rows_capability_uses_native_provider"`
- `venv/bin/python -m pytest -q tests/test_agent_blueprint_layer.py`
- `git diff --check`

## Raw artifacts
- .agent/tasks/google-sheets-reference-agent-20260626/raw/build.txt
- .agent/tasks/google-sheets-reference-agent-20260626/raw/test-unit.txt
- .agent/tasks/google-sheets-reference-agent-20260626/raw/test-integration.txt
- .agent/tasks/google-sheets-reference-agent-20260626/raw/lint.txt
- .agent/tasks/google-sheets-reference-agent-20260626/raw/screenshot-1.png

## Known gaps
- Production live read needs the user to reconnect Google after the new Sheets OAuth scope is deployed.
- The reference smoke is read-only and does not create Telegram/WhatsApp delivery.
