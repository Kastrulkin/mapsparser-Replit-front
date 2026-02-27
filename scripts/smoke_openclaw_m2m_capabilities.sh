#!/usr/bin/env bash
set -euo pipefail

if [[ "$(pwd)" != "/opt/seo-app" ]]; then
  echo "Run from /opt/seo-app"
  exit 1
fi

if [[ -z "${OPENCLAW_TOKEN:-}" ]]; then
  echo "OPENCLAW_TOKEN is required"
  exit 1
fi

if [[ -z "${TENANT_ID:-}" ]]; then
  echo "TENANT_ID is required"
  exit 1
fi

base_url="${BASE_URL:-http://localhost:8000}"
decision="${DECISION:-}"
decision_reason="${DECISION_REASON:-smoke decision}"
tmp_dir="${TMPDIR:-/tmp}/openclaw_m2m_capabilities_smoke"
mkdir -p "${tmp_dir}"

json_read() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json
import sys

path = sys.argv[1]
expr = sys.argv[2]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
parts = [p for p in expr.split(".") if p]
cur = data
for p in parts:
    if isinstance(cur, dict):
        cur = cur.get(p)
    else:
        cur = None
        break
if isinstance(cur, (dict, list)):
    print(json.dumps(cur, ensure_ascii=False))
elif cur is None:
    print("")
else:
    print(str(cur))
PY
}

trace_id="$(python3 - <<'PY'
import uuid
print(str(uuid.uuid4()))
PY
)"

idempotency_key="$(python3 - <<'PY'
import uuid
print(str(uuid.uuid4()))
PY
)"

execute_payload_file="${tmp_dir}/execute_payload.json"
cat > "${execute_payload_file}" <<EOF
{
  "tenant_id": "${TENANT_ID}",
  "actor": {
    "type": "system",
    "role": "openclaw",
    "channel": "openclaw"
  },
  "trace_id": "${trace_id}",
  "idempotency_key": "${idempotency_key}",
  "capability": "services.optimize",
  "approval": {
    "mode": "required",
    "ttl_sec": 1800
  },
  "billing": {
    "tariff_id": "openclaw-smoke",
    "reserve_tokens": 1200
  },
  "payload": {
    "name": "Робототехника",
    "description": "Курс для детей",
    "bulk": true,
    "source": "file"
  }
}
EOF

echo "[1/8] M2M health"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/health?tenant_id=${TENANT_ID}&window_minutes=120" > "${tmp_dir}/health.json"
health_success="$(json_read "${tmp_dir}/health.json" "success")"
if [[ "${health_success}" != "True" && "${health_success}" != "true" ]]; then
  echo "Health call failed"
  cat "${tmp_dir}/health.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/health.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
checks = data.get("checks") or {}
required = {"token_configured", "callbacks_enabled", "dlq_count", "retry_backlog", "stuck_retry"}
missing = sorted([k for k in required if k not in checks])
if missing:
    print("Missing health checks:", ", ".join(missing))
    sys.exit(1)
print("Health OK:", data.get("status"))
PY
then
  cat "${tmp_dir}/health.json"
  exit 1
fi

echo "[2/8] M2M health trend"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/health/trend?tenant_id=${TENANT_ID}&window_minutes=120&limit=20" > "${tmp_dir}/health_trend.json"
trend_success="$(json_read "${tmp_dir}/health_trend.json" "success")"
if [[ "${trend_success}" != "True" && "${trend_success}" != "true" ]]; then
  echo "Health trend call failed"
  cat "${tmp_dir}/health_trend.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/health_trend.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
items = data.get("items")
if not isinstance(items, list):
    print("Health trend has no items list")
    sys.exit(1)
print("Health trend OK: count=", data.get("count"))
PY
then
  cat "${tmp_dir}/health_trend.json"
  exit 1
fi

echo "[3/8] M2M catalog"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/catalog" > "${tmp_dir}/catalog.json"
catalog_success="$(json_read "${tmp_dir}/catalog.json" "success")"
if [[ "${catalog_success}" != "True" && "${catalog_success}" != "true" ]]; then
  echo "Catalog call failed"
  cat "${tmp_dir}/catalog.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/catalog.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
caps = (data.get("capabilities") or {})
required = {"services.optimize", "reviews.reply", "news.generate", "sales.ingest"}
missing = sorted([x for x in required if x not in caps])
if missing:
    print("Missing capabilities:", ", ".join(missing))
    sys.exit(1)
print("Catalog OK")
PY
then
  cat "${tmp_dir}/catalog.json"
  exit 1
fi

echo "[4/8] M2M execute"
curl -fsS -X POST \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @"${execute_payload_file}" \
  "${base_url}/api/openclaw/capabilities/execute" > "${tmp_dir}/execute.json"
execute_success="$(json_read "${tmp_dir}/execute.json" "success")"
execute_status="$(json_read "${tmp_dir}/execute.json" "status")"
action_id="$(json_read "${tmp_dir}/execute.json" "action_id")"
if [[ "${execute_success}" != "True" && "${execute_success}" != "true" ]]; then
  echo "Execute failed"
  cat "${tmp_dir}/execute.json"
  exit 1
fi
if [[ -z "${action_id}" ]]; then
  echo "Execute response has no action_id"
  cat "${tmp_dir}/execute.json"
  exit 1
fi
echo "Execute OK: action_id=${action_id}, status=${execute_status}"

echo "[5/10] M2M action status"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}?tenant_id=${TENANT_ID}" > "${tmp_dir}/status.json"
status_success="$(json_read "${tmp_dir}/status.json" "success")"
status_value="$(json_read "${tmp_dir}/status.json" "status")"
if [[ "${status_success}" != "True" && "${status_success}" != "true" ]]; then
  echo "Status read failed"
  cat "${tmp_dir}/status.json"
  exit 1
fi
echo "Status OK: ${status_value}"

echo "[6/10] M2M action timeline"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/timeline?tenant_id=${TENANT_ID}&limit=200" > "${tmp_dir}/timeline.json"
timeline_success="$(json_read "${tmp_dir}/timeline.json" "success")"
if [[ "${timeline_success}" != "True" && "${timeline_success}" != "true" ]]; then
  echo "Timeline read failed"
  cat "${tmp_dir}/timeline.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/timeline.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
events = data.get("events")
if not isinstance(events, list) or len(events) == 0:
    print("Timeline has no events")
    sys.exit(1)
print("Timeline OK: count=", data.get("count"))
PY
then
  cat "${tmp_dir}/timeline.json"
  exit 1
fi

echo "[7/10] M2M action billing"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/billing?tenant_id=${TENANT_ID}" > "${tmp_dir}/billing.json"
billing_success="$(json_read "${tmp_dir}/billing.json" "success")"
if [[ "${billing_success}" != "True" && "${billing_success}" != "true" ]]; then
  echo "Billing read failed"
  cat "${tmp_dir}/billing.json"
  exit 1
fi
echo "Billing OK"

if [[ -n "${decision}" ]]; then
  if [[ "${decision}" != "approved" && "${decision}" != "rejected" && "${decision}" != "expired" ]]; then
    echo "DECISION must be approved|rejected|expired"
    exit 1
  fi

  echo "[8/10] M2M action decision (${decision})"
  decision_payload_file="${tmp_dir}/decision_payload.json"
  cat > "${decision_payload_file}" <<EOF
{
  "tenant_id": "${TENANT_ID}",
  "decision": "${decision}",
  "reason": "${decision_reason}"
}
EOF

  curl -fsS -X POST \
    -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
    -H "Content-Type: application/json" \
    -d @"${decision_payload_file}" \
    "${base_url}/api/openclaw/capabilities/actions/${action_id}/decision" > "${tmp_dir}/decision.json"
  decision_success="$(json_read "${tmp_dir}/decision.json" "success")"
  if [[ "${decision_success}" != "True" && "${decision_success}" != "true" ]]; then
    echo "Decision failed"
    cat "${tmp_dir}/decision.json"
    exit 1
  fi
  echo "Decision OK"

  echo "[9/10] M2M final status"
  curl -fsS \
    -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
    "${base_url}/api/openclaw/capabilities/actions/${action_id}?tenant_id=${TENANT_ID}" > "${tmp_dir}/final_status.json"
  final_success="$(json_read "${tmp_dir}/final_status.json" "success")"
  final_status="$(json_read "${tmp_dir}/final_status.json" "status")"
  if [[ "${final_success}" != "True" && "${final_success}" != "true" ]]; then
    echo "Final status read failed"
    cat "${tmp_dir}/final_status.json"
    exit 1
  fi
  if [[ "${final_status}" != "${decision}" && ! ("${decision}" == "approved" && "${final_status}" == "completed") ]]; then
    echo "Unexpected final status: ${final_status}"
    cat "${tmp_dir}/final_status.json"
    exit 1
  fi
  echo "Final status OK: ${final_status}"

  echo "[10/10] M2M final timeline"
  curl -fsS \
    -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
    "${base_url}/api/openclaw/capabilities/actions/${action_id}/timeline?tenant_id=${TENANT_ID}&limit=200" > "${tmp_dir}/timeline_final.json"
  timeline_final_success="$(json_read "${tmp_dir}/timeline_final.json" "success")"
  if [[ "${timeline_final_success}" != "True" && "${timeline_final_success}" != "true" ]]; then
    echo "Final timeline read failed"
    cat "${tmp_dir}/timeline_final.json"
    exit 1
  fi
fi

echo "OK: OpenClaw M2M capability smoke passed"
