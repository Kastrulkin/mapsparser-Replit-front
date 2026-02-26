#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[CI gate] duplicate suffix guard"
./scripts/check_duplicate_suffix_files.sh

echo "[CI gate] py_compile"
python3 -m py_compile src/main.py src/core/action_orchestrator.py src/worker.py

echo "[CI gate] phase1 integration tests"
python3 -m pytest -q tests/test_capabilities_api_phase1.py -ra

echo "[CI gate] OK"
