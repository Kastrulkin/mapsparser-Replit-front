# Evidence Bundle: beauty-service-problem-regeneration-stage6-20260505

## Summary
- Overall status: PASS
- Last updated: 2026-05-05T17:50:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `POST /api/services/regenerate-problematic` and `GET /api/services/regenerate-problematic/<job_id>` implemented in `src/api/services_api.py`.
  - Selection helper filters `needs_review` and caps batch at 10.
  - Production unauthenticated checks returned 401 for both routes.

### AC2
- Status: PASS
- Proof:
  - Background daemon thread calls existing `/api/services/optimize`, applies drafts, and tracks `fixed`, `failed`, `manual_review`, `remaining`.
  - UI polls job status and refreshes services after completion.

### AC3
- Status: PASS
- Proof:
  - Attempt guard moves repeated problem services to manual review.
  - Unit tests cover repeat-failure manual review and batch limits.

### AC4
- Status: PASS
- Proof:
  - UI shows `Перегенерировать проблемные` and `До 10 услуг за запуск`.
  - `npm run build:all` passed.

### AC5
- Status: PASS
- Proof:
  - Telegram card menu uses `client_services_regenerate_problematic`.
  - Callback creates a scoped LocalOS session and starts the backend job.
  - Telegram service is active after deploy.

### AC6
- Status: PASS
- Proof:
  - `record_ai_learning_event` logs job start, service result, and job finish with `services.regenerate_problematic`.
  - No migration was added.

## Commands run
- `python3 -m py_compile src/core/service_problem_regeneration.py src/api/services_api.py src/telegram_bot.py`
- `python3 -m pytest -q tests/test_service_keyword_scoring.py tests/test_service_problem_regeneration.py`
- `cd frontend && npm run build:all`
- `python3 -m pytest -q tests/test_beauty_service_optimization.py tests/test_service_keyword_scoring.py tests/test_service_problem_regeneration.py`
- Production: `docker compose restart app worker`
- Production: `systemctl restart openclaw-localos-telegram-bot.service`
- Production: route auth gates, app logs, frontend bundle strings, and Telegram service status checked.

## Known gaps
- In-process queue/attempt memory resets on app restart. This is intentional for the no-migration stage.
- Runtime `py_compile` cannot write pycache under read-only `/app/src`, so source compile was verified with Python `compile(...)`.
