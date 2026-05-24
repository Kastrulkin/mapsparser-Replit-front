# Evidence Bundle: operator-sprint39-content-history-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T15:23:09Z

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `services.operator_content_history.list_operator_content_history` returns typed history items.
  - `GET /api/operator/content-history` exposes the scoped history through Operator API.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - The service emits `review_reply_draft`, `news_draft`, `social_post_draft`, `service_suggestion`, and `service_apply`.
  - `tests/test_operator_content_history.py` verifies all five buckets.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `_insert_news_draft` accepts `prompt_key`.
  - Social post generation passes `operator_social_post_generate`.
- Gaps:
  - Existing old social post rows may still have the older prompt key; new rows are separated.

### AC4
- Status: PASS
- Proof:
  - `OperatorPage.tsx` renders `Черновики и предложения` with per-kind counters and typed items.
  - Frontend build passed.
- Gaps:
  - No authenticated browser session was used to click through real content history.

## Commands run
- `python3 -m py_compile src/services/operator_content_history.py src/services/operator_refresh_result.py src/services/operator_apify_settlement.py src/services/operator_news_generation.py src/services/operator_social_post_generation.py src/api/operator_api.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_operator_content_history.py tests/test_operator_news_generation.py tests/test_operator_social_post_generation.py`
- `cd frontend && npm run build`
- `scripts/lint_backend_baseline.sh`
- `git diff --check`

## Raw artifacts
- .agent/tasks/operator-sprint39-content-history-20260524/raw/build.txt
- .agent/tasks/operator-sprint39-content-history-20260524/raw/test-unit.txt
- .agent/tasks/operator-sprint39-content-history-20260524/raw/test-integration.txt
- .agent/tasks/operator-sprint39-content-history-20260524/raw/lint.txt
- .agent/tasks/operator-sprint39-content-history-20260524/raw/screenshot-1.png

## Known gaps
- Existing old social post rows may still have the older prompt key; new generated social posts are separated.
- No authenticated browser click-through was run.
