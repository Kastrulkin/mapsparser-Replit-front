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
  --entrypoint sh \
  --env GIGACHAT_KEYS= \
  --env GIGACHAT_CLIENT_ID= \
  --env GIGACHAT_CLIENT_SECRET= \
  --env DEEPSEEK_API_KEY= \
  --volume "${repo_dir}:/app" \
  app -lc '
    python -m pip install --disable-pip-version-check -q \
      -r requirements.txt \
      -r requirements.test.txt
    exec python -m pytest "$@"
  ' sh "${tests[@]}" -q "$@"
