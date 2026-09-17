#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -z "${PYTHON_BIN:-}" ]; then
  if [ -x "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
  elif [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

python_command=("${PYTHON_BIN}")
if [ "$(uname -s)" = "Darwin" ]; then
  python_command=(/usr/bin/arch -arm64 "${PYTHON_BIN}")
fi

echo "== Python undefined-name gate =="
PYTHON_BIN="${PYTHON_BIN}" bash scripts/ci_gate_python_f821.sh

echo "== Focused backend regressions =="
"${python_command[@]}" -m pytest -q \
  tests/test_reproduced_api_regressions.py \
  tests/test_finance_routes_contract.py \
  tests/test_operator_inbox.py \
  tests/test_telegram_callback_routing.py \
  tests/test_agent_blueprint_compiler.py \
  tests/test_agent_blueprint_api_generic_runs.py

echo "== Python compile =="
"${python_command[@]}" -m compileall -q src tests

echo "== Frontend unit tests =="
npm --prefix frontend run test -- --maxWorkers=2

echo "== Frontend lint =="
npm --prefix frontend run lint

echo "== Frontend typecheck =="
npm --prefix frontend run typecheck

echo "== Frontend production builds =="
npm --prefix frontend run build:all
