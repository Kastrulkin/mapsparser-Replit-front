#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${LOCALOS_TEST_DATABASE_URL:?Set an isolated PostgreSQL test database}"
TASK_PYTHON="${PYTHON_BIN:-python3}"
"${TASK_PYTHON}" -m pytest -q -ra \
  tests/test_today_preferences_pg.py \
  tests/test_operator_today_api.py \
  tests/test_operator_mobile_today.py \
  tests/test_product_events_api.py \
  tests/test_runtime_schema_contracts.py \
  tests/test_runtime_queue_pg.py \
  tests/test_runtime_job_reliability.py \
  tests/test_application_boundaries.py \
  tests/test_capabilities_api_phase1.py \
  tests/test_operator_async_jobs.py \
  tests/test_agent_blueprint_async_contracts.py \
  tests/test_agent_blueprint_capabilities.py \
  tests/test_compiled_script_api.py \
  tests/test_compiled_script_artifact.py \
  tests/test_partnership_draft_review.py \
  tests/test_telegram_control_scope.py
"${TASK_PYTHON}" -m compileall -q src
bash -n scripts/smoke_openclaw_m2m_capabilities.sh scripts/smoke_openclaw_m2m_outbox.sh scripts/ci_gate_partnership.sh
