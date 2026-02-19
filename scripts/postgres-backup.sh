#!/usr/bin/env bash
# Создание локального gzip-бэкапа Postgres из docker compose.
# Использование:
#   ./scripts/postgres-backup.sh

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

pg_user="${POSTGRES_USER:-beautybot}"
pg_db="${POSTGRES_DB:-beautybot}"
backup_dir="data/backups/postgres"
mkdir -p "${backup_dir}"

ts="$(date +%Y%m%d_%H%M%S)"
backup_file="${backup_dir}/${pg_db}_${ts}.sql.gz"

echo "Creating backup: ${backup_file}"
docker compose up -d postgres >/dev/null
docker compose exec -T postgres pg_dump -U "${pg_user}" "${pg_db}" | gzip > "${backup_file}"
cp "${backup_file}" "${backup_dir}/latest.sql.gz"
echo "Backup complete: ${backup_file}"
