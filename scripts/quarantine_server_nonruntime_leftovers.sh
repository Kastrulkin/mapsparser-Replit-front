#!/usr/bin/env bash
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
SERVER="${SERVER:-root@80.78.242.105}"

ssh -i "$SSH_KEY" \
  -o ConnectTimeout=20 \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=6 \
  "$SERVER" '
    set -euo pipefail
    cd /opt/seo-app

    quarantine_dir="/opt/seo-app/backups/nonruntime-quarantine-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$quarantine_dir"

    tmpfile="$(mktemp)"

    {
      find . -maxdepth 1 -type d -name ".codex_tmp"
      find . -maxdepth 1 -type f -name "tmp_*"
      find . -maxdepth 1 -type f -name "*.tgz"
      find . -maxdepth 1 -type f -name ".env.bak*"
      find . -maxdepth 1 -type f -name "docker-compose.yml.bak.*"
      find . -maxdepth 1 -type f -name "name"
      find . -maxdepth 1 -type d -name "tmp_sync"
      find . -maxdepth 1 -type d -name "tmp_app_versions"
      find . -maxdepth 1 -type d -name "tmp_cardauto_upload"
      find . -maxdepth 1 -type f -name "tmp_*.log"
    } | sed "s#^./##" | sort -u > "$tmpfile"

    count="$(wc -l < "$tmpfile" | tr -d " ")"
    echo "QUARANTINE_DIR=$quarantine_dir"
    echo "CANDIDATE_COUNT=$count"

    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      src_path="/opt/seo-app/$rel"
      dst_path="$quarantine_dir/$rel"
      mkdir -p "$(dirname "$dst_path")"
      mv "$src_path" "$dst_path"
      echo "MOVED $rel"
    done < "$tmpfile"

    rm -f "$tmpfile"

    remaining="$(
      {
        find . -maxdepth 1 -type d -name ".codex_tmp"
        find . -maxdepth 1 -type f -name "tmp_*"
        find . -maxdepth 1 -type f -name "*.tgz"
        find . -maxdepth 1 -type f -name ".env.bak*"
        find . -maxdepth 1 -type f -name "docker-compose.yml.bak.*"
        find . -maxdepth 1 -type f -name "name"
        find . -maxdepth 1 -type d -name "tmp_sync"
        find . -maxdepth 1 -type d -name "tmp_app_versions"
        find . -maxdepth 1 -type d -name "tmp_cardauto_upload"
        find . -maxdepth 1 -type f -name "tmp_*.log"
      } | wc -l | tr -d " "
    )"
    echo "REMAINING_SAFE_NONRUNTIME=$remaining"
  '
