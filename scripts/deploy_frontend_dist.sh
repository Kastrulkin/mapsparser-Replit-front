#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_dir="${repo_root}/frontend"
dist_dir="${frontend_dir}/dist"
public_dist_dir="${frontend_dir}/public-dist"

server_host="${DEPLOY_HOST:-root@80.78.242.105}"
ssh_options=(
  -i "${HOME}/.ssh/localos_prod"
  -o ConnectTimeout=15
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=6
)
server_ssh_prefix=(ssh "${ssh_options[@]}" "${server_host}")
server_scp_prefix=(scp "${ssh_options[@]}")
server_project_dir="/opt/seo-app"
app_container_name="${APP_CONTAINER_NAME:-seo-app-app-1}"
public_domain="${PUBLIC_DOMAIN:-https://localos.pro}"
remote_tmp="/tmp/localos_frontend_dist_deploy"

build_dist=0
skip_remote=0
retry_count="${DEPLOY_RETRY_COUNT:-3}"
retry_delay_seconds="${DEPLOY_RETRY_DELAY_SECONDS:-5}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      build_dist=1
      ;;
    --skip-remote)
      skip_remote=1
      ;;
    --host)
      shift
      server_host="$1"
      server_ssh_prefix=(ssh "${ssh_options[@]}" "${server_host}")
      server_scp_prefix=(scp "${ssh_options[@]}")
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--build] [--skip-remote] [--host user@host]"
      exit 1
      ;;
  esac
  shift
done

cd "${repo_root}"

if [[ "${build_dist}" -eq 1 ]]; then
  (
    cd "${frontend_dir}"
    npm run build:all
  )
fi

"${repo_root}/scripts/verify_frontend_dist_integrity.sh" "${dist_dir}"
"${repo_root}/scripts/verify_frontend_dist_integrity.sh" "${public_dist_dir}" "${public_dist_dir}/public-audit/index.html"

if [[ "${skip_remote}" -eq 1 ]]; then
  echo "Local integrity check passed. Remote deploy skipped."
  exit 0
fi

remote_exec() {
  "${server_ssh_prefix[@]}" "cd ${server_project_dir} && $1"
}

remote_ensure_app_running() {
  remote_exec "\
    docker compose up -d app >/dev/null && \
    attempts=0 && \
    until docker compose ps --status running app | grep -q '${app_container_name}'; do \
      attempts=\$((attempts + 1)); \
      if [ \"\$attempts\" -ge 24 ]; then \
        echo 'app service did not reach running state in time' >&2; \
        docker compose ps; \
        exit 1; \
      fi; \
      sleep 5; \
    done"
}

retry_command() {
  local label="$1"
  shift
  local attempt=1
  while true; do
    if "$@"; then
      return 0
    fi
    if [[ "${attempt}" -ge "${retry_count}" ]]; then
      echo "${label} failed after ${attempt} attempts" >&2
      return 1
    fi
    echo "${label} failed on attempt ${attempt}/${retry_count}. Retrying in ${retry_delay_seconds}s..." >&2
    sleep "${retry_delay_seconds}"
    attempt=$((attempt + 1))
  done
}

echo "Deploying frontend dist to ${server_host}:${server_project_dir}"
echo "Keeping previous asset files in place to avoid breaking open tabs that still reference older lazy chunks."

retry_command "remote temp dir prepare" remote_exec "rm -rf ${remote_tmp} ${remote_tmp}-public && mkdir -p ${remote_tmp} ${remote_tmp}-public"
retry_command "upload frontend dist" "${server_scp_prefix[@]}" -r "${dist_dir}/." "${server_host}:${remote_tmp}/"
retry_command "upload public dist" "${server_scp_prefix[@]}" -r "${public_dist_dir}/." "${server_host}:${remote_tmp}-public/"
retry_command "ensure app service is running" remote_ensure_app_running

retry_command "sync frontend dist into server runtime" remote_exec "\
  mkdir -p frontend/dist && \
  mkdir -p frontend/public-dist && \
  cp -R ${remote_tmp}/. frontend/dist/ && \
  cp -R ${remote_tmp}-public/. frontend/public-dist/ && \
  tar -C frontend/dist -cf - . | docker compose exec -T app sh -lc 'mkdir -p /app/frontend/dist && tar -xf - -C /app/frontend/dist' && \
  docker compose exec -T app sh -lc 'mkdir -p /app/dist && cp -R /app/frontend/dist/. /app/dist/' && \
  tar -C frontend/public-dist -cf - . | docker compose exec -T app sh -lc 'mkdir -p /app/frontend/public-dist && tar -xf - -C /app/frontend/public-dist'"

echo "Verification:"
echo "1) docker compose ps"
retry_command "docker compose ps" remote_exec "docker compose ps"
echo "2) docker compose logs --since 10m app"
retry_command "docker compose logs" remote_exec "docker compose logs --since 10m app | tail -n 120"
echo "3) curl -I http://localhost:8000"
retry_command "localhost health check" remote_exec "curl -I http://localhost:8000"
echo "4) targeted frontend checks"
retry_command "runtime index check" remote_exec "docker compose exec -T app sh -lc 'grep -n \"/assets/index-\" /app/frontend/dist/index.html'"
retry_command "public-audit index check" remote_exec "docker compose exec -T app sh -lc 'grep -n \"/public-audit/assets/index-\" /app/frontend/public-dist/public-audit/index.html'"
retry_command "live html check" remote_exec "curl -s ${public_domain}/ | grep -n \"/assets/index-\" | head -n 1"

echo "Frontend dist deployed to ${server_project_dir}/frontend/dist and ${server_project_dir}/frontend/public-dist"
