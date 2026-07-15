#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and rerun this command." >&2
  exit 1
fi

agent_tests=(tests/test_agent_blueprint_layer.py)
if [[ ! -f "${agent_tests[0]}" ]]; then
  agent_tests=(tests/test_agent_blueprint_*.py)
fi
tests=("${agent_tests[@]}" tests/test_agent_api_security.py tests/test_prospecting_research.py)

docker compose run --rm --no-deps \
  --entrypoint python \
  --volume "${repo_dir}:/app" \
  app -m pytest "${tests[@]}" -q "$@"
