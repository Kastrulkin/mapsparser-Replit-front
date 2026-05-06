# Evidence Bundle: beauty-service-persistent-regeneration-stage7-20260505

## Summary
- Overall status: PASS
- Last updated: 2026-05-05T19:15:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added Alembic migration `20260505_002`.
  - Production `flask db current` returns `20260505_002 (head)`.
  - Production table check returns `serviceregenerationjobs|serviceregenerationjobitems`.

### AC2
- Status: PASS
- Proof:
  - Backend creates `awaiting_confirmation` job unless `confirm: true`.
  - Confirm request with `job_id` starts persisted job.

### AC3
- Status: PASS
- Proof:
  - Scoring now returns `manual_review` status separately.
  - UI summary/filter includes manual review.
  - Bulk regeneration targets only ordinary `needsReview`.

### AC4
- Status: PASS
- Proof:
  - Latest job item is attached to each service as `regeneration_history`.
  - Table shows latest status, attempt, after-issues, and error.

### AC5
- Status: PASS
- Proof:
  - Telegram first click asks for confirmation.
  - `svc_regen_go:<job_id>` callback starts the job.

### AC6
- Status: PASS
- Proof:
  - 429 path stores `cooldown_until`.
  - Start endpoint blocks new runs during active cooldown.
  - UI message shows cooldown time.

### AC7
- Status: PASS
- Proof:
  - `19 passed` targeted pytest.
  - `npm run build:all` passed.
  - Production app/worker running, health 200, routes auth-gated, Telegram active.

## Commands run
- `python3 -m py_compile src/core/service_problem_regeneration.py src/core/service_keyword_scoring.py src/api/services_api.py src/telegram_bot.py alembic_migrations/versions/20260505_add_service_regeneration_jobs.py`
- `python3 -m pytest -q tests/test_beauty_service_optimization.py tests/test_service_keyword_scoring.py tests/test_service_problem_regeneration.py`
- `cd frontend && npm run build:all`
- Production DB backup: `pg_dump`.
- Production deploy/restart: `docker compose up -d --force-recreate app worker`.
- Production checks: `flask db current`, `to_regclass`, route 401 checks, app logs, Telegram status.

## Known gaps
- Execution is app-thread triggered, not yet a dedicated worker queue consumer.
- Full service-history drawer is not included; latest history item is shown inline.
