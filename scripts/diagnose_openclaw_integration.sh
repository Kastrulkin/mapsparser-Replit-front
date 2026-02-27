#!/usr/bin/env bash
set -euo pipefail

if [[ "$(pwd)" != "/opt/seo-app" ]]; then
  echo "Run from /opt/seo-app"
  exit 1
fi

base_url="${BASE_URL:-http://localhost:8000}"
window="${WINDOW_MINUTES:-120}"
log_window="${LOG_WINDOW:-15m}"
limit="${LIMIT:-20}"
action_id="${ACTION_ID:-}"

echo "== OpenClaw/LocalOS diagnostics =="
echo "cwd: $(pwd)"
echo "base_url: ${base_url}"
echo "window_minutes: ${window}"
if [[ -n "${action_id}" ]]; then
  echo "action_id: ${action_id}"
fi
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

echo "== Runtime =="
docker compose ps || true
echo
docker compose logs --since "${log_window}" app | tail -n 120 || true
echo
docker compose logs --since "${log_window}" worker | tail -n 120 || true
echo
curl -fsS -I "${base_url}" || true
echo

if [[ -z "${OPENCLAW_TOKEN:-}" || -z "${TENANT_ID:-}" ]]; then
  echo "OPENCLAW_TOKEN/TENANT_ID are not set, skipping M2M endpoint diagnostics"
  exit 0
fi

tmp_dir="${TMPDIR:-/tmp}/openclaw_diag"
mkdir -p "${tmp_dir}"

fetch_json() {
  local name="$1"
  local url="$2"
  local path="${tmp_dir}/${name}.json"
  echo "-- ${name}: ${url}"
  if ! curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" "${url}" > "${path}"; then
    echo "FAILED: ${name}"
    return 1
  fi
  python3 - "${path}" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
print(json.dumps(data, ensure_ascii=False, indent=2))
PY
}

echo "== M2M endpoints =="
fetch_json "health" "${base_url}/api/openclaw/capabilities/health?tenant_id=${TENANT_ID}&window_minutes=${window}" || true
echo
fetch_json "health_trend" "${base_url}/api/openclaw/capabilities/health/trend?tenant_id=${TENANT_ID}&window_minutes=${window}&limit=${limit}" || true
echo
fetch_json "callbacks_metrics" "${base_url}/api/openclaw/callbacks/metrics?tenant_id=${TENANT_ID}&window_minutes=${window}" || true
echo
fetch_json "outbox" "${base_url}/api/openclaw/callbacks/outbox?tenant_id=${TENANT_ID}&limit=${limit}&offset=0" || true
echo
fetch_json "billing_reconcile" "${base_url}/api/openclaw/capabilities/billing/reconcile?tenant_id=${TENANT_ID}&window_minutes=${window}&limit=${limit}" || true
echo
if [[ -n "${action_id}" ]]; then
  fetch_json "action_status" "${base_url}/api/openclaw/capabilities/actions/${action_id}?tenant_id=${TENANT_ID}" || true
  echo
  fetch_json "action_billing" "${base_url}/api/openclaw/capabilities/actions/${action_id}/billing?tenant_id=${TENANT_ID}" || true
  echo
  fetch_json "action_timeline" "${base_url}/api/openclaw/capabilities/actions/${action_id}/timeline?tenant_id=${TENANT_ID}&limit=200" || true
  echo
  fetch_json "action_support_package" "${base_url}/api/openclaw/capabilities/actions/${action_id}/support-package?tenant_id=${TENANT_ID}&limit=200" || true
  echo
fi

echo "== Result =="
python3 - "${tmp_dir}/health.json" "${tmp_dir}/callbacks_metrics.json" "${tmp_dir}/billing_reconcile.json" <<'PY'
import json, sys

def load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

health = load(sys.argv[1])
metrics = load(sys.argv[2])
billing = load(sys.argv[3])
status = health.get("status")
alerts = metrics.get("alerts") or []
dlq = int((metrics.get("metrics") or {}).get("dlq", 0) or 0)
stuck = int((metrics.get("metrics") or {}).get("stuck_retry", 0) or 0)
billing_issues = int((billing.get("summary") or {}).get("issue_count", 0) or 0)
if status == "ready" and not alerts and dlq == 0 and stuck == 0 and billing_issues == 0:
    print("OK: integration ready")
    raise SystemExit(0)
print("WARN: integration requires attention")
print(f"status={status} alerts={len(alerts)} dlq={dlq} stuck_retry={stuck} billing_issues={billing_issues}")
raise SystemExit(2)
PY
