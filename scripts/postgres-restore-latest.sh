#!/usr/bin/env bash
# Восстановление Postgres из локального .sql.gz бэкапа.
# Использование:
#   ./scripts/postgres-restore-latest.sh
#   ./scripts/postgres-restore-latest.sh data/backups/postgres/beautybot_YYYYmmdd_HHMMSS.sql.gz

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

pg_user="${POSTGRES_USER:-local}"
pg_db="${POSTGRES_DB:-local}"
backup_dir="data/backups/postgres"

if [[ $# -gt 0 ]]; then
  backup_file="$1"
else
  backup_file="$(ls -1t "${backup_dir}"/*.sql.gz 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "${backup_file}" || ! -f "${backup_file}" ]]; then
  echo "Backup file not found. Put a dump into ${backup_dir}."
  exit 1
fi

echo "Starting postgres service..."
docker compose up -d postgres >/dev/null

echo "Restoring from: ${backup_file}"
gunzip -c "${backup_file}" | docker compose exec -T postgres psql -U "${pg_user}" -d "${pg_db}"
echo "Restore complete."
