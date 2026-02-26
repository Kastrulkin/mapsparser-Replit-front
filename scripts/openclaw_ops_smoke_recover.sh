#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BASE_URL="${BASE_URL:-http://localhost:8000}"
TENANT_ID="${TENANT_ID:-}"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN:-}"
WINDOW_MINUTES="${WINDOW_MINUTES:-60}"
RECOVERY_ATTEMPTS="${RECOVERY_ATTEMPTS:-2}"
STRICT="${STRICT:-1}"

if [[ -z "${OPENCLAW_TOKEN}" ]]; then
  echo "OPENCLAW_TOKEN is required"
  exit 1
fi
if [[ -z "${TENANT_ID}" ]]; then
  echo "TENANT_ID is required"
  exit 1
fi

echo "[ops] 1/5 capabilities smoke"
BASE_URL="${BASE_URL}" OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" \
  ./scripts/smoke_openclaw_m2m_capabilities.sh

echo "[ops] 2/5 outbox smoke"
BASE_URL="${BASE_URL}" OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" \
  ./scripts/smoke_openclaw_m2m_outbox.sh

echo "[ops] 3/5 current callbacks metrics"
METRICS_JSON="$(curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${BASE_URL}/api/openclaw/callbacks/metrics?tenant_id=${TENANT_ID}&window_minutes=${WINDOW_MINUTES}")"
echo "${METRICS_JSON}" | python3 -m json.tool

ALERTS_COUNT="$(python3 - <<'PY' "${METRICS_JSON}"
import json, sys
obj = json.loads(sys.argv[1])
print(len(obj.get("alerts") or []))
PY
)"

if [[ "${ALERTS_COUNT}" -gt 0 ]]; then
  echo "[ops] alerts detected: ${ALERTS_COUNT}. Starting recovery..."
  for ((i=1; i<=RECOVERY_ATTEMPTS; i++)); do
    echo "[ops][recovery] attempt ${i}/${RECOVERY_ATTEMPTS}: replay dlq+retry -> dispatch"
    BASE_URL="${BASE_URL}" OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" \
      ACTION=replay INCLUDE_RETRY=true LIMIT=500 ./scripts/manage_openclaw_outbox.sh

    curl -fsS -X POST \
      -H "Content-Type: application/json" \
      -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
      -d "{\"tenant_id\":\"${TENANT_ID}\",\"batch_size\":100}" \
      "${BASE_URL}/api/openclaw/callbacks/dispatch" >/tmp/openclaw_dispatch_recover.json || true
    cat /tmp/openclaw_dispatch_recover.json || true
    sleep 2
  done
fi

echo "[ops] 4/5 post-recovery callbacks metrics"
POST_JSON="$(curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${BASE_URL}/api/openclaw/callbacks/metrics?tenant_id=${TENANT_ID}&window_minutes=${WINDOW_MINUTES}")"
echo "${POST_JSON}" | python3 -m json.tool

POST_ALERTS_COUNT="$(python3 - <<'PY' "${POST_JSON}"
import json, sys
obj = json.loads(sys.argv[1])
print(len(obj.get("alerts") or []))
PY
)"

echo "[ops] 5/5 deep diagnose"
BASE_URL="${BASE_URL}" OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" \
  ./scripts/diagnose_openclaw_integration.sh

if [[ "${POST_ALERTS_COUNT}" -gt 0 ]]; then
  echo "[ops] alerts remain after recovery: ${POST_ALERTS_COUNT}"
  if [[ "${STRICT}" == "1" ]]; then
    exit 2
  fi
fi

echo "[ops] OK"
