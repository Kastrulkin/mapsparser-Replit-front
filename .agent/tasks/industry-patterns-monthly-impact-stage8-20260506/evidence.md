# Evidence Bundle: industry-patterns-monthly-impact-stage8-20260506

## Summary
- Overall status: PASS
- Last updated: 2026-05-06T17:36:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `build_monthly_industry_pattern_impact_report` aggregates active pattern impact from `industry_pattern_impact_events`.

### AC2
- Status: PASS
- Proof:
  - `format_monthly_industry_pattern_impact_report` shows totals and causes: fallback, guardrails, missing keys, drift, facts risk, too long, no detail.

### AC3
- Status: PASS
- Proof:
  - `classify_industry_pattern_impact_item` marks active patterns as `disable_candidate`, `revise_candidate`, `stable`, `watch`, or `no_data`.

### AC4
- Status: PASS
- Proof:
  - Telegram command `/industry_patterns_impact` added.
  - Industry patterns menu now has `Impact report` button.

### AC5
- Status: PASS
- Proof:
  - `card_automation` superadmin digest now includes `_superadmin_monthly_impact_block` on day 1.

### AC6
- Status: PASS
- Proof:
  - Impact report buttons can call existing disable flow.
  - New active-pattern revision flow creates a needs_revision proposal from an active version via `mark_industry_pattern_version_for_revision`.

### AC7
- Status: PASS
- Proof:
  - Local syntax passed.
  - Local tests: `82 passed`.
  - Production AST syntax: `syntax ok`.
  - Production smoke: app/worker up, Telegram bot active, `HTTP/1.1 200 OK`, logs without tracebacks.

## Commands run
- `python3 -m py_compile src/core/industry_pattern_recalibration.py src/core/card_automation.py src/telegram_bot.py`
- `python3 -m pytest -q tests/test_industry_patterns.py tests/test_content_plan_generation.py tests/test_worker_services_quality.py`
- `python3 -m pytest -q tests/test_industry_patterns.py tests/test_service_keyword_scoring.py tests/test_beauty_service_optimization.py tests/test_service_problem_regeneration.py tests/test_worker_services_quality.py tests/test_content_plan_generation.py`
- Production sync, AST syntax check, restart app/worker, restart Telegram bot, HTTP/log smoke checks.

## Raw artifacts
- .agent/tasks/industry-patterns-monthly-impact-stage8-20260506/raw/build.txt
- .agent/tasks/industry-patterns-monthly-impact-stage8-20260506/raw/test-unit.txt
- .agent/tasks/industry-patterns-monthly-impact-stage8-20260506/raw/test-integration.txt
- .agent/tasks/industry-patterns-monthly-impact-stage8-20260506/raw/lint.txt
- .agent/tasks/industry-patterns-monthly-impact-stage8-20260506/raw/screenshot-1.png

## Known gaps
- Report is observational, not A/B attribution.
- Detailed per-pattern history screen remains next stage.
