#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

python_bin="${PYTHON_BIN:-venv/bin/python}"
tests=(
  tests/test_agent_template_validation_fixtures.py
  tests/test_agent_template_pilot_readiness.py
  tests/test_agent_blueprint_async_contracts.py::test_agent_run_queue_reuses_existing_idempotency_key
  tests/test_agent_blueprint_async_contracts.py::test_agent_run_claim_recovers_stale_heartbeat_before_claiming_retry
  tests/test_agent_blueprint_capabilities.py::test_google_sheets_adapter_read_rows_refreshes_expired_access_token
  tests/test_agent_blueprint_capabilities.py::test_google_sheets_temporary_provider_error_is_raised_for_worker_retry
  tests/test_agent_blueprint_capabilities.py::test_scheduler_catches_up_after_restart_when_enabled_before_slot
  tests/test_agent_blueprint_capabilities.py::test_scheduled_trigger_runtime_blocks_when_required_sheet_connection_missing
  tests/test_agent_blueprint_runtime_policy.py::test_successful_retry_clears_previous_transient_error
  tests/test_agent_blueprint_runtime_connections.py::test_activate_version_marks_blueprint_active_for_trigger_runtime
  tests/test_agent_blueprint_runtime_connections.py::test_rollback_recognizes_previously_active_version_and_records_transition
)
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec env PYTHONPATH=src arch -arm64 "${python_bin}" -m pytest "${tests[@]}" -q
fi
exec env PYTHONPATH=src "${python_bin}" -m pytest "${tests[@]}" -q
