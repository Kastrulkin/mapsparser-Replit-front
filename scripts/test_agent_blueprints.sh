#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

python_bin="${PYTHON_BIN:-venv/bin/python}"
agent_tests=(tests/test_agent_blueprint_layer.py)
if [[ ! -f "${agent_tests[0]}" ]]; then
  agent_tests=(tests/test_agent_blueprint_*.py)
fi
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec arch -arm64 "${python_bin}" -m pytest "${agent_tests[@]}" -q
fi

exec "${python_bin}" -m pytest "${agent_tests[@]}" -q
