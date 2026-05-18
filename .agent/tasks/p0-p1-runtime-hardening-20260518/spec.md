# Task Spec: p0-p1-runtime-hardening-20260518

## Metadata
- Task ID: p0-p1-runtime-hardening-20260518
- Created: 2026-05-18T09:10:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
P0/P1 autonomous hardening: scan and fix remaining PostgreSQL/SQLite runtime incompatibilities in src, repair runnable Yandex smoke/test gap, add reusable live runtime smoke script, and verify with proof-loop.

## Acceptance criteria
- AC1: Remaining direct runtime SQL calls in `src/` do not use SQLite `?` placeholders, excluding explicitly legacy SQLite report reads through `safe_db_utils`.
- AC2: The Yandex Business connection check no longer breaks pytest collection and remains available as an explicit live smoke.
- AC3: A reusable runtime smoke script exists for local and server checks.
- AC4: Local build/import/unit checks pass.
- AC5: Live server receives the backend fix, `app`/`worker` restart cleanly, HTTP root returns `200 OK`, and live host/container scans confirm the fixed `main.py`.

## Constraints
- Do not change production data.
- Do not run schema migrations manually.
- Keep runtime SQL changes behavior-preserving: placeholder conversion only.
- Server commands must start from `/opt/seo-app`.

## Non-goals
- Do not refactor `main.py` into blueprints in this pass.
- Do not remove legacy SQLite report routes that intentionally use `safe_db_utils`.
- Do not run Yandex live network checks without an explicit `YANDEX_TEST_BUSINESS_ID`.

## Verification plan
- Build: `python3 -m py_compile src/main.py tests/test_yandex_business_connection.py` and `bash -n scripts/smoke_runtime.sh`.
- Unit tests: `python3 -m pytest -q tests/test_query_adapter.py tests/test_yandex_business_connection.py`.
- Integration tests: import `main`, `YandexSyncService`, and `growth_bp`.
- Lint/static: AST scan for direct `execute`/`executemany` SQL strings containing `?`.
- Manual/live checks: `scripts/smoke_runtime.sh server`, live host scan, live app-container scan.
