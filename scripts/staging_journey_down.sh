#!/bin/sh
set -eu

staging_project_name="${STAGING_PROJECT_NAME:-localos-staging}"

docker compose \
  -p "$staging_project_name" \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  down

echo "Staging containers stopped. Isolated volumes were preserved."

