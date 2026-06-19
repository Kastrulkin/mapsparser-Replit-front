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

echo "== Python compile =="
"${PYTHON_BIN}" -m compileall -q src tests

echo "== Focused pytest subset =="
"${PYTHON_BIN}" -m pytest -q \
  tests/test_security_runtime_config.py \
  tests/test_sales_rooms.py \
  tests/test_sales_room_file_storage.py \
  tests/test_content_plan_policy.py \
  tests/test_approval_boundaries_audit.py \
  tests/test_social_post_service.py \
  tests/test_social_posts_api.py

echo "== Python dependency audit =="
if ! "${PYTHON_BIN}" -m pip_audit --version >/dev/null 2>&1; then
  echo "pip-audit is required; run: python3 -m pip install -r requirements.test.txt"
  exit 1
fi
"${PYTHON_BIN}" -m pip_audit -r requirements.txt -r requirements.test.txt

echo "== Frontend audit =="
npm --prefix frontend audit --omit=dev
npm --prefix frontend audit

echo "== Frontend build =="
npm --prefix frontend run build

echo "== Frontend lint =="
npm --prefix frontend run lint

echo "== Frontend changed-file lint baseline =="
changed_frontend_files="$(
  git diff --name-only --diff-filter=ACMR HEAD -- 'frontend/**/*.ts' 'frontend/**/*.tsx' || true
)"
if [ -n "${changed_frontend_files}" ]; then
  (
    cd frontend
    echo "${changed_frontend_files}" | sed 's#^frontend/##' | xargs npx eslint --max-warnings=0
  )
else
  echo "No changed frontend TS/TSX files."
fi

echo "== Frontend typecheck =="
(
  cd frontend
  npx tsc --noEmit
)
