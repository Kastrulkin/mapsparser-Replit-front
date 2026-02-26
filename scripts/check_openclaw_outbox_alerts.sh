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
response="$(curl -fsS -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" "${base_url}/api/openclaw/callbacks/metrics?tenant_id=${TENANT_ID}&window_minutes=60")"
echo "${response}"

alerts_count="$(echo "${response}" | python3 -c 'import sys, json; d=json.load(sys.stdin); print(len(d.get("alerts", [])))')"
if [[ "${alerts_count}" -gt 0 ]]; then
  echo "ALERT: callbacks metrics contain ${alerts_count} alerts"
  exit 2
fi

echo "OK: no outbox alerts"

