#!/usr/bin/env bash
set -euo pipefail

server_host="${DEPLOY_HOST:-root@80.78.242.105}"
server_project_dir="/opt/seo-app"
ssh_key="${HOME}/.ssh/localos_prod"
ssh_options=(
  -i "${ssh_key}"
  -o ConnectTimeout=15
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=6
)

ssh "${ssh_options[@]}" "${server_host}" "
  git config --global --add safe.directory ${server_project_dir} >/dev/null 2>&1 || true
  cd ${server_project_dir}
  echo SERVER_PWD=\$(pwd)
  echo
  echo '## branch'
  git status --short --branch
  echo
  echo '## heads'
  git rev-parse HEAD
  git rev-parse origin/main
  echo
  echo '## backend source-of-truth'
  bash scripts/check_backend_source_of_truth.sh || true
  echo
  echo '## runtime drift summary'
  echo UNTRACKED=\$(git ls-files --others --exclude-standard -- src/**/*.py alembic_migrations/versions/*.py | wc -l | tr -d ' ')
  echo MODIFIED=\$(git diff --name-only -- src alembic_migrations/versions | wc -l | tr -d ' ')
"
