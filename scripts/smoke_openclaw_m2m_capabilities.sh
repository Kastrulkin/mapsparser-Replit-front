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

echo "[1/12] M2M health"
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

echo "[2/12] M2M health trend"
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

echo "[3/12] M2M catalog"
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

echo "[4/12] M2M execute"
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

echo "[5/12] M2M action status"
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

echo "[6/12] M2M action timeline"
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
total = int(data.get("total_count") or 0)
count = int(data.get("count") or 0)
if total < count:
    print("Timeline total_count < count")
    sys.exit(1)
print("Timeline OK: count=", data.get("count"))
PY
then
  cat "${tmp_dir}/timeline.json"
  exit 1
fi

curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/timeline?tenant_id=${TENANT_ID}&limit=20&offset=0&source=action_transition" > "${tmp_dir}/timeline_filtered.json"
timeline_filtered_success="$(json_read "${tmp_dir}/timeline_filtered.json" "success")"
if [[ "${timeline_filtered_success}" != "True" && "${timeline_filtered_success}" != "true" ]]; then
  echo "Timeline filtered read failed"
  cat "${tmp_dir}/timeline_filtered.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/timeline_filtered.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
events = data.get("events")
if not isinstance(events, list):
    print("Timeline filtered has no events list")
    sys.exit(1)
if any((e or {}).get("source") != "action_transition" for e in events):
    print("Timeline filtered contains unexpected source")
    sys.exit(1)
print("Timeline filtered OK: count=", data.get("count"))
PY
then
  cat "${tmp_dir}/timeline_filtered.json"
  exit 1
fi

echo "[7/12] M2M action callback-attempts"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/callback-attempts?tenant_id=${TENANT_ID}&limit=200&offset=0" > "${tmp_dir}/callback_attempts.json"
callback_attempts_success="$(json_read "${tmp_dir}/callback_attempts.json" "success")"
if [[ "${callback_attempts_success}" != "True" && "${callback_attempts_success}" != "true" ]]; then
  echo "Callback-attempts read failed"
  cat "${tmp_dir}/callback_attempts.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/callback_attempts.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
items = data.get("items")
if not isinstance(items, list):
    print("callback-attempts has no items list")
    sys.exit(1)
breakdown = data.get("event_type_breakdown")
if not isinstance(breakdown, list):
    print("callback-attempts has no event_type_breakdown list")
    sys.exit(1)
print("Callback-attempts OK: total=", data.get("total"))
PY
then
  cat "${tmp_dir}/callback_attempts.json"
  exit 1
fi

echo "[8/12] M2M action support package"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/support-package?tenant_id=${TENANT_ID}&limit=200" > "${tmp_dir}/support_package.json"
support_success="$(json_read "${tmp_dir}/support_package.json" "success")"
if [[ "${support_success}" != "True" && "${support_success}" != "true" ]]; then
  echo "Support package read failed"
  cat "${tmp_dir}/support_package.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/support_package.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
if not data.get("action", {}).get("success"):
    print("Support package.action is not successful")
    sys.exit(1)
if not data.get("billing", {}).get("success"):
    print("Support package.billing is not successful")
    sys.exit(1)
timeline = data.get("timeline", {})
if not timeline.get("success"):
    print("Support package.timeline is not successful")
    sys.exit(1)
events = timeline.get("events")
if not isinstance(events, list) or len(events) == 0:
    print("Support package.timeline has no events")
    sys.exit(1)
print("Support package OK")
PY
then
  cat "${tmp_dir}/support_package.json"
  exit 1
fi

curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/support-package?tenant_id=${TENANT_ID}&limit=200&source=action_transition" > "${tmp_dir}/support_package_filtered.json"
support_filtered_success="$(json_read "${tmp_dir}/support_package_filtered.json" "success")"
if [[ "${support_filtered_success}" != "True" && "${support_filtered_success}" != "true" ]]; then
  echo "Support package filtered read failed"
  cat "${tmp_dir}/support_package_filtered.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/support_package_filtered.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
timeline = data.get("timeline", {})
events = timeline.get("events")
if not isinstance(events, list):
    print("Support package filtered has no events list")
    sys.exit(1)
if any((e or {}).get("source") != "action_transition" for e in events):
    print("Support package filtered contains unexpected source")
    sys.exit(1)
print("Support package filtered OK: count=", timeline.get("count"))
PY
then
  cat "${tmp_dir}/support_package_filtered.json"
  exit 1
fi

curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/support-package?tenant_id=${TENANT_ID}&limit=2&offset=0&full=true" > "${tmp_dir}/support_package_full.json"
support_full_success="$(json_read "${tmp_dir}/support_package_full.json" "success")"
if [[ "${support_full_success}" != "True" && "${support_full_success}" != "true" ]]; then
  echo "Support package full read failed"
  cat "${tmp_dir}/support_package_full.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/support_package_full.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
timeline = data.get("timeline", {})
count = int(timeline.get("count") or 0)
total = int(timeline.get("total_count") or 0)
if count <= 0:
    print("Support package full has empty timeline")
    sys.exit(1)
if total != count:
    print("Support package full total_count mismatch", total, count)
    sys.exit(1)
print("Support package full OK: count=", count)
PY
then
  cat "${tmp_dir}/support_package_full.json"
  exit 1
fi

curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/diagnostics-bundle?tenant_id=${TENANT_ID}&limit=2&offset=0&full=true&attempts_full=true" > "${tmp_dir}/diagnostics_bundle.json"
bundle_success="$(json_read "${tmp_dir}/diagnostics_bundle.json" "success")"
if [[ "${bundle_success}" != "True" && "${bundle_success}" != "true" ]]; then
  echo "Diagnostics bundle read failed"
  cat "${tmp_dir}/diagnostics_bundle.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/diagnostics_bundle.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
support = data.get("support_package", {})
attempts = data.get("callback_attempts", {})
if not support.get("success"):
    print("Diagnostics bundle support_package is not successful")
    sys.exit(1)
if not attempts.get("success"):
    print("Diagnostics bundle callback_attempts is not successful")
    sys.exit(1)
if not data.get("generated_at"):
    print("Diagnostics bundle has no generated_at")
    sys.exit(1)
print("Diagnostics bundle OK")
PY
then
  cat "${tmp_dir}/diagnostics_bundle.json"
  exit 1
fi

echo "[8.1/12] M2M action diagnostics bundle (markdown)"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/diagnostics-bundle?tenant_id=${TENANT_ID}&limit=2&offset=0&full=true&attempts_full=true&format=markdown" > "${tmp_dir}/diagnostics_bundle_markdown.json"
bundle_md_success="$(json_read "${tmp_dir}/diagnostics_bundle_markdown.json" "success")"
if [[ "${bundle_md_success}" != "True" && "${bundle_md_success}" != "true" ]]; then
  echo "Diagnostics bundle markdown read failed"
  cat "${tmp_dir}/diagnostics_bundle_markdown.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/diagnostics_bundle_markdown.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
report = data.get("markdown_report")
if not isinstance(report, str) or "# OpenClaw Action Diagnostics Bundle" not in report:
    print("Diagnostics bundle markdown_report is invalid")
    sys.exit(1)
print("Diagnostics bundle markdown OK")
PY
then
  cat "${tmp_dir}/diagnostics_bundle_markdown.json"
  exit 1
fi

echo "[8.2/12] M2M action lifecycle summary"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/lifecycle-summary?tenant_id=${TENANT_ID}&full=true" > "${tmp_dir}/lifecycle_summary.json"
lifecycle_summary_success="$(json_read "${tmp_dir}/lifecycle_summary.json" "success")"
if [[ "${lifecycle_summary_success}" != "True" && "${lifecycle_summary_success}" != "true" ]]; then
  echo "Lifecycle summary read failed"
  cat "${tmp_dir}/lifecycle_summary.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/lifecycle_summary.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
lifecycle = data.get("lifecycle") or {}
required = {"pending_human", "approved", "rejected", "expired", "completed"}
missing = sorted([k for k in required if k not in lifecycle])
if missing:
    print("Lifecycle summary missing keys:", ", ".join(missing))
    sys.exit(1)
print("Lifecycle summary OK: events=", data.get("filtered_events"), "/", data.get("total_events"))
PY
then
  cat "${tmp_dir}/lifecycle_summary.json"
  exit 1
fi

echo "[8.3/12] M2M action incident report"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/incident-report?tenant_id=${TENANT_ID}" > "${tmp_dir}/incident_report.json"
incident_report_success="$(json_read "${tmp_dir}/incident_report.json" "success")"
if [[ "${incident_report_success}" != "True" && "${incident_report_success}" != "true" ]]; then
  echo "Incident report read failed"
  cat "${tmp_dir}/incident_report.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/incident_report.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
report = data.get("markdown_report")
if not isinstance(report, str) or "# OpenClaw Incident Report" not in report:
    print("Incident report markdown_report is invalid")
    sys.exit(1)
print("Incident report markdown OK")
PY
then
  cat "${tmp_dir}/incident_report.json"
  exit 1
fi

echo "[8.4/12] M2M action incident snapshot"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/actions/${action_id}/incident-snapshot?tenant_id=${TENANT_ID}" > "${tmp_dir}/incident_snapshot.json"
incident_snapshot_success="$(json_read "${tmp_dir}/incident_snapshot.json" "success")"
if [[ "${incident_snapshot_success}" != "True" && "${incident_snapshot_success}" != "true" ]]; then
  echo "Incident snapshot read failed"
  cat "${tmp_dir}/incident_snapshot.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/incident_snapshot.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
overview = data.get("overview") or {}
recent = data.get("recent_timeline")
if not isinstance(overview, dict):
    print("Incident snapshot overview is invalid")
    sys.exit(1)
if not isinstance(recent, list):
    print("Incident snapshot recent_timeline is invalid")
    sys.exit(1)
if "diagnostics_bundle" not in data:
    print("Incident snapshot has no diagnostics_bundle")
    sys.exit(1)
print("Incident snapshot OK")
PY
then
  cat "${tmp_dir}/incident_snapshot.json"
  exit 1
fi

echo "[8.5/12] M2M recovery history"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/callbacks/recovery-history?tenant_id=${TENANT_ID}&limit=5" > "${tmp_dir}/recovery_history.json"
recovery_history_success="$(json_read "${tmp_dir}/recovery_history.json" "success")"
if [[ "${recovery_history_success}" != "True" && "${recovery_history_success}" != "true" ]]; then
  echo "Recovery history read failed"
  cat "${tmp_dir}/recovery_history.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/recovery_history.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
items = data.get("items")
if not isinstance(items, list):
    print("Recovery history has no items list")
    sys.exit(1)
print("Recovery history OK: count=", data.get("count"))
PY
then
  cat "${tmp_dir}/recovery_history.json"
  exit 1
fi

echo "[8.6/12] M2M recovery history export"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/callbacks/recovery-history/export?tenant_id=${TENANT_ID}&limit=5&format=markdown" > "${tmp_dir}/recovery_history_export.json"
recovery_history_export_success="$(json_read "${tmp_dir}/recovery_history_export.json" "success")"
if [[ "${recovery_history_export_success}" != "True" && "${recovery_history_export_success}" != "true" ]]; then
  echo "Recovery history export failed"
  cat "${tmp_dir}/recovery_history_export.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/recovery_history_export.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
report = data.get("markdown_report")
if not isinstance(report, str) or "# OpenClaw Recovery History" not in report:
    print("Recovery history markdown_report is invalid")
    sys.exit(1)
print("Recovery history export OK")
PY
then
  cat "${tmp_dir}/recovery_history_export.json"
  exit 1
fi

echo "[8.7/12] M2M support export bundle"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/support-export?tenant_id=${TENANT_ID}&action_id=${action_id}&format=markdown" > "${tmp_dir}/support_export.json"
support_export_success="$(json_read "${tmp_dir}/support_export.json" "success")"
if [[ "${support_export_success}" != "True" && "${support_export_success}" != "true" ]]; then
  echo "Support export bundle failed"
  cat "${tmp_dir}/support_export.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/support_export.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
report = data.get("markdown_report")
if not isinstance(report, str) or "# OpenClaw Support Export Bundle" not in report:
    print("Support export markdown_report is invalid")
    sys.exit(1)
print("Support export bundle OK")
PY
then
  cat "${tmp_dir}/support_export.json"
  exit 1
fi

echo "[8.8/12] M2M support-send history export"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/support-export/send-history/export?tenant_id=${TENANT_ID}&limit=5&format=markdown" > "${tmp_dir}/support_send_history_export.json"
support_send_history_export_success="$(json_read "${tmp_dir}/support_send_history_export.json" "success")"
if [[ "${support_send_history_export_success}" != "True" && "${support_send_history_export_success}" != "true" ]]; then
  echo "Support-send history export failed"
  cat "${tmp_dir}/support_send_history_export.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/support_send_history_export.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
report = data.get("markdown_report")
if not isinstance(report, str) or "# OpenClaw Support Send History" not in report:
    print("Support-send history markdown_report is invalid")
    sys.exit(1)
print("Support-send history export OK")
PY
then
  cat "${tmp_dir}/support_send_history_export.json"
  exit 1
fi

echo "[8.9/12] M2M unified audit timeline"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/audit-timeline?tenant_id=${TENANT_ID}&limit=20" > "${tmp_dir}/audit_timeline.json"
audit_timeline_success="$(json_read "${tmp_dir}/audit_timeline.json" "success")"
if [[ "${audit_timeline_success}" != "True" && "${audit_timeline_success}" != "true" ]]; then
  echo "Unified audit timeline failed"
  cat "${tmp_dir}/audit_timeline.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/audit_timeline.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
items = data.get("items")
if not isinstance(items, list):
    print("Unified audit timeline has no items list")
    sys.exit(1)
if int(data.get("total_count") or 0) < int(data.get("count") or 0):
    print("Unified audit timeline total_count < count")
    sys.exit(1)
print("Unified audit timeline OK: count=", data.get("count"))
PY
then
  cat "${tmp_dir}/audit_timeline.json"
  exit 1
fi

echo "[8.10/12] M2M unified audit timeline export"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/audit-timeline/export?tenant_id=${TENANT_ID}&limit=20&format=markdown" > "${tmp_dir}/audit_timeline_export.json"
audit_timeline_export_success="$(json_read "${tmp_dir}/audit_timeline_export.json" "success")"
if [[ "${audit_timeline_export_success}" != "True" && "${audit_timeline_export_success}" != "true" ]]; then
  echo "Unified audit timeline export failed"
  cat "${tmp_dir}/audit_timeline_export.json"
  exit 1
fi
if ! python3 - "${tmp_dir}/audit_timeline_export.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
report = data.get("markdown_report")
if not isinstance(report, str) or "# OpenClaw Unified Audit Timeline" not in report:
    print("Unified audit timeline markdown_report is invalid")
    sys.exit(1)
print("Unified audit timeline export OK")
PY
then
  cat "${tmp_dir}/audit_timeline_export.json"
  exit 1
fi

echo "[8.11/12] M2M audit event bundle"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/audit-timeline?tenant_id=${TENANT_ID}&limit=20&source=support_send" > "${tmp_dir}/audit_timeline_support_send.json"
python3 - "${tmp_dir}/audit_timeline_support_send.json" > "${tmp_dir}/audit_event_query.txt" <<'PY'
import json, sys, urllib.parse
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
items = data.get("items") or []
if not items:
    print("NO_EVENT")
    sys.exit(0)
item = items[0]
params = urllib.parse.urlencode({
    "tenant_id": data.get("tenant_id") or "",
    "event_id": item.get("event_id") or "",
    "source": item.get("source") or "",
    "format": "markdown",
})
print(params)
PY
if [[ "$(cat "${tmp_dir}/audit_event_query.txt")" != "NO_EVENT" ]]; then
  curl -fsS \
    -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
    "${base_url}/api/openclaw/audit-timeline/event-bundle?$(cat "${tmp_dir}/audit_event_query.txt")" > "${tmp_dir}/audit_event_bundle.json"
  if ! python3 - "${tmp_dir}/audit_event_bundle.json" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
report = data.get("markdown_report")
if not isinstance(report, str) or "# OpenClaw Audit Event Bundle" not in report:
    print("Audit event bundle markdown_report is invalid")
    sys.exit(1)
print("Audit event bundle OK")
PY
  then
    cat "${tmp_dir}/audit_event_bundle.json"
    exit 1
  fi
else
  echo "Audit event bundle skipped: no support_send event"
fi

echo "[9/12] M2M action billing"
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

  echo "[10/12] M2M action decision (${decision})"
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

  echo "[11/12] M2M final status"
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

  echo "[12/12] M2M final timeline"
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
