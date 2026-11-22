#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

# A busy backup lock also means this run has not verified a recovery point.
backup_result="$(python3 scripts/verified_backup_retention.py --apply)"
printf '%s\n' "$backup_result"
backup_status="$(python3 -c 'import json, sys; print(json.load(sys.stdin)["status"])' <<< "$backup_result")"
case "$backup_status" in
  verified) ;;
  already_running) exit 0 ;;
  *) printf 'Unexpected backup status: %s\n' "$backup_status" >&2; exit 1 ;;
esac
bash scripts/compress_sql_backups.sh --apply
python3 scripts/prune_postgres_backups.py --apply
python3 scripts/prune_named_database_backups.py --apply
bash scripts/prune_debug_data.sh --apply
