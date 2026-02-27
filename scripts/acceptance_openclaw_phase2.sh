#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000}"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN:-${OPENCLAW_LOCALOS_TOKEN:-}}"
TENANT_ID="${TENANT_ID:-${OPENCLAW_DEFAULT_TENANT_ID:-}}"
WINDOW_MINUTES="${WINDOW_MINUTES:-120}"

if [[ -z "${OPENCLAW_TOKEN}" ]]; then
  echo "ERROR: OPENCLAW_TOKEN is required." >&2
  exit 1
fi

if [[ -z "${TENANT_ID}" ]]; then
  echo "ERROR: TENANT_ID is required." >&2
  exit 1
fi

echo "[acceptance] base_url=${BASE_URL}"
echo "[acceptance] tenant=${TENANT_ID}"

echo "[1/5] runtime health"
curl -fsSI "${BASE_URL}" | head -n 1

echo "[2/5] capabilities smoke"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" \
  ./scripts/smoke_openclaw_m2m_capabilities.sh

echo "[3/5] outbox smoke"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" \
  ./scripts/smoke_openclaw_m2m_outbox.sh

echo "[4/5] billing reconciliation smoke"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" \
  ./scripts/smoke_openclaw_m2m_reconciliation.sh

echo "[5/5] alerts check"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" WINDOW_MINUTES="${WINDOW_MINUTES}" \
  ./scripts/check_openclaw_outbox_alerts.sh

HEALTH_JSON="$(curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${BASE_URL}/api/openclaw/capabilities/health?tenant_id=${TENANT_ID}&window_minutes=${WINDOW_MINUTES}")"
READY="$(python3 -c 'import json,sys; print("1" if json.loads(sys.stdin.read()).get("ready") else "0")' <<< "${HEALTH_JSON}")"

if [[ "${READY}" != "1" ]]; then
  echo "ERROR: integration health is not ready" >&2
  echo "${HEALTH_JSON}" >&2
  exit 2
fi

echo "[acceptance] OK: Phase 2 checks passed"
