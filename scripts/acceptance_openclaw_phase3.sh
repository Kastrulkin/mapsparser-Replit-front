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

echo "[phase3-acceptance] base_url=${BASE_URL}"
echo "[phase3-acceptance] tenant=${TENANT_ID}"

echo "[1/7] runtime health"
curl -fsSI "${BASE_URL}" | head -n 1

echo "[2/7] capabilities smoke"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" \
  ./scripts/smoke_openclaw_m2m_capabilities.sh

echo "[3/7] outbox smoke"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" \
  ./scripts/smoke_openclaw_m2m_outbox.sh

echo "[4/7] billing reconciliation smoke"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" \
  ./scripts/smoke_openclaw_m2m_reconciliation.sh

echo "[5/7] alerts check"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" BASE_URL="${BASE_URL}" WINDOW_MINUTES="${WINDOW_MINUTES}" \
  ./scripts/check_openclaw_outbox_alerts.sh

echo "[6/7] support export bundle"
SUPPORT_EXPORT_JSON="$(curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${BASE_URL}/api/openclaw/capabilities/support-export?tenant_id=${TENANT_ID}&format=markdown")"
python3 -c 'import json,sys; data=json.loads(sys.stdin.read()); assert data.get("success") is True; report=str(data.get("markdown_report") or ""); assert "# OpenClaw Support Export Bundle" in report; print("Support export bundle OK")' <<< "${SUPPORT_EXPORT_JSON}"

echo "[7/7] support-send history export"
SUPPORT_SEND_HISTORY_JSON="$(curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${BASE_URL}/api/openclaw/capabilities/support-export/send-history/export?tenant_id=${TENANT_ID}&limit=10&format=markdown")"
python3 -c 'import json,sys; data=json.loads(sys.stdin.read()); assert data.get("success") is True; report=str(data.get("markdown_report") or ""); assert "# OpenClaw Support Send History" in report; print("Support-send history export OK")' <<< "${SUPPORT_SEND_HISTORY_JSON}"

HEALTH_JSON="$(curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${BASE_URL}/api/openclaw/capabilities/health?tenant_id=${TENANT_ID}&window_minutes=${WINDOW_MINUTES}")"
READY="$(python3 -c 'import json,sys; print("1" if json.loads(sys.stdin.read()).get("ready") else "0")' <<< "${HEALTH_JSON}")"

if [[ "${READY}" != "1" ]]; then
  echo "ERROR: integration health is not ready" >&2
  echo "${HEALTH_JSON}" >&2
  exit 2
fi

echo "[phase3-acceptance] OK: Phase 3 checks passed"
