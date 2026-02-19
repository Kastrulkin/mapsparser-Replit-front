#!/bin/sh
# Ждём готовности Postgres, применяем миграции, затем запускаем переданную команду.
set -e

POSTGRES_USER="${POSTGRES_USER:-local}"
POSTGRES_DB="${POSTGRES_DB:-local}"

echo "Waiting for Postgres at postgres:5432..."
until pg_isready -h postgres -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  sleep 2
done
echo "Postgres is ready."

echo "Running migrations..."
flask db upgrade
echo "Migrations done."

exec "$@"
