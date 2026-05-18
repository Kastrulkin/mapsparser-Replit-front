# Evidence Bundle: p2-growth-route-dedupe-20260518

## Summary
- Overall status: PASS
- Last updated: 2026-05-18T20:05:15+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Removed stale `get_business_stages`, `get_growth_stages`, `create_growth_stage`, and `update_or_delete_growth_stage` route handlers from `src/main.py`.
- Gaps: none

### AC2
- Status: PASS
- Proof:
  - `raw/test-integration.txt` confirms `/api/business/<string:business_id>/stages` is still served first by `growth_api.get_business_stages`.
  - `raw/test-integration.txt` confirms admin growth-stages routes are served by `admin_growth_api`.
  - `raw/live-route-ownership.txt` confirms the same ownership inside the live container after deploy.
- Gaps: none

### AC3
- Status: PASS
- Proof:
  - `tests/test_growth_workflow_routes.py` now checks growth stage route ownership and absence of stale main endpoints.
  - `scripts/lint_backend_baseline.sh` now checks these route ownership rules and duplicate cleanup.
  - `raw/lint.txt` passed.
- Gaps: none

### AC4
- Status: PASS
- Proof:
  - `raw/build.txt` passed.
  - `raw/test-unit.txt` passed: focused pytest reported `13 passed`.
  - `raw/live-smoke-runtime.txt` confirms app/worker are up and root endpoint returns `200 OK`.
- Gaps: none

## Commands run
- `scripts/lint_backend_baseline.sh`
- `python3 -m py_compile src/main.py tests/test_growth_workflow_routes.py`
- `PYTHONPATH=src python3 -m pytest -q tests/test_growth_workflow_routes.py tests/test_reports_api_routes.py tests/test_security_runtime_config.py tests/test_query_adapter.py`
- `PYTHONPATH=src python3 - <<'PY' ... route ownership ... PY`
- `ssh ... cd /opt/seo-app && backup/sync/restart app worker`
- `SMOKE_SINCE=5m SMOKE_LOG_LINES=120 scripts/smoke_runtime.sh server`

## Raw artifacts
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/build.txt
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/test-unit.txt
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/test-integration.txt
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/lint.txt
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/live-backup.txt
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/live-deploy.txt
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/live-route-ownership.txt
- .agent/tasks/p2-growth-route-dedupe-20260518/raw/live-smoke-runtime.txt

## Known gaps
- `api.growth_api` and `api.admin_growth_api` still contain older implementation style; this pass only removed duplicate `main.py` handlers while preserving runtime behavior.
