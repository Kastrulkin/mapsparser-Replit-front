#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[backend-lint] py_compile focused backend modules"
python3 -m py_compile \
  src/main.py \
  src/api/reports_api.py \
  src/api/growth_workflow_api.py \
  src/auth_encryption.py \
  tests/test_reports_api_routes.py \
  tests/test_growth_workflow_routes.py \
  tests/test_security_runtime_config.py

echo "[backend-lint] import and route ownership smoke"
PYTHONPATH=src python3 - <<'PY'
import main
import api.growth_workflow_api
import api.reports_api

rules = {
    "/api/download-report/<card_id>": "reports_api.download_report",
    "/api/view-report/<card_id>": "reports_api.view_report",
    "/api/reports/<card_id>/status": "reports_api.report_status",
    "/api/progress": "growth_workflow_api.get_business_progress",
    "/api/business/<business_id>/optimization-wizard": "growth_workflow_api.business_optimization_wizard",
    "/api/business/<business_id>/sprint": "growth_workflow_api.business_sprint",
    "/api/business/<string:business_id>/stages": "growth_api.get_business_stages",
    "/api/admin/growth-stages/<type_id>": "admin_growth_api.get_growth_stages",
    "/api/admin/growth-stages": "admin_growth_api.create_growth_stage",
}

for rule, endpoint in rules.items():
    actual = next((item.endpoint for item in main.app.url_map.iter_rules() if item.rule == rule), None)
    if actual != endpoint:
        raise SystemExit(f"{rule}: expected {endpoint}, got {actual}")

print("OK: extracted routes are registered through their API blueprints")
PY

echo "[backend-lint] extracted growth routes stay out of main.py"
python3 - <<'PY'
from pathlib import Path

main_text = Path("src/main.py").read_text(encoding="utf-8")
for marker in (
    "/api/progress",
    "/api/business/<business_id>/optimization-wizard",
    "/api/business/<business_id>/sprint",
    "/api/business/<string:business_id>/stages",
    "/api/admin/growth-stages/<business_type_id>",
    "/api/admin/growth-stages",
    "/api/admin/growth-stages/<stage_id>",
):
    if marker in main_text:
        raise SystemExit(f"route still owned by main.py: {marker}")

print("OK: extracted growth routes are not declared in main.py")
PY

echo "[backend-lint] growth stage duplicate route smoke"
PYTHONPATH=src python3 - <<'PY'
import main

route_methods = {}
for rule in main.app.url_map.iter_rules():
    methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
    route_methods[(rule.rule, methods)] = rule.endpoint

expected_methods = {
    ("/api/admin/growth-stages/<stage_id>", frozenset({"PUT"})): "admin_growth_api.update_growth_stage",
    ("/api/admin/growth-stages/<stage_id>", frozenset({"DELETE"})): "admin_growth_api.delete_growth_stage",
}

for key, endpoint in expected_methods.items():
    actual = route_methods.get(key)
    if actual != endpoint:
        raise SystemExit(f"{key}: expected {endpoint}, got {actual}")

stale_main_endpoints = {
    "get_business_stages",
    "get_growth_stages",
    "create_growth_stage",
    "update_or_delete_growth_stage",
}
actual_endpoints = {rule.endpoint for rule in main.app.url_map.iter_rules()}
stale = stale_main_endpoints.intersection(actual_endpoints)
if stale:
    raise SystemExit(f"stale main.py growth endpoints still registered: {sorted(stale)}")

print("OK: growth stage routes have no stale main.py duplicates")
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

echo "[backend-lint] growth workflow SQL placeholder scan"
python3 - <<'PY'
import ast
from pathlib import Path

path = Path("src/api/growth_workflow_api.py")
tree = ast.parse(path.read_text(encoding="utf-8"))
findings = []

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

print("OK: growth workflow blueprint uses PostgreSQL placeholders")
PY
