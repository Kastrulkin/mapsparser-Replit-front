#!/usr/bin/env bash
set -euo pipefail

cd /opt/seo-app 2>/dev/null || true

BASE_URL="${BASE_URL:-http://localhost:8000}"
AUTH_TOKEN="${AUTH_TOKEN:-}"
BUSINESS_ID="${BUSINESS_ID:-}"
MAP_URL="${MAP_URL:-}"
REPORT_PATH="${REPORT_PATH:-/tmp/partnership_smoke_$(date +%s).json}"
MARKDOWN_REPORT_PATH="${MARKDOWN_REPORT_PATH:-${REPORT_PATH%.json}.md}"
SMOKE_TIMEOUT_SEC="${SMOKE_TIMEOUT_SEC:-90}"

if [[ -z "$AUTH_TOKEN" || -z "$BUSINESS_ID" || -z "$MAP_URL" ]]; then
  cat <<'USAGE'
Usage:
  AUTH_TOKEN="<jwt>" \
  BUSINESS_ID="<uuid>" \
  MAP_URL="https://yandex.ru/maps/org/1221240931/" \
  ./scripts/smoke_partnership_flow.sh
Optional:
  BASE_URL=http://localhost:8000
  REPORT_PATH=/tmp/partnership_smoke.json
  MARKDOWN_REPORT_PATH=/tmp/partnership_smoke.md
  SMOKE_TIMEOUT_SEC=90
USAGE
  exit 2
fi

python3 scripts/smoke_partnership_flow.py \
  --base-url "$BASE_URL" \
  --token "$AUTH_TOKEN" \
  --business-id "$BUSINESS_ID" \
  --map-url "$MAP_URL" \
  --report "$REPORT_PATH" \
  --markdown-report "$MARKDOWN_REPORT_PATH" \
  --timeout "$SMOKE_TIMEOUT_SEC"

echo "[smoke] report saved to: $REPORT_PATH"
echo "[smoke] markdown report saved to: $MARKDOWN_REPORT_PATH"
