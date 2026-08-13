#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

python_bin="${PYTHON_BIN:-venv/bin/python}"
tests=(
  tests/test_agent_template_catalog_contract.py
  tests/test_agent_blueprint_compiler.py::test_use_agent_template_is_idempotent_for_business_and_template_version
  tests/test_agent_blueprint_compiler.py::test_draft_template_cannot_be_used_in_self_service
)
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec env PYTHONPATH=src arch -arm64 "${python_bin}" -m pytest "${tests[@]}" -q
fi
exec env PYTHONPATH=src "${python_bin}" -m pytest "${tests[@]}" -q
