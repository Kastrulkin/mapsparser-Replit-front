#!/usr/bin/env bash
set -euo pipefail

cd /opt/seo-app

database_url="$({
  docker inspect seo-app-app-1 --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | sed -n 's/^DATABASE_URL=//p' \
    | head -n 1
} || true)"
postgres_ip="$({
  docker inspect seo-app-postgres-1 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
} || true)"

if [[ -z "${database_url}" || -z "${postgres_ip}" ]]; then
  echo "Cannot resolve the LocalOS PostgreSQL runtime for Telegram owner-bot." >&2
  exit 1
fi

export DATABASE_URL="${database_url/@postgres:5432/@${postgres_ip}:5432}"
export PYTHONPATH="/opt/seo-app/src"

if [[ -z "${TELEGRAM_HTTP_PROXY:-}" ]]; then
  echo "TELEGRAM_HTTP_PROXY is required. On the LocalOS host use http://192.168.0.177:10809." >&2
  exit 1
fi

exec /opt/seo-app/runtime_bot/.venv/bin/python /opt/seo-app/src/telegram_bot.py
