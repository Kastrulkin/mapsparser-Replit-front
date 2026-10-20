#!/usr/bin/env bash
# Проверенный custom/zstd-бэкап Postgres и ограниченная ротация.
# Использование:
#   ./scripts/postgres-backup.sh

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--preview" ]]; then
  exec python3 scripts/verified_backup_retention.py
fi
exec python3 scripts/verified_backup_retention.py --apply "$@"
