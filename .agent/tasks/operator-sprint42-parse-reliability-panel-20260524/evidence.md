# Evidence Bundle: operator-sprint42-parse-reliability-panel-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T16:40:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `services.operator_refresh_result.build_parse_reliability_state` builds a structured state from `parsequeue` status, `error_message`, `retry_after`, captcha fields, `resume_requested`, and `warnings`.
  - `build_refresh_result_status` and `list_refresh_jobs` include `reliability_state`.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Reliability states include `ok`, `processing`, `retrying`, `captcha_required`, `failed`, `paused`, `warning`, and `unknown`.
  - Failure reason labels use `parsing_failure_taxonomy.classify_failure_reason`.
  - Tests cover timeout, captcha, retry, and completed-with-warnings.
- Gaps:
  - New future parser reason codes will fall back to `unknown` until mapped.

### AC3
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/OperatorPage.tsx` shows summary counters for Retry, Captcha, Ошибки, and Warnings.
  - Each refresh job and single refresh result can render `renderReliabilityDetails`.
- Gaps:
  - No browser screenshot was captured in this pass; frontend build verifies the component compiles.

### AC4
- Status: PASS
- Proof:
  - `services.telegram_dashboard._format_operator_refresh_jobs_text` adds a compact `Надёжность` line for jobs requiring attention.
  - `tests/test_telegram_dashboard_copy.py` asserts the reliability line appears in Telegram copy.
- Gaps:
  - No live Telegram message was sent during verification.

### AC5
- Status: PASS
- Proof:
  - `scripts/lint_backend_baseline.sh` now checks that refresh reliability stays read-only and visible.
  - `operator_refresh_result.py` only reads parsequeue/reservation/review data and returns structured observations.
  - Docs state that Sprint 42 does not retry jobs, start Apify, mutate credits, publish replies, or write to external map providers.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/services/operator_refresh_result.py src/services/telegram_dashboard.py src/api/operator_api.py src/worker.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_operator_refresh_result.py tests/test_telegram_dashboard_copy.py tests/test_operator_refresh_telegram_followup.py tests/test_worker_apify_settlement.py tests/test_operator_map_refresh.py`
- `scripts/lint_backend_baseline.sh`
- `npm --prefix frontend run build`
- `git diff --check`

## Raw artifacts
- `.agent/tasks/operator-sprint42-parse-reliability-panel-20260524/raw/build.txt`
- `.agent/tasks/operator-sprint42-parse-reliability-panel-20260524/raw/test-unit.txt`
- `.agent/tasks/operator-sprint42-parse-reliability-panel-20260524/raw/lint.txt`
- `.agent/tasks/operator-sprint42-parse-reliability-panel-20260524/raw/test-integration.txt`

## Known gaps
- No production parse failure was manually triggered. Verification uses unit coverage and live deploy checks after commit.
