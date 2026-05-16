# Evidence Bundle: p0-runtime-smoke-sql-placeholders-20260516

## Summary
- Overall status: PASS
- Last updated: 2026-05-16T09:53:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/api/growth_api.py` changed all DB parameter placeholders from `?` to `%s`.
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/lint.txt`
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `src/yandex_sync_service.py` changed all DB parameter placeholders from `?` to `%s`.
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/lint.txt`
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/build.txt`
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/test-unit.txt`
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/test-integration.txt`
- Gaps:
  - `tests/test_yandex_business_connection.py` is not currently runnable as pytest because it declares `business_id` as an unresolved fixture; this was not caused by the change.

### AC4
- Status: PASS
- Proof:
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/live-runtime-smoke-after.txt`
  - `docker compose ps` shows `app`, `worker`, and healthy `postgres`.
  - `curl -I http://localhost:8000` returned `HTTP/1.1 200 OK`.
- Gaps:
  - Local Docker daemon was unavailable, so local container smoke was not possible; live server smoke succeeded.

### AC5
- Status: PASS
- Proof:
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/live-host-placeholder-scan-after.txt`
  - `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/live-container-placeholder-scan-after.txt`
  - Server backup before hotfix: `.agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/live-backup.txt`
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/api/growth_api.py src/yandex_sync_service.py`
- `python3 -m pytest -q tests/test_query_adapter.py`
- `PYTHONPATH=src python3 - <<'PY' ...`
- `rg -n "\?" src/api/growth_api.py src/yandex_sync_service.py`
- `ssh ... 'cd /opt/seo-app && docker compose ps ... && curl -I --max-time 10 http://localhost:8000'`
- `ssh ... 'cd /opt/seo-app && grep -nF "?" src/api/growth_api.py src/yandex_sync_service.py'`
- `scp ... src/api/growth_api.py root@80.78.242.105:/opt/seo-app/src/api/growth_api.py`
- `scp ... src/yandex_sync_service.py root@80.78.242.105:/opt/seo-app/src/yandex_sync_service.py`
- `ssh ... 'cd /opt/seo-app && docker compose restart app worker && docker compose ps'`
- `ssh ... 'cd /opt/seo-app && docker compose exec -T app ... grep ... /app/src/...'`

## Raw artifacts
- .agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/build.txt
- .agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/test-unit.txt
- .agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/test-integration.txt
- .agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/lint.txt
- .agent/tasks/p0-runtime-smoke-sql-placeholders-20260516/raw/screenshot-1.png

## Known gaps
- Local Docker daemon was unavailable: local `docker compose ps/logs` failed with `Cannot connect to the Docker daemon`.
- `tests/test_yandex_business_connection.py` has a pre-existing pytest collection problem: missing `business_id` fixture.
