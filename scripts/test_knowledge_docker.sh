#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and rerun this command." >&2
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm --no-deps \
  --entrypoint sh \
  --volume "${repo_dir}:/app" \
  app -lc 'python -m pip install --quiet -r requirements.test.txt && python -m pytest tests/test_knowledge_layer.py -q "$@"' sh "$@"
