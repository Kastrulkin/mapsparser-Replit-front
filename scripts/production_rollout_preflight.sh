#!/usr/bin/env bash
set -euo pipefail

# Read-only production inventory. This script intentionally does not print
# environment variables, mutate ownership, restart services or create backups.
cd /opt/seo-app

localos_precheck_origin="${LOCALOS_PRECHECK_ORIGIN:-http://localhost:8000}"

echo "LocalOS production rollout preflight"
date -u '+UTC %Y-%m-%dT%H:%M:%SZ'
echo "workdir=$(pwd)"
echo "git_head=$(git rev-parse HEAD 2>/dev/null || echo unavailable)"
echo "compose_sha256=$(docker compose config | sha256sum | awk '{print $1}')"

docker compose ps
docker compose images
docker compose exec -T postgres pg_isready

for localos_service in app worker telegram-bot; do
  localos_container_id="$(docker compose ps -q "$localos_service" 2>/dev/null || true)"
  if [[ -z "$localos_container_id" ]]; then
    echo "service=$localos_service container=missing"
    continue
  fi
  echo "service=$localos_service container=$localos_container_id"
  docker inspect --format 'image={{.Image}} configured_user={{json .Config.User}}' "$localos_container_id"
  docker inspect --format '{{range .Mounts}}{{println "mount" .Source "->" .Destination "rw=" .RW}}{{end}}' "$localos_container_id"
  docker exec "$localos_container_id" id
done

for localos_runtime_path in uploads debug_data; do
  if [[ -e "/opt/seo-app/$localos_runtime_path" ]]; then
    stat -c 'path=%n uid=%u gid=%g mode=%a' "/opt/seo-app/$localos_runtime_path"
  else
    echo "path=/opt/seo-app/$localos_runtime_path status=missing"
  fi
done

df -h / /opt/seo-app
curl --fail --silent --show-error --head "$localos_precheck_origin"

echo "PREFLIGHT_READ_ONLY_OK"
