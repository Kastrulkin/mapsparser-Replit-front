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

ACTION="${ACTION:-replay}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
LIMIT="${LIMIT:-200}"

case "${ACTION}" in
  replay)
    INCLUDE_RETRY="${INCLUDE_RETRY:-false}"
    curl -fsS -X POST \
      -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"tenant_id\":\"${TENANT_ID}\",\"include_retry\":${INCLUDE_RETRY},\"limit\":${LIMIT}}" \
      "${BASE_URL}/api/openclaw/callbacks/outbox/replay"
    ;;
  cleanup)
    OLDER_THAN_MINUTES="${OLDER_THAN_MINUTES:-1440}"
    curl -fsS -X POST \
      -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"tenant_id\":\"${TENANT_ID}\",\"older_than_minutes\":${OLDER_THAN_MINUTES},\"limit\":${LIMIT}}" \
      "${BASE_URL}/api/openclaw/callbacks/outbox/cleanup"
    ;;
  *)
    echo "Unsupported ACTION=${ACTION}. Use ACTION=replay or ACTION=cleanup"
    exit 1
    ;;
esac
echo
