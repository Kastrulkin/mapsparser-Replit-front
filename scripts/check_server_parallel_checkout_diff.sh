#!/usr/bin/env bash
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
SERVER_HOST="${SERVER_HOST:-root@80.78.242.105}"
PARALLEL_ROOT="/opt/seo-app-parallel"
SSH_OPTS=(
  -i "$SSH_KEY"
  -o ConnectTimeout=20
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=6
)

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail
cd /opt/seo-app
latest_checkout=$(find /opt/seo-app-parallel -maxdepth 1 -mindepth 1 -type d -name 'origin-main-*' | sort | tail -n 1)
if [ -z "$latest_checkout" ]; then
  echo "ERROR: no parallel checkout found in /opt/seo-app-parallel" >&2
  exit 1
fi

echo "LATEST_CHECKOUT=$latest_checkout"
backend_diff=$(diff -qr /opt/seo-app/src "$latest_checkout/src" || true)
migrations_diff=$(diff -qr /opt/seo-app/alembic_migrations "$latest_checkout/alembic_migrations" || true)
root_diff=$(diff -q /opt/seo-app/docker-compose.yml "$latest_checkout/docker-compose.yml" || true)

echo
echo "## diff summary"
echo "SRC_DIFF_LINES=$(printf '%s\n' "$backend_diff" | sed '/^$/d' | wc -l | tr -d ' ')"
echo "MIGRATION_DIFF_LINES=$(printf '%s\n' "$migrations_diff" | sed '/^$/d' | wc -l | tr -d ' ')"
echo "ROOT_DOCKER_COMPOSE_DIFF=$(printf '%s\n' "$root_diff" | sed '/^$/d' | wc -l | tr -d ' ')"

echo
echo "## sample backend diff"
printf '%s\n' "$backend_diff" | sed -n '1,40p'

echo
echo "## sample migration diff"
printf '%s\n' "$migrations_diff" | sed -n '1,40p'
REMOTE

ssh "${SSH_OPTS[@]}" "$SERVER_HOST" "$REMOTE_SCRIPT"
