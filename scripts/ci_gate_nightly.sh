#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

: "${LOCALOS_TEST_DATABASE_URL:?Set LOCALOS_TEST_DATABASE_URL to an isolated PostgreSQL database}"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-${LOCALOS_TEST_DATABASE_URL}}"

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

echo "== Full backend suite with isolated PostgreSQL =="
DATABASE_URL="${LOCALOS_TEST_DATABASE_URL}" "${python_command[@]}" -m pytest -q --durations=30

echo "== Frontend unit tests =="
npm --prefix frontend run test -- --maxWorkers=2

echo "== Frontend lint =="
npm --prefix frontend run lint

echo "== Frontend typecheck =="
npm --prefix frontend run typecheck

echo "== Frontend production builds =="
npm --prefix frontend run build:all

echo "== Local mocked browser scenarios =="
(
  cd frontend
  npx playwright test e2e/*.spec.ts
)
