#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src_dir="${repo_root}/src"
migrations_dir="${repo_root}/alembic_migrations"
entrypoint_file="${repo_root}/entrypoint.sh"

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
remote_tmp="/tmp/localos_backend_src_deploy"
public_domain="${PUBLIC_DOMAIN:-https://localos.pro}"
restart_services=1
retry_count="${DEPLOY_RETRY_COUNT:-3}"
retry_delay_seconds="${DEPLOY_RETRY_DELAY_SECONDS:-5}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      shift
      server_host="$1"
      server_ssh_prefix=(ssh "${ssh_options[@]}" "${server_host}")
      server_scp_prefix=(scp "${ssh_options[@]}")
      ;;
    --no-restart)
      restart_services=0
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--host user@host] [--no-restart]"
      exit 1
      ;;
  esac
  shift
done

cd "${repo_root}"

python3 -m py_compile "${src_dir}/main.py" "${src_dir}/worker.py"
bash -n "${entrypoint_file}"

if ! "${repo_root}/scripts/check_backend_source_of_truth.sh"; then
  echo "Continuing deploy with untracked runtime files present. Source-of-truth drift still needs cleanup." >&2
fi

local_bundle_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${local_bundle_dir}"
}
trap cleanup EXIT

rsync -a \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='*.db' \
  --exclude='*.db-*' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite-*' \
  --exclude='.DS_Store' \
  "${src_dir}/" "${local_bundle_dir}/src/"

rsync -a \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  "${migrations_dir}/" "${local_bundle_dir}/alembic_migrations/"

cp "${entrypoint_file}" "${local_bundle_dir}/entrypoint.sh"

remote_exec() {
  "${server_ssh_prefix[@]}" "cd ${server_project_dir} && $1"
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

echo "Deploying backend source to ${server_host}:${server_project_dir}"
retry_command "remote temp dir prepare" remote_exec "rm -rf ${remote_tmp} && mkdir -p ${remote_tmp}/src ${remote_tmp}/alembic_migrations"
retry_command "upload src" "${server_scp_prefix[@]}" -r "${local_bundle_dir}/src/." "${server_host}:${remote_tmp}/src/"
retry_command "upload alembic migrations" "${server_scp_prefix[@]}" -r "${local_bundle_dir}/alembic_migrations/." "${server_host}:${remote_tmp}/alembic_migrations/"
retry_command "upload entrypoint" "${server_scp_prefix[@]}" "${local_bundle_dir}/entrypoint.sh" "${server_host}:${remote_tmp}/entrypoint.sh"

retry_command "sync backend source on server" remote_exec "\
  command -v rsync >/dev/null 2>&1 && \
  mkdir -p src alembic_migrations && \
  rsync -a --delete ${remote_tmp}/src/ src/ && \
  rsync -a --delete ${remote_tmp}/alembic_migrations/ alembic_migrations/ && \
  install -m 755 ${remote_tmp}/entrypoint.sh entrypoint.sh"

if [[ "${restart_services}" -eq 1 ]]; then
  echo "Recreating affected services to apply compose/runtime source mounts..."
  retry_command "docker compose up -d --force-recreate app worker" remote_exec "docker compose up -d --force-recreate app worker"
fi

echo "Verification:"
echo "1) docker compose ps"
retry_command "docker compose ps" remote_exec "docker compose ps"
echo "2) docker compose logs --since 10m app"
retry_command "docker compose logs app" remote_exec "docker compose logs --since 10m app | tail -n 120"
echo "3) docker compose logs --since 10m worker"
retry_command "docker compose logs worker" remote_exec "docker compose logs --since 10m worker | tail -n 120"
echo "4) curl -I http://localhost:8000"
retry_command "localhost health check" remote_exec "curl -I http://localhost:8000"
echo "5) targeted runtime source check"
retry_command "runtime source check" remote_exec "docker compose exec -T app sh -lc 'test -f /app/src/core/card_automation.py && python3 -c \"import core.card_automation; print(\\\"APP_CORE_OK\\\")\"'"
retry_command "live html check" remote_exec "curl -s ${public_domain}/ | grep -n \"/assets/index-\" | head -n 1"

echo "Backend source deployed to ${server_project_dir}/src with runtime bind-mount protection."
