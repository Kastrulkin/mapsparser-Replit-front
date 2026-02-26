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

echo "[1/4] M2M callbacks metrics"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/callbacks/metrics?tenant_id=${TENANT_ID}&window_minutes=60" >/tmp/openclaw_metrics.json
cat /tmp/openclaw_metrics.json
echo

echo "[2/4] M2M callbacks outbox"
curl -fsS \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  "${base_url}/api/openclaw/callbacks/outbox?tenant_id=${TENANT_ID}&limit=5&offset=0" >/tmp/openclaw_outbox.json
cat /tmp/openclaw_outbox.json
echo

echo "[3/4] M2M dispatch (batch_size=10)"
curl -fsS -X POST \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"batch_size":10}' \
  "${base_url}/api/openclaw/callbacks/dispatch" >/tmp/openclaw_dispatch.json
cat /tmp/openclaw_dispatch.json
echo

echo "[4/4] HTTP health"
curl -fsSI "${base_url}" | head -n 1

echo "OK: OpenClaw M2M outbox smoke passed"

