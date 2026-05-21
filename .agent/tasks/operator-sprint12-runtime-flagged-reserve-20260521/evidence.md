# Evidence Bundle: operator-sprint12-runtime-flagged-reserve-20260521

## Summary
- Overall status: PASS
- Last updated: 2026-05-21T08:35:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `services.operator_paid_preflight.EXECUTION_ENABLED` remains `False`.
  - `test_execution_attempt_does_not_reserve_when_runtime_flag_disabled` asserts no reservation insert and no rollback result.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - `src/services/operator_paid_executor.py` calls `reserve_paid_action_credits` only in the `EXECUTION_ENABLED=True` branch after preflight is ready.
  - `test_execution_attempt_reserves_and_rolls_back_when_runtime_flag_enabled` asserts reservation creation.
- Gaps:
  - Runtime flag remains disabled by default.

### AC3
- Status: PASS
- Proof:
  - The enabled branch calls `finalize_reserved_action_credits(..., finalization_mode="release")` after the internal stub adapter.
  - Tests assert rollback status `released`, no credit charge, no ledger entry, and no external side effects.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Executor passes `reservation_plan.idempotency_key` into reserve.
  - Tests assert reservation result uses the same idempotency key.
  - Reservation tests assert the DB statement uses `ON CONFLICT (business_id, action_key, idempotency_key)`.
- Gaps:
  - Full DB conflict behavior is covered by schema/query contract, not by a live DB integration test.

### AC5
- Status: PASS
- Proof:
  - Execute result still reports `external_calls_performed=False`, `parsequeue_jobs_created=False`, `ai_generation_performed=False`, and `credit_charged=False`.
  - No Apify or provider code path changed.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - Updated `docs/agents/localos-operator.md` and `docs/agents/index.md`.
  - Operator test suite passed.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest -q tests/test_operator_credit_reservation.py tests/test_operator_paid_action_adapter.py tests/test_operator_paid_executor.py tests/test_operator_paid_preflight.py tests/test_operator_consent_policy.py tests/test_operator_paid_actions.py tests/test_operator_attention.py tests/test_operator_audit.py tests/test_telegram_dashboard_copy.py`
- `python3 -m py_compile src/services/operator_paid_executor.py src/services/operator_credit_reservation.py src/services/operator_paid_action_adapter.py src/api/operator_api.py tests/test_operator_paid_executor.py`
- `git diff --check`

## Raw artifacts
- .agent/tasks/operator-sprint12-runtime-flagged-reserve-20260521/raw/build.txt
- .agent/tasks/operator-sprint12-runtime-flagged-reserve-20260521/raw/test-unit.txt
- .agent/tasks/operator-sprint12-runtime-flagged-reserve-20260521/raw/test-integration.txt
- .agent/tasks/operator-sprint12-runtime-flagged-reserve-20260521/raw/lint.txt
- .agent/tasks/operator-sprint12-runtime-flagged-reserve-20260521/raw/screenshot-1.png

## Known gaps
- No commit, push, or deploy performed yet.
- `EXECUTION_ENABLED` remains disabled by default.
- No real paid external execution or Apify integration.
