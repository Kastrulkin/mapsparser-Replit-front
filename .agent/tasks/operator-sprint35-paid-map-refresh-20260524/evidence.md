# Evidence Bundle: operator-sprint35-paid-map-refresh-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T09:13:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `services.operator_fresh_reviews.refresh_reviews_from_operator` calls `enqueue_paid_operator_map_refresh`.
  - `services.operator_map_refresh.enqueue_paid_operator_map_refresh` calls `build_paid_action_preflight` before reserving credits or enqueueing.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `enqueue_paid_operator_map_refresh` generates a `queue_id`, reserves `map_reviews_refresh`, and writes `parsequeue_id` into reservation metadata.
  - `tests/test_operator_map_refresh.py::test_paid_map_refresh_reserves_credits_and_links_reservation_to_queue` covers the reservation metadata link.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `enqueue_operator_map_refresh` remains the narrow read-only parsequeue enqueue boundary.
  - `enqueue_paid_operator_map_refresh` releases the reservation through `finalize_reserved_action_credits(..., finalization_mode="release")` if enqueue fails.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Fresh-review responses include `queue_id`, `reservation_id`, `estimated_credits`, `balance_credits`, billing URL for blocked states, and UI next actions.
  - `tests/test_operator_fresh_reviews.py` covers both queued and insufficient-balance responses.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Operator code only enqueues read-only parsing and reports manual-publication boundaries.
  - No provider write or reply publication path was added.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/services/operator_map_refresh.py src/services/operator_fresh_reviews.py src/api/operator_api.py`
- `python3 -m pytest -q tests/test_operator_map_refresh.py tests/test_operator_fresh_reviews.py tests/test_operator_refresh_result.py tests/test_operator_apify_settlement.py`
- `git diff --check`

## Raw artifacts
- .agent/tasks/operator-sprint35-paid-map-refresh-20260524/raw/build.txt
- .agent/tasks/operator-sprint35-paid-map-refresh-20260524/raw/test-unit.txt
- .agent/tasks/operator-sprint35-paid-map-refresh-20260524/raw/test-integration.txt
- .agent/tasks/operator-sprint35-paid-map-refresh-20260524/raw/lint.txt
- .agent/tasks/operator-sprint35-paid-map-refresh-20260524/raw/screenshot-1.png

## Known gaps
- No known implementation gaps for Sprint 35. Apify provider execution itself remains in the existing worker/parser path; Operator does not call Apify directly.
