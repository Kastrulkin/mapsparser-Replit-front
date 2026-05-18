#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-local}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_HOST="${DEPLOY_HOST:-root@80.78.242.105}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
BASE_URL="${SMOKE_BASE_URL:-http://localhost:8000}"
ALLOWED_ORIGIN="${SMOKE_ALLOWED_ORIGIN:-https://localos.pro}"
BLOCKED_ORIGIN="${SMOKE_BLOCKED_ORIGIN:-https://evil.example}"
SSH_OPTS=(
  -i "$SSH_KEY"
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=10
)

run_cors_smoke() {
  echo "[security] CORS allowed origin: ${ALLOWED_ORIGIN}"
  allowed_headers="$(mktemp)"
  curl -sS -D "$allowed_headers" -o /dev/null -H "Origin: ${ALLOWED_ORIGIN}" "${BASE_URL}/"
  grep -Fi "Access-Control-Allow-Origin: ${ALLOWED_ORIGIN}" "$allowed_headers"

  echo "[security] CORS blocked origin: ${BLOCKED_ORIGIN}"
  blocked_headers="$(mktemp)"
  curl -sS -D "$blocked_headers" -o /dev/null -H "Origin: ${BLOCKED_ORIGIN}" "${BASE_URL}/"
  if grep -Fi "Access-Control-Allow-Origin: ${BLOCKED_ORIGIN}" "$blocked_headers"; then
    echo "Blocked origin was allowed" >&2
    exit 1
  fi
}

run_rate_limit_smoke() {
  echo "[security] rate limit /api/auth/login"
  tmp_body="$(mktemp)"
  got_429=0
  for attempt in 1 2 3 4 5 6; do
    status="$(
      curl -sS -o "$tmp_body" -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -X POST "${BASE_URL}/api/auth/login" \
        --data "{\"email\":\"rate-limit-smoke-${RANDOM}@example.invalid\",\"password\":\"wrong\"}"
    )"
    echo "attempt=${attempt} status=${status}"
    if [[ "$status" == "429" ]]; then
      got_429=1
      grep -F "rate_limited" "$tmp_body" >/dev/null
      break
    fi
  done
  if [[ "$got_429" != "1" ]]; then
    echo "Expected a 429 from /api/auth/login within 6 attempts" >&2
    exit 1
  fi
}

run_secret_presence_smoke() {
  echo "[security] production secret presence"
  docker compose exec -T app python3 - <<'PY'
import os
import sys

secret = os.getenv("EXTERNAL_AUTH_SECRET_KEY", "").strip()
if not secret:
    print("EXTERNAL_AUTH_SECRET_KEY=missing")
    sys.exit(1)
if secret == "dev_secret_key_change_in_production":
    print("EXTERNAL_AUTH_SECRET_KEY=weak_dev_default")
    sys.exit(1)
if len(secret) < 32:
    print("EXTERNAL_AUTH_SECRET_KEY=too_short")
    sys.exit(1)
print("EXTERNAL_AUTH_SECRET_KEY=present")
PY
}

run_local() {
  cd "$ROOT_DIR"
  run_cors_smoke
  run_rate_limit_smoke
  run_secret_presence_smoke
}

run_server() {
  ssh "${SSH_OPTS[@]}" "$SERVER_HOST" "
    set -euo pipefail
    cd /opt/seo-app
    SMOKE_BASE_URL='${BASE_URL}' \
    SMOKE_ALLOWED_ORIGIN='${ALLOWED_ORIGIN}' \
    SMOKE_BLOCKED_ORIGIN='${BLOCKED_ORIGIN}' \
    bash scripts/smoke_security_runtime.sh local
  "
}

case "$MODE" in
  local)
    run_local
    ;;
  server)
    run_server
    ;;
  *)
    echo "Usage: $0 [local|server]" >&2
    exit 2
    ;;
esac
