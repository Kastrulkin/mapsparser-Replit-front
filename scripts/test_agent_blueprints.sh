#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

python_bin="${PYTHON_BIN:-venv/bin/python}"
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec arch -arm64 "${python_bin}" -m pytest tests/test_agent_blueprint_layer.py -q
fi

exec "${python_bin}" -m pytest tests/test_agent_blueprint_layer.py -q
