#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-local}"
SINCE="${SMOKE_SINCE:-15m}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_HOST="${DEPLOY_HOST:-root@80.78.242.105}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
SSH_OPTS=(
  -i "$SSH_KEY"
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=10
)

run_local() {
  cd "$ROOT_DIR"
  echo "[smoke] docker compose ps"
  docker compose ps

  echo
  echo "[smoke] app logs since ${SINCE}"
  docker compose logs --since "$SINCE" app | tail -n "${SMOKE_LOG_LINES:-160}"

  echo
  echo "[smoke] worker logs since ${SINCE}"
  docker compose logs --since "$SINCE" worker | tail -n "${SMOKE_LOG_LINES:-160}"

  echo
  echo "[smoke] curl root"
  curl -I --max-time "${SMOKE_CURL_TIMEOUT:-10}" http://localhost:8000
}

run_server() {
  ssh "${SSH_OPTS[@]}" "$SERVER_HOST" "
    set -euo pipefail
    cd /opt/seo-app
    echo '[smoke] docker compose ps'
    docker compose ps

    echo
    echo '[smoke] app logs since ${SINCE}'
    docker compose logs --since '${SINCE}' app | tail -n '${SMOKE_LOG_LINES:-160}'

    echo
    echo '[smoke] worker logs since ${SINCE}'
    docker compose logs --since '${SINCE}' worker | tail -n '${SMOKE_LOG_LINES:-160}'

    echo
    echo '[smoke] curl root'
    curl -I --max-time '${SMOKE_CURL_TIMEOUT:-10}' http://localhost:8000
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
