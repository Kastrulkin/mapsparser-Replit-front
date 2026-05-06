# Evidence Bundle: industry-patterns-impact-stage6-20260506

## Summary
- Overall status: PASS
- Last updated: 2026-05-06T17:12:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/core/industry_pattern_recalibration.py` now has `load_active_industry_patterns` and `format_loaded_active_industry_patterns`.
  - `src/main.py` uses structured active service patterns before `/api/services/optimize` prompt construction.
  - `src/main.py` records `applied` impact events with source `services_optimize`.

### AC2
- Status: PASS
- Proof:
  - `build_pattern_impact_metrics` counts service totals, good, needs_review, fallback, guardrail_failed, pattern_fit, missing_keywords, weak_matches_only, and no_keywords.
  - `/api/services/optimize` records a `result` event after normalization and before saving the optimization result.

### AC3
- Status: PASS
- Proof:
  - `src/telegram_bot.py` adds `Health active-паттернов` in the industry patterns menu.
  - `industry_patterns_health` callback renders usage/result metrics and adds disable buttons through the existing `ip_d:<version_id>` flow.

### AC4
- Status: PASS
- Proof:
  - Production backup created before migration: `/opt/seo-app/backups/industry-patterns-impact-20260506_170948/postgres_before_industry_pattern_impact.sql`.
  - Alembic migration `20260506_002` adds `industry_pattern_impact_events`.
  - Production `flask db current` returned `20260506_002 (head)`.

### AC5
- Status: PASS
- Proof:
  - Local syntax: `python3 -m py_compile src/core/industry_pattern_recalibration.py src/main.py src/telegram_bot.py`.
  - Local targeted tests: `78 passed`.
  - Production syntax AST check: `syntax ok`.
  - Production smoke: `docker compose ps` app/worker up; `curl -I http://localhost:8000` returned `HTTP/1.1 200 OK`; Telegram bot service active; `to_regclass` returned `industry_pattern_impact_events`.
  - Full local pytest result: `247 passed, 66 skipped, 10 failed, 2 errors`; failures are pre-existing integration/env issues: missing localhost server, missing `business_id` fixture, removed parser helper methods.

## Commands run
- `python3 -m py_compile src/core/industry_pattern_recalibration.py src/main.py src/telegram_bot.py`
- `python3 -m pytest -q tests/test_industry_patterns.py`
- `python3 -m pytest -q tests/test_industry_patterns.py tests/test_service_keyword_scoring.py tests/test_beauty_service_optimization.py tests/test_service_problem_regeneration.py tests/test_worker_services_quality.py tests/test_content_plan_generation.py`
- `python3 -m pytest -q`
- Production backup, sync, AST syntax check, `flask db upgrade`, `flask db current`, `docker compose restart app worker`, Telegram bot restart, smoke checks.

## Raw artifacts
- .agent/tasks/industry-patterns-impact-stage6-20260506/raw/build.txt
- .agent/tasks/industry-patterns-impact-stage6-20260506/raw/test-unit.txt
- .agent/tasks/industry-patterns-impact-stage6-20260506/raw/test-integration.txt
- .agent/tasks/industry-patterns-impact-stage6-20260506/raw/lint.txt
- .agent/tasks/industry-patterns-impact-stage6-20260506/raw/screenshot-1.png

## Known gaps
- Full pytest still includes environment/integration tests that require a running local server or obsolete parser helpers; not caused by this change.
- Impact measurement is observational, not true A/B attribution.
