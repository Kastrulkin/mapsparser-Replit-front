#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

# Route-registration tests import the Flask application but never access its
# database. Keep that import reproducible in a clean shell while preserving an
# explicitly supplied PostgreSQL test URL.
export FLASK_ENV="${FLASK_ENV:-testing}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///:memory:}"

python_bin="${PYTHON_BIN:-venv/bin/python}"
agent_tests=(tests/test_agent_blueprint_layer.py)
if [[ ! -f "${agent_tests[0]}" ]]; then
  agent_tests=(tests/test_agent_blueprint_*.py)
fi
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec arch -arm64 "${python_bin}" -m pytest "${agent_tests[@]}" -q
fi

exec "${python_bin}" -m pytest "${agent_tests[@]}" -q
