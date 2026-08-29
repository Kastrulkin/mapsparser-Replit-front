#!/bin/sh
set -eu

staging_project_name="${STAGING_PROJECT_NAME:-localos-staging}"
staging_port="${STAGING_PORT:-18000}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to start the isolated staging environment." >&2
  exit 1
fi

external_auth_secret_key="$(openssl rand -hex 32)"
outreach_email_secret_key="$(openssl rand -hex 32)"
export EXTERNAL_AUTH_SECRET_KEY="$external_auth_secret_key"
export OUTREACH_EMAIL_SECRET_KEY="$outreach_email_secret_key"
export STAGING_PORT="$staging_port"

if [ "${STAGING_SKIP_BUILD:-false}" = "true" ]; then
  docker compose \
    -p "$staging_project_name" \
    -f docker-compose.yml \
    -f docker-compose.staging.yml \
    up -d --no-build postgres redis app
else
  docker compose \
    -p "$staging_project_name" \
    -f docker-compose.yml \
    -f docker-compose.staging.yml \
    up -d --build postgres redis app
fi

attempt=1
while [ "$attempt" -le 60 ]; do
  if curl --fail --silent "http://127.0.0.1:${staging_port}/" >/dev/null; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 2
done

if [ "$attempt" -gt 60 ]; then
  echo "Staging app did not become ready on port ${staging_port}." >&2
  docker compose -p "$staging_project_name" -f docker-compose.yml -f docker-compose.staging.yml logs --tail=100 app
  exit 1
fi

docker compose \
  -p "$staging_project_name" \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  exec -T app python /app/scripts/seed_journey_staging.py

STAGING_BASE_URL="http://127.0.0.1:${staging_port}" \
  python3 scripts/smoke_journey_staging.py

echo "Isolated LocalOS staging is ready: http://127.0.0.1:${staging_port}"
