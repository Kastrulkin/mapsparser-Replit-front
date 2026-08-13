#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"
python_bin="${PYTHON_BIN:-venv/bin/python}"
test_args=(tests/test_agent_blueprint_compiler.py -q -k "compiled or validation or approval")
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec env PYTHONPATH=src arch -arm64 "${python_bin}" -m pytest "${test_args[@]}"
fi
exec env PYTHONPATH=src "${python_bin}" -m pytest "${test_args[@]}"
