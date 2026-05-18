# Evidence Bundle: p2-growth-blueprint-20260518

## Summary
- Overall status: PASS
- Last updated: 2026-05-18T19:56:30+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/api/growth_workflow_api.py` with `/api/progress`, `/api/business/<business_id>/optimization-wizard`, and `/api/business/<business_id>/sprint`.
  - Removed those route declarations from `src/main.py`; `main.py` only imports/registers `growth_workflow_bp`.
  - `raw/test-integration.txt` confirms endpoint ownership.
- Gaps: none

### AC2
- Status: PASS
- Proof:
  - Left duplicate-priority-sensitive `/api/business/<string:business_id>/stages` and `/api/admin/growth-stages...` handlers in their current modules for a later dedicated pass.
- Gaps: none

### AC3
- Status: PASS
- Proof:
  - `scripts/lint_backend_baseline.sh` now py-compiles and imports `src/api/growth_workflow_api.py`.
  - The lint baseline checks route ownership, absence of moved route declarations in `src/main.py`, and PostgreSQL placeholder usage in the new blueprint.
  - `raw/lint.txt` passed.
- Gaps: none

### AC4
- Status: PASS
- Proof:
  - `raw/build.txt` passed.
  - `raw/test-unit.txt` passed: focused pytest suite reported `12 passed`.
  - `raw/live-route-ownership.txt` confirms live container route ownership.
  - `raw/live-smoke-runtime.txt` confirms Docker services up and root endpoint returns `200 OK`.
- Gaps: server-host lint script cannot run as-is because tests are not deployed on the host; local lint and live route/runtime smoke are the acceptance artifacts.

## Commands run
- `scripts/lint_backend_baseline.sh`
- `python3 -m py_compile src/main.py src/api/growth_workflow_api.py tests/test_growth_workflow_routes.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_growth_workflow_routes.py tests/test_reports_api_routes.py tests/test_security_runtime_config.py tests/test_query_adapter.py`
- `PYTHONPATH=src python3 - <<'PY' ... route ownership ... PY`
- `ssh ... cd /opt/seo-app && backup/sync/restart app worker`
- `SMOKE_SINCE=5m SMOKE_LOG_LINES=120 scripts/smoke_runtime.sh server`

## Raw artifacts
- .agent/tasks/p2-growth-blueprint-20260518/raw/build.txt
- .agent/tasks/p2-growth-blueprint-20260518/raw/test-unit.txt
- .agent/tasks/p2-growth-blueprint-20260518/raw/test-integration.txt
- .agent/tasks/p2-growth-blueprint-20260518/raw/lint.txt
- .agent/tasks/p2-growth-blueprint-20260518/raw/live-backup.txt
- .agent/tasks/p2-growth-blueprint-20260518/raw/live-deploy.txt
- .agent/tasks/p2-growth-blueprint-20260518/raw/live-route-ownership.txt
- .agent/tasks/p2-growth-blueprint-20260518/raw/live-smoke-runtime.txt

## Known gaps
- `business/stages` and `admin/growth-stages` still have duplicate/overlapping route ownership and should be handled in a separate priority-order-preserving pass.
