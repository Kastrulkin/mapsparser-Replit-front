# Evidence Bundle: p2-admin-business-types-dedupe-20260519

## Summary
- Overall status: PASS
- Last updated: 2026-05-19T06:25:10+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `raw/test-integration.txt` confirms GET/POST/DELETE admin business-type routes are owned by `admin_growth_api`.
  - `raw/live-route-ownership.txt` confirms the same ownership inside the live container after deploy.
- Gaps: none

### AC2
- Status: PASS
- Proof:
  - Added `admin_growth_api.update_business_type` for PUT `/api/admin/business-types/<type_id>`.
  - Focused tests and live route ownership confirm PUT is now owned by `admin_growth_api.update_business_type`.
- Gaps: none

### AC3
- Status: PASS
- Proof:
  - Removed stale admin `business-types` route declarations from `src/main.py`.
  - `raw/lint.txt` and focused tests confirm stale main endpoints are absent.
  - Public `/api/business-types` remains in `src/main.py`.
- Gaps: none

### AC4
- Status: PASS
- Proof:
  - `raw/build.txt` passed.
  - `raw/test-unit.txt` passed: focused pytest reported `14 passed`.
  - `raw/lint.txt` passed.
  - `raw/live-smoke-runtime.txt` confirms app/worker are up and root endpoint returns `200 OK`.
- Gaps: none

## Commands run
- `scripts/lint_backend_baseline.sh`
- `python3 -m py_compile src/main.py src/api/admin_growth_api.py tests/test_growth_workflow_routes.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_growth_workflow_routes.py tests/test_reports_api_routes.py tests/test_security_runtime_config.py tests/test_query_adapter.py`
- `PYTHONPATH=src python3 - <<'PY' ... route ownership ... PY`
- `ssh ... cd /opt/seo-app && backup/sync/restart app worker`
- `SMOKE_SINCE=5m SMOKE_LOG_LINES=120 scripts/smoke_runtime.sh server`

## Raw artifacts
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/build.txt
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/test-unit.txt
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/test-integration.txt
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/lint.txt
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/live-backup.txt
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/live-deploy.txt
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/live-route-ownership.txt
- .agent/tasks/p2-admin-business-types-dedupe-20260519/raw/live-smoke-runtime.txt

## Known gaps
- `api.admin_growth_api` still has older broad exception style in pre-existing handlers; this pass only moved PUT ownership and removed `main.py` duplicates.
