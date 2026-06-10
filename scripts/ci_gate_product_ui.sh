#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[product-ui] agents first-layer copy guard"
python3 scripts/check_agents_product_ui_copy.py

echo "[product-ui] python guard syntax"
python3 -m py_compile scripts/check_agents_product_ui_copy.py
python3 -m py_compile scripts/smoke_agents_product_ui_mock.py

if curl -fsS --max-time 2 http://127.0.0.1:3000/dashboard/agents >/dev/null 2>&1; then
  echo "[product-ui] agents mocked cockpit render"
  python3 scripts/smoke_agents_product_ui_mock.py
else
  echo "[product-ui] skip mocked cockpit render: local frontend is not running on 127.0.0.1:3000"
fi

echo "[product-ui] OK"
