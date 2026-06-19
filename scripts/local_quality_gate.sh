#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "== Python compile =="
python3 -m compileall -q src tests

echo "== Focused pytest subset =="
python3 -m pytest -q \
  tests/test_security_runtime_config.py \
  tests/test_sales_rooms.py \
  tests/test_sales_room_file_storage.py \
  tests/test_content_plan_policy.py

echo "== Python dependency audit =="
if python3 -m pip_audit --version >/dev/null 2>&1; then
  python3 -m pip_audit -r requirements.txt
else
  echo "pip-audit is not installed; run: python3 -m pip install pip-audit"
fi

echo "== Frontend audit =="
npm --prefix frontend audit --omit=dev
npm --prefix frontend audit

echo "== Frontend build =="
npm --prefix frontend run build

echo "== Frontend lint =="
npm --prefix frontend run lint

echo "== Frontend typecheck =="
(
  cd frontend
  npx tsc --noEmit
)
