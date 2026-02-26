#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[CI gate] duplicate suffix guard"
./scripts/check_duplicate_suffix_files.sh

echo "[CI gate] py_compile"
python3 -m py_compile src/main.py src/core/action_orchestrator.py src/worker.py

echo "[CI gate] phase1/phase2 integration tests"
python3 -m pytest -q tests/test_capabilities_api_phase1.py -ra

echo "[CI gate] smoke script syntax"
bash -n scripts/smoke_openclaw_m2m_capabilities.sh
bash -n scripts/smoke_openclaw_m2m_outbox.sh
bash -n scripts/smoke_openclaw_m2m_reconciliation.sh
bash -n scripts/check_openclaw_outbox_alerts.sh

if [[ -n "${CI:-}" ]]; then
  echo "[CI gate] CI mode: M2M smoke is mandatory"
  : "${OPENCLAW_TOKEN:?OPENCLAW_TOKEN is required in CI}"
  : "${TENANT_ID:?TENANT_ID is required in CI}"
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
    OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" \
    TENANT_ID="${TENANT_ID}" \
    ./scripts/smoke_openclaw_m2m_capabilities.sh
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
    OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" \
    TENANT_ID="${TENANT_ID}" \
    ./scripts/smoke_openclaw_m2m_outbox.sh
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
    OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" \
    TENANT_ID="${TENANT_ID}" \
    ./scripts/smoke_openclaw_m2m_reconciliation.sh
elif [[ -n "${OPENCLAW_TOKEN:-}" && -n "${TENANT_ID:-}" ]]; then
  echo "[CI gate] local mode: running optional M2M smoke"
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
    OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" \
    TENANT_ID="${TENANT_ID}" \
    ./scripts/smoke_openclaw_m2m_capabilities.sh
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
    OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" \
    TENANT_ID="${TENANT_ID}" \
    ./scripts/smoke_openclaw_m2m_outbox.sh
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
    OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" \
    TENANT_ID="${TENANT_ID}" \
    ./scripts/smoke_openclaw_m2m_reconciliation.sh
else
  echo "[CI gate] local mode: OPENCLAW_TOKEN/TENANT_ID not set, skipping M2M smoke"
fi

echo "[CI gate] OK"
