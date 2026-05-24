# Evidence Bundle: operator-sprint34-apify-worker-settlement-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T09:02:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `ProspectingService.run_business_by_map_url` now returns `usage_total_usd`, `usage_usd`, `usage`, and `run_data`.
  - Worker stores those fields in `_apify_debug`.
- Gaps:
  - Depends on Apify run response including authenticated usage fields.

### AC2
- Status: PASS
- Proof:
  - Worker helper queries `operatorcreditreservations` where `metadata ->> 'parsequeue_id' = queue_id`.
  - No parsequeue schema change required.
- Gaps:
  - Future paid refresh enqueue still needs to write that metadata.

### AC3
- Status: PASS
- Proof:
  - `_settle_operator_apify_cost_if_present` gates by Apify source, provider cost, queue identity, and matching reservation.
  - Unit test verifies `settle_apify_actual_cost` call payload.
- Gaps:
  - No live Apify call in tests.

### AC4
- Status: PASS
- Proof:
  - Missing cost and missing reservation return `status: skipped`.
  - Worker wraps settlement in a database savepoint.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - No UI/API paid refresh enqueue changes.
  - No external publish/write behavior added.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/worker.py src/services/prospecting_service.py src/services/operator_apify_settlement.py`
- `python3 -m pytest -q tests/test_worker_apify_settlement.py tests/test_prospecting_service_apify_business_parse.py tests/test_operator_apify_settlement.py`
- `git diff --check`

## Raw artifacts
- .agent/tasks/operator-sprint34-apify-worker-settlement-20260524/raw/build.txt
- .agent/tasks/operator-sprint34-apify-worker-settlement-20260524/raw/test-unit.txt
- .agent/tasks/operator-sprint34-apify-worker-settlement-20260524/raw/test-integration.txt
- .agent/tasks/operator-sprint34-apify-worker-settlement-20260524/raw/lint.txt
- .agent/tasks/operator-sprint34-apify-worker-settlement-20260524/raw/screenshot-1.png

## Known gaps
- Paid map refresh still needs preflight/reserve/enqueue and reservation metadata writing.
- Telegram follow-up after refresh completion is still later.
