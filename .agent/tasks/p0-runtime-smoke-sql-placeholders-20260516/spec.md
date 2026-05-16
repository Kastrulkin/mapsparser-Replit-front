# Task Spec: p0-runtime-smoke-sql-placeholders-20260516

## Metadata
- Task ID: p0-runtime-smoke-sql-placeholders-20260516
- Created: 2026-05-16T09:47:33+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P0 live/runtime smoke plus full replacement of SQLite placeholders in src/api/growth_api.py and src/yandex_sync_service.py. Verify runtime health and keep changes focused.

## Acceptance criteria
- AC1: `src/api/growth_api.py` uses PostgreSQL `%s` placeholders instead of SQLite `?` placeholders.
- AC2: `src/yandex_sync_service.py` uses PostgreSQL `%s` placeholders instead of SQLite `?` placeholders.
- AC3: Local Python checks pass for the touched modules and DB placeholder adapter contract.
- AC4: Live runtime smoke confirms `app`, `worker`, and `postgres` are running and `http://localhost:8000` returns `200 OK`.
- AC5: Live host and app-container copies of the touched files no longer contain SQLite `?` placeholders.

## Constraints
- No production data changes.
- No schema migrations.
- Keep the code change limited to the two target source files.
- Server commands must run from `/opt/seo-app`.

## Non-goals
- No broader `main.py` refactor.
- No frontend changes.
- No Yandex API behavior change beyond SQL parameter placeholder compatibility.

## Verification plan
- Build: `python3 -m py_compile src/api/growth_api.py src/yandex_sync_service.py`
- Unit tests: `python3 -m pytest -q tests/test_query_adapter.py`
- Integration tests: import smoke for `api.growth_api` and `YandexSyncService`
- Lint/static: scan target files for `?`
- Live checks: server `docker compose ps`, `docker compose logs`, `curl -I http://localhost:8000`, and host/container placeholder scans
