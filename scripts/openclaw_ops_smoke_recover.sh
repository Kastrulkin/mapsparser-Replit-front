#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BASE_URL="${BASE_URL:-http://localhost:8000}"
TENANT_ID="${TENANT_ID:-}"
OPENCLAW_TOKEN="${OPENCLAW_TOKEN:-}"
WINDOW_MINUTES="${WINDOW_MINUTES:-60}"
RECOVERY_ATTEMPTS="${RECOVERY_ATTEMPTS:-2}"
STRICT="${STRICT:-1}"
SNAPSHOT_LIMIT="${SNAPSHOT_LIMIT:-2}"

if [[ -z "${OPENCLAW_TOKEN}" ]]; then
  echo "OPENCLAW_TOKEN is required"
  exit 1
fi
if [[ -z "${TENANT_ID}" ]]; then
  echo "TENANT_ID is required"
  exit 1
fi

TMP_DIR="${TMPDIR:-/tmp}/openclaw_ops_recover"
mkdir -p "${TMP_DIR}"

pick_problem_action_ids() {
  curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
    "${BASE_URL}/api/openclaw/callbacks/outbox?tenant_id=${TENANT_ID}&limit=50&offset=0" \
    | python3 - "${SNAPSHOT_LIMIT}" <<'PY'
import json, sys

limit = max(1, min(int(sys.argv[1]), 5))
data = json.load(sys.stdin)
items = data.get("items") or []
picked = []
seen = set()

def priority(item):
    status = str(item.get("status") or "")
    if status == "dlq":
        return 0
    if status == "retry":
        return 1
    return 2

for item in sorted(items, key=priority):
    action_id = str(item.get("action_id") or "").strip()
    if not action_id or action_id in seen:
        continue
    seen.add(action_id)
    picked.append(action_id)
    if len(picked) >= limit:
        break

print("\n".join(picked))
PY
}

print_incident_snapshot() {
  local action_id="$1"
  local label="$2"
  local path="${TMP_DIR}/incident_${label}_${action_id}.json"
  echo "[ops] incident snapshot (${label}) action=${action_id}"
  if ! curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
    "${BASE_URL}/api/openclaw/capabilities/actions/${action_id}/incident-snapshot?tenant_id=${TENANT_ID}" > "${path}"; then
    echo "[ops] failed to fetch incident snapshot for ${action_id}"
    return 1
  fi
  python3 - "${path}" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
overview = data.get("overview") or {}
recent = data.get("recent_timeline") or []
print(json.dumps({
    "action_id": data.get("action_id"),
    "status": data.get("status"),
    "capability": data.get("capability"),
    "overview": overview,
    "last_event": recent[-1] if recent else None,
}, ensure_ascii=False, indent=2))
PY
}

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

PROBLEM_ACTION_IDS="$(pick_problem_action_ids || true)"
if [[ -n "${PROBLEM_ACTION_IDS}" ]]; then
  while IFS= read -r action_id; do
    [[ -n "${action_id}" ]] || continue
    print_incident_snapshot "${action_id}" "before" || true
  done <<< "${PROBLEM_ACTION_IDS}"
fi

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

if [[ -n "${PROBLEM_ACTION_IDS}" ]]; then
  while IFS= read -r action_id; do
    [[ -n "${action_id}" ]] || continue
    print_incident_snapshot "${action_id}" "after" || true
  done <<< "${PROBLEM_ACTION_IDS}"
fi

echo "[ops] 5/5 deep diagnose"
DIAG_ACTION_ID="$(printf '%s\n' "${PROBLEM_ACTION_IDS}" | head -n 1)"
BASE_URL="${BASE_URL}" OPENCLAW_TOKEN="${OPENCLAW_TOKEN}" TENANT_ID="${TENANT_ID}" ACTION_ID="${DIAG_ACTION_ID}" \
  ./scripts/diagnose_openclaw_integration.sh

if [[ "${POST_ALERTS_COUNT}" -gt 0 ]]; then
  echo "[ops] alerts remain after recovery: ${POST_ALERTS_COUNT}"
  if [[ "${STRICT}" == "1" ]]; then
    exit 2
  fi
fi

echo "[ops] OK"
