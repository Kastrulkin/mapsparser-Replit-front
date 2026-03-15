#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[CI gate partnership] duplicate suffix guard"
./scripts/check_duplicate_suffix_files.sh

echo "[CI gate partnership] py_compile"
python3 -m py_compile src/api/admin_prospecting.py scripts/smoke_partnership_flow.py

echo "[CI gate partnership] smoke script syntax"
bash -n scripts/smoke_partnership_flow.sh

STRICT="${PARTNERSHIP_CI_STRICT:-1}"

if [[ -n "${CI:-}" && "${STRICT}" == "1" ]]; then
  echo "[CI gate partnership] CI strict mode: partnership smoke is mandatory"
  : "${AUTH_TOKEN:?AUTH_TOKEN is required in strict CI mode}"
  : "${BUSINESS_ID:?BUSINESS_ID is required in strict CI mode}"
  : "${MAP_URL:?MAP_URL is required in strict CI mode}"
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
  AUTH_TOKEN="${AUTH_TOKEN}" \
  BUSINESS_ID="${BUSINESS_ID}" \
  MAP_URL="${MAP_URL}" \
  ./scripts/smoke_partnership_flow.sh
elif [[ -n "${AUTH_TOKEN:-}" && -n "${BUSINESS_ID:-}" && -n "${MAP_URL:-}" ]]; then
  echo "[CI gate partnership] local mode: running optional partnership smoke"
  BASE_URL="${BASE_URL:-http://localhost:8000}" \
  AUTH_TOKEN="${AUTH_TOKEN}" \
  BUSINESS_ID="${BUSINESS_ID}" \
  MAP_URL="${MAP_URL}" \
  ./scripts/smoke_partnership_flow.sh
else
  echo "[CI gate partnership] local mode: AUTH_TOKEN/BUSINESS_ID/MAP_URL not set, skipping smoke"
fi

echo "[CI gate partnership] OK"
