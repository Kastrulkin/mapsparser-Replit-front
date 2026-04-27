#!/usr/bin/env bash
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
SERVER_HOST="${SERVER_HOST:-root@80.78.242.105}"
PARALLEL_ROOT="/opt/seo-app-parallel"
SESSION_NAME="parallel_checkout"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
CHECKOUT_DIR="$PARALLEL_ROOT/origin-main-$TIMESTAMP"
SSH_OPTS=(
  -i "$SSH_KEY"
  -o ConnectTimeout=20
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=6
)

read -r -d '' REMOTE_SCRIPT <<REMOTE || true
set -euo pipefail
cd /opt/seo-app
mkdir -p "$PARALLEL_ROOT"
git config --global --add safe.directory /opt/seo-app >/dev/null 2>&1 || true
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
tmux new-session -d -s "$SESSION_NAME" '
  set -euo pipefail
  git clone --branch main --single-branch https://github.com/Kastrulkin/mapsparser-Replit-front.git "$CHECKOUT_DIR" > /tmp/${SESSION_NAME}.log 2>&1
  printf "CHECKOUT_DIR=%s\n" "$CHECKOUT_DIR" >> /tmp/${SESSION_NAME}.log
'
sleep 2
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "TMUX_SESSION=$SESSION_NAME"
  echo "CHECKOUT_DIR=$CHECKOUT_DIR"
  echo "STATUS=running"
else
  echo "TMUX_SESSION=$SESSION_NAME"
  echo "CHECKOUT_DIR=$CHECKOUT_DIR"
  echo "STATUS=finished"
  cat /tmp/${SESSION_NAME}.log
fi
REMOTE

ssh "${SSH_OPTS[@]}" "$SERVER_HOST" "$REMOTE_SCRIPT"
