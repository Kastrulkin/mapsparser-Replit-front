#!/usr/bin/env bash
# Сборка и запуск без BuildKit (стабильно на macOS/Docker Desktop).
# Использование: ./scripts/docker-compose-build.sh up -d --build
# Или: ./scripts/docker-compose-build.sh up -d   (без пересборки)

set -e
cd "$(dirname "$0")/.."
export DOCKER_BUILDKIT=0

# На некоторых окружениях параллельная сборка app/worker через `up --build`
# приводит к нестабильным ошибкам кэша/snapshot в classic builder.
# Для этого сценария делаем детерминированно: build app -> build worker -> up без --build.
if [[ "${1:-}" == "up" ]]; then
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
    echo "Sequential build: app -> worker (to avoid flaky parallel build failures)"
    docker compose build app
    docker compose build worker
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
