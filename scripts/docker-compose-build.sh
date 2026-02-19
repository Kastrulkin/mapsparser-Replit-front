#!/usr/bin/env bash
# Сборка и запуск без BuildKit (стабильно на macOS/Docker Desktop).
# Использование: ./scripts/docker-compose-build.sh up -d --build
# Или: ./scripts/docker-compose-build.sh up -d   (без пересборки)

set -e
cd "$(dirname "$0")/.."
export DOCKER_BUILDKIT=0

backup_postgres_if_running() {
  local backup_dir backup_file latest_file ts pg_user pg_db postgres_id
  backup_dir="data/backups/postgres"
  latest_file="${backup_dir}/latest.sql.gz"

  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi

  pg_user="${POSTGRES_USER:-local}"
  pg_db="${POSTGRES_DB:-local}"

  postgres_id="$(docker compose ps -q postgres 2>/dev/null || true)"
  if [[ -z "${postgres_id}" ]]; then
    echo "Postgres container is not running; auto-backup skipped."
    return 0
  fi

  mkdir -p "${backup_dir}"
  ts="$(date +%Y%m%d_%H%M%S)"
  backup_file="${backup_dir}/${pg_db}_${ts}.sql.gz"

  echo "Creating Postgres backup: ${backup_file}"
  if docker compose exec -T postgres pg_dump -U "${pg_user}" "${pg_db}" | gzip > "${backup_file}"; then
    cp "${backup_file}" "${latest_file}"
    echo "Postgres backup complete: ${backup_file}"
  else
    rm -f "${backup_file}"
    echo "WARNING: Postgres backup failed; continue without backup."
  fi
}

cleanup_docker_images() {
  echo "Cleaning dangling Docker images..."
  if docker image prune -f >/dev/null; then
    echo "Dangling images cleaned."
  else
    echo "WARNING: Docker image cleanup failed; continue without cleanup."
  fi
}

# На некоторых окружениях параллельная сборка app/worker через `up --build`
# приводит к нестабильным ошибкам кэша/snapshot в classic builder.
# Для этого сценария делаем детерминированно: build app -> build worker -> up без --build.
if [[ "${1:-}" == "up" ]]; then
  if [[ "${AUTO_DB_BACKUP:-1}" == "1" ]]; then
    backup_postgres_if_running
  fi

  has_build_flag=0
  has_explicit_service=0
  for arg in "$@"; do
    if [[ "$arg" == "--build" ]]; then
      has_build_flag=1
      continue
    fi
    if [[ "$arg" != "up" && "$arg" != "-d" && "$arg" != "--remove-orphans" && "$arg" != "--force-recreate" ]]; then
      if [[ "$arg" != -* ]]; then
        has_explicit_service=1
      fi
    fi
  done

  if [[ $has_build_flag -eq 1 && $has_explicit_service -eq 0 ]]; then
    if [[ "${AUTO_DOCKER_CLEANUP:-1}" == "1" ]]; then
      cleanup_docker_images
    fi

    echo "Sequential build: app -> worker (to avoid flaky parallel build failures)"
    docker compose build app
    docker compose build worker

    if [[ "${AUTO_DOCKER_CLEANUP:-1}" == "1" ]]; then
      cleanup_docker_images
    fi

    filtered_args=()
    for arg in "$@"; do
      if [[ "$arg" != "--build" ]]; then
        filtered_args+=("$arg")
      fi
    done
    exec docker compose "${filtered_args[@]}"
  fi
fi

exec docker compose "$@"
