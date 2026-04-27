#!/usr/bin/env bash
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
SERVER_HOST="${SERVER_HOST:-root@80.78.242.105}"
REMOTE_DIR="/opt/seo-app"
SSH_OPTS=(
  -i "$SSH_KEY"
  -o ConnectTimeout=20
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=6
)

ssh "${SSH_OPTS[@]}" "$SERVER_HOST" '
  set -euo pipefail
  cd /opt/seo-app
  git config --global --add safe.directory /opt/seo-app >/dev/null 2>&1 || true
  backup_dir="/opt/seo-app/backups/git-drift-$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$backup_dir"
  git status --short --branch > "$backup_dir/git-status.txt"
  git rev-parse HEAD > "$backup_dir/head.txt"
  git rev-parse origin/main > "$backup_dir/origin-main.txt"
  git diff > "$backup_dir/git-diff.patch" || true
  git ls-files --others --exclude-standard > "$backup_dir/untracked.txt"
  tar -czf "$backup_dir/runtime-dirty-tree.tgz" \
    --ignore-failed-read \
    src alembic_migrations frontend entrypoint.sh docker-compose.yml README.md docs scripts requirements.txt 2>/dev/null || true
  du -sh "$backup_dir"
  echo BACKUP_DIR="$backup_dir"
  ls -1 "$backup_dir"
'
