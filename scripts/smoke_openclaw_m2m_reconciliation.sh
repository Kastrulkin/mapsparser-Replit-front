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
window_minutes="${WINDOW_MINUTES:-1440}"
limit="${LIMIT:-200}"

echo "[1/1] M2M billing reconciliation"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/capabilities/billing/reconcile?tenant_id=${TENANT_ID}&window_minutes=${window_minutes}&limit=${limit}" > /tmp/openclaw_reconcile.json
cat /tmp/openclaw_reconcile.json
echo

python3 - <<'PY'
import json
with open("/tmp/openclaw_reconcile.json", "r", encoding="utf-8") as f:
    data = json.load(f)
if not data.get("success"):
    raise SystemExit("reconciliation failed")
summary = data.get("summary") or {}
print("OK: reconcile success")
print("actions_checked=", summary.get("actions_checked"))
print("actions_with_issues=", summary.get("actions_with_issues"))
print("tokenusage_minus_settled=", summary.get("tokenusage_minus_settled"))
PY
