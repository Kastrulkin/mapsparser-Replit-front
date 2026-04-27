#!/usr/bin/env bash
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
SERVER_HOST="${SERVER_HOST:-root@80.78.242.105}"
SSH_OPTS=(
  -i "$SSH_KEY"
  -o ConnectTimeout=20
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=6
)

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail
cd /opt/seo-app
quarantine_dir="/opt/seo-app/backups/runtime-quarantine-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$quarantine_dir"

echo "QUARANTINE_DIR=$quarantine_dir"

find_targets() {
  find /opt/seo-app/src /opt/seo-app/alembic_migrations \
    \( -type f -name '* (2).py' -o -type d -name '__pycache__' \) \
    | sort
}

targets=$(find_targets || true)
if [ -z "$targets" ]; then
  echo "NO_TARGETS_FOUND"
  exit 0
fi

echo "TARGETS:"
printf '%s\n' "$targets"

echo
printf '%s\n' "$targets" | while IFS= read -r target; do
  [ -n "$target" ] || continue
  relative_path=${target#/opt/seo-app/}
  destination="$quarantine_dir/$relative_path"
  mkdir -p "$(dirname "$destination")"
  mv "$target" "$destination"
  echo "MOVED $relative_path"
done

echo
echo "REMAINING_DUPLICATES=$(find /opt/seo-app/src /opt/seo-app/alembic_migrations \( -type f -name '* (2).py' -o -type d -name '__pycache__' \) | wc -l | tr -d ' ')"
REMOTE

ssh "${SSH_OPTS[@]}" "$SERVER_HOST" "$REMOTE_SCRIPT"
