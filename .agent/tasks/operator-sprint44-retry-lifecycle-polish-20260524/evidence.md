# Evidence Bundle: operator-sprint44-retry-lifecycle-polish-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T17:30:00Z

## Proof
- Retry requests now pass `retry_source_queue_id`, source status, and reason code into the new paid map-refresh reservation metadata.
- Refresh result/list APIs expose that lineage through `billing_state.retry_source_queue_id` and job-level `retry_source_queue_id`.
- Web Operator shows `Повтор от job ...` and immediately checks the newly created job after a retry succeeds.
- Existing safety boundaries remain: old job is not updated, no provider writes are added, and request time still reserves rather than charges credits.

## Commands Run
- `python3 -m py_compile src/services/operator_map_refresh.py src/services/operator_refresh_retry.py src/services/operator_refresh_result.py src/api/operator_api.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_operator_refresh_retry.py tests/test_operator_refresh_result.py tests/test_operator_map_refresh.py`
- `npm --prefix frontend run build`
- `git diff --check`

## Result
- `18 passed`
- Frontend production build passed.
- Diff whitespace check passed.

## Known Gaps
- No live paid retry was triggered on production, intentionally, because it would create a real reservation and parsequeue job.
