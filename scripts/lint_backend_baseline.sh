#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[backend-lint] py_compile focused backend modules"
python3 -m py_compile \
  src/main.py \
  src/api/reports_api.py \
  src/auth_encryption.py \
  tests/test_reports_api_routes.py \
  tests/test_security_runtime_config.py

echo "[backend-lint] import and route smoke"
PYTHONPATH=src python3 - <<'PY'
import main

rules = {
    "/api/download-report/<card_id>": "reports_api.download_report",
    "/api/view-report/<card_id>": "reports_api.view_report",
    "/api/reports/<card_id>/status": "reports_api.report_status",
}

for rule, endpoint in rules.items():
    actual = next((item.endpoint for item in main.app.url_map.iter_rules() if item.rule == rule), None)
    if actual != endpoint:
        raise SystemExit(f"{rule}: expected {endpoint}, got {actual}")

print("OK: report routes are registered through reports_api")
PY

echo "[backend-lint] runtime SQL placeholder scan"
python3 - <<'PY'
import ast
from pathlib import Path

skip_parts = {"migrations", "scripts", "__pycache__"}
skip_prefixes = ("migrate_", "migration_", "debug_", "verify_", "clear_database.py", "add_to_queue.py")
allowed_files = {"src/api/reports_api.py"}
findings = []

for path in sorted(Path("src").rglob("*.py")):
    path_text = str(path)
    if path_text in allowed_files:
        continue
    if any(part in skip_parts for part in path.parts):
        continue
    if path.name.startswith(skip_prefixes):
        continue

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name not in {"execute", "executemany"} or not node.args:
            continue
        arg = node.args[0]
        value = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
        if value and "?" in value:
            first_line = value.strip().splitlines()[0][:120]
            findings.append(f"{path}:{node.lineno}: {first_line}")

if findings:
    print("\n".join(findings))
    raise SystemExit(1)

print("OK: no direct runtime SQLite ? placeholders outside allowed legacy reports blueprint")
PY
