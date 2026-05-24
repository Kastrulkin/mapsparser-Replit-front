# Evidence Bundle: operator-sprint43-refresh-retry-request-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T17:36:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/api/operator_api.py` exposes `POST /api/operator/reviews/refresh-jobs/<queue_id>/retry`.
  - Backend lint route ownership check verifies the route endpoint.
  - `frontend/src/pages/dashboard/OperatorPage.tsx` shows `Повторить refresh` for retryable jobs and sends `confirm_retry: true`.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `build_refresh_retry_plan` uses `build_parse_reliability_state`.
  - Retryable states are `failed`, `captcha_required`, `paused`, and `warning`.
  - Unit tests cover allowed failed jobs and blocked processing jobs.
- Gaps:
  - Automatic retry scheduling is intentionally out of scope.

### AC3
- Status: PASS
- Proof:
  - `request_refresh_retry` blocks with `explicit_retry_confirmation_required` unless `confirm_retry=True`.
  - API route passes `confirm_retry=bool(payload.get("confirm_retry"))`.
  - Unit test covers the no-confirm block with no side effects.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Confirmed retry calls `enqueue_paid_operator_map_refresh`.
  - Unit test verifies the old failed queue is not updated and the new queued result comes from the paid enqueue boundary.
- Gaps:
  - Live production retry was not executed to avoid creating a paid reservation/job on real data.

### AC5
- Status: PASS
- Proof:
  - Service reports `external_writes_performed=False`, `external_calls_performed=False`, and `credit_charged=False`.
  - Lint guardrail rejects direct parsequeue mutation, direct Apify client use, direct message sends, and provider publish markers.
  - Chat response explicitly states the old failed job was not changed and map publication remains manual.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - `python3 -m py_compile src/services/operator_refresh_retry.py src/services/operator_refresh_result.py src/services/telegram_dashboard.py src/api/operator_api.py src/worker.py` passed.
  - `40 passed` for targeted retry/map-refresh/refresh-result/Telegram follow-up/worker settlement tests.
  - `scripts/lint_backend_baseline.sh` passed.
  - `npm --prefix frontend run build` passed.
  - `git diff --check` passed.
- Gaps:
  - Full test suite was not run; scope was targeted backend/frontend checks.

## Commands run
- `python3 -m py_compile src/services/operator_refresh_retry.py src/services/operator_refresh_result.py src/services/telegram_dashboard.py src/api/operator_api.py src/worker.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_operator_refresh_retry.py tests/test_operator_refresh_result.py tests/test_operator_map_refresh.py tests/test_operator_refresh_telegram_followup.py tests/test_worker_apify_settlement.py tests/test_telegram_dashboard_copy.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `git diff --check`

## Raw artifacts
- .agent/tasks/operator-sprint43-refresh-retry-request-20260524/raw/build.txt
- .agent/tasks/operator-sprint43-refresh-retry-request-20260524/raw/test-unit.txt
- .agent/tasks/operator-sprint43-refresh-retry-request-20260524/raw/test-integration.txt
- .agent/tasks/operator-sprint43-refresh-retry-request-20260524/raw/lint.txt
- .agent/tasks/operator-sprint43-refresh-retry-request-20260524/raw/frontend-build.txt
- .agent/tasks/operator-sprint43-refresh-retry-request-20260524/raw/diff-check.txt
- .agent/tasks/operator-sprint43-refresh-retry-request-20260524/raw/screenshot-1.png

## Known gaps
- No live production retry was triggered, intentionally, because it would create a paid reservation and a new parsequeue job.
- Production route smoke will verify auth boundary after deploy; it will not trigger a paid retry.
