#!/bin/sh
# Migration ownership is explicit; check-only startup never attempts DDL.
set -e
mode="${LOCALOS_MIGRATION_MODE:-startup}"
case "$mode" in
  startup|migrate-only|schema-check-only) ;;
  *) echo "Unknown LOCALOS_MIGRATION_MODE" >&2; exit 2 ;;
esac

POSTGRES_USER="${POSTGRES_USER:-local}"
POSTGRES_DB="${POSTGRES_DB:-local}"
echo "Waiting for Postgres..."
until pg_isready -h "${POSTGRES_HOST:-postgres}" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  sleep 2
done

case "$mode" in
  schema-check-only) python3 scripts/localos_migrator.py check ;;
  startup|migrate-only) python3 scripts/localos_migrator.py upgrade ;;
esac
if [ "$mode" = "migrate-only" ]; then
  exit 0
fi
exec "$@"
