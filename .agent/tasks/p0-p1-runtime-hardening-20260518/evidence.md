# Evidence Bundle: p0-p1-runtime-hardening-20260518

## Summary
- Overall status: PASS
- Last updated: 2026-05-18T09:16:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/main.py` runtime `DatabaseManager` SQL placeholders changed from `?` to `%s`.
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/lint.txt`
- Gaps:
  - Three legacy report reads in `src/main.py` intentionally still use `?` through `safe_db_utils`/SQLite for old generated reports.

### AC2
- Status: PASS
- Proof:
  - `tests/test_yandex_business_connection.py` now exposes `run_business_connection_check`.
  - Pytest wrapper uses `YANDEX_TEST_BUSINESS_ID` and skips when unset instead of requiring a nonexistent fixture.
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/test-unit.txt`
- Gaps:
  - Live Yandex account check was not run because no `YANDEX_TEST_BUSINESS_ID` was provided.

### AC3
- Status: PASS
- Proof:
  - `scripts/smoke_runtime.sh` added.
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/live-smoke-runtime-script.txt`
- Gaps:
  - Local Docker daemon is unavailable in this workstation session, so local mode cannot complete here.

### AC4
- Status: PASS
- Proof:
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/build.txt`
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/test-unit.txt`
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/test-integration.txt`
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/live-backup.txt`
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/live-restart.txt`
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/live-smoke-runtime-script.txt`
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/live-main-placeholder-scan.txt`
  - `.agent/tasks/p0-p1-runtime-hardening-20260518/raw/live-container-main-placeholder-scan.txt`
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/main.py tests/test_yandex_business_connection.py`
- `bash -n scripts/smoke_runtime.sh`
- `python3 -m pytest -q tests/test_query_adapter.py tests/test_yandex_business_connection.py`
- `PYTHONPATH=src python3 - <<'PY' ...`
- AST runtime placeholder scan over `src/`
- `scripts/smoke_runtime.sh local`
- `scp src/main.py root@80.78.242.105:/opt/seo-app/src/main.py`
- `scp scripts/smoke_runtime.sh root@80.78.242.105:/opt/seo-app/scripts/smoke_runtime.sh`
- `ssh ... 'cd /opt/seo-app && docker compose restart app worker && docker compose ps'`
- `scripts/smoke_runtime.sh server`
- live host and app-container AST scans for `src/main.py`

## Raw artifacts
- .agent/tasks/p0-p1-runtime-hardening-20260518/raw/build.txt
- .agent/tasks/p0-p1-runtime-hardening-20260518/raw/test-unit.txt
- .agent/tasks/p0-p1-runtime-hardening-20260518/raw/test-integration.txt
- .agent/tasks/p0-p1-runtime-hardening-20260518/raw/lint.txt
- .agent/tasks/p0-p1-runtime-hardening-20260518/raw/screenshot-1.png

## Known gaps
- Local Docker daemon is unavailable: local runtime smoke fails before app checks.
- `YANDEX_TEST_BUSINESS_ID` was not provided, so the live Yandex external smoke is intentionally skipped.
