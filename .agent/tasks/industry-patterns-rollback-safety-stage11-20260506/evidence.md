# Evidence Bundle: industry-patterns-rollback-safety-stage11-20260506

## Summary
- Overall status: PASS
- Last updated: 2026-05-06T18:05:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Rollback candidate buttons now use `ip_rpc:<version_id>` and open preview instead of executing rollback.
  - Old `ip_rb:<version_id>` callback is retained as a preview alias for messages already sent before deploy.
- Gaps:
  - None

### AC2
- Status: PASS
- Proof:
  - Added `get_industry_pattern_rollback_preview` in `src/core/industry_pattern_recalibration.py`.
  - Added `_build_industry_pattern_rollback_preview_text` in `src/telegram_bot.py`.
- Gaps:
  - None

### AC3
- Status: PASS
- Proof:
  - Preview includes current/target version text, status, impact counters, bad rate, length delta, similarity, added/removed terms, selected reason, and warnings.
  - Disabled target versions are shown with a warning instead of being hidden.
- Gaps:
  - None

### AC4
- Status: PASS
- Proof:
  - Added rollback reason buttons via `ip_rbr:<target_version_id>:<reason>`.
  - Actual DB rollback only runs on `ip_rbc:<target_version_id>`.
- Gaps:
  - None

### AC5
- Status: PASS
- Proof:
  - Confirmation compares target with the last preview stored in `user_states`.
  - Confirmation re-runs `get_industry_pattern_rollback_preview` and blocks if `can_confirm` is false.
  - Preview requires same industry/type, current active context, and different current/target IDs.
- Gaps:
  - None

### AC6
- Status: PASS
- Proof:
  - `rollback_industry_pattern_version` still inserts `rollback_activate` into `industry_pattern_decisions`.
  - It now also writes `admin_rollback` into `industry_pattern_impact_events` with reason, current version, target version, and disabled versions.
- Gaps:
  - None

### AC7
- Status: PASS
- Proof:
  - `ip_rb:<version_id>` is supported as a preview alias, so old Telegram messages do not execute one-click rollback.
- Gaps:
  - None

### AC8
- Status: PASS
- Proof:
  - Local `py_compile` passed.
  - Local targeted suite passed: 84 tests.
  - Production AST check passed in app container.
  - Production app/worker restarted, Telegram bot restarted, HTTP smoke returned 200, logs show no tracebacks.
- Gaps:
  - Production image does not include pytest, so server unit test command cannot run without dev dependencies.

## Commands run
- `python3 -m py_compile src/core/industry_pattern_recalibration.py src/telegram_bot.py`
- `python3 -m pytest -q tests/test_industry_patterns.py tests/test_service_keyword_scoring.py tests/test_beauty_service_optimization.py tests/test_service_problem_regeneration.py tests/test_worker_services_quality.py tests/test_content_plan_generation.py`
- Server deploy: partial tar sync to `/opt/seo-app`
- Server: `cd /opt/seo-app && docker compose exec -T app python -B -c "<AST syntax check>"`
- Server: `cd /opt/seo-app && docker compose restart app worker`
- Server: `cd /opt/seo-app && systemctl restart openclaw-localos-telegram-bot.service`
- Server: `cd /opt/seo-app && docker compose ps && curl -I http://localhost:8000`
- Server: `cd /opt/seo-app && docker compose logs --since 2m app worker --tail=160`
- Server: `cd /opt/seo-app && systemctl is-active openclaw-localos-telegram-bot.service`

## Raw artifacts
- .agent/tasks/industry-patterns-rollback-safety-stage11-20260506/raw/build.txt
- .agent/tasks/industry-patterns-rollback-safety-stage11-20260506/raw/test-unit.txt
- .agent/tasks/industry-patterns-rollback-safety-stage11-20260506/raw/test-integration.txt
- .agent/tasks/industry-patterns-rollback-safety-stage11-20260506/raw/lint.txt
- .agent/tasks/industry-patterns-rollback-safety-stage11-20260506/raw/screenshot-1.png

## Known gaps
- No schema migration was needed.
- No browser screenshot was needed because this is Telegram/backend HITL.
- Production app image lacks pytest; local tests plus production AST/smoke were used.
