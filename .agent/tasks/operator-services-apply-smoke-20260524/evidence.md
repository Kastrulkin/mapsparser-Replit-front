# Evidence Bundle: operator-services-apply-smoke-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T18:17:00+03:00

## Acceptance criteria evidence

### AC1: Self-contained authenticated smoke
- Status: PASS
- Proof:
  - Added `scripts/smoke_operator_services_apply_api.py`.
  - The script uses only app source modules and standard library; it does not import `tests/`.
  - Lint baseline checks for self-contained markers.
- Gaps:
  - None.

### AC2: Fixture cleanup
- Status: PASS
- Proof:
  - Smoke inserts its own user, business, and two `userservices` rows.
  - Live output returned `fixture_cleaned=true`.

### AC3: Suggestions generated without external AI/provider calls
- Status: PASS
- Proof:
  - Smoke calls `optimize_services_from_operator` with an injected `fake_services_generator`.
  - No GigaChat/provider call is needed for the smoke.

### AC4: Apply without confirm is blocked
- Status: PASS
- Proof:
  - Live output returned `blocked_without_confirm=true`.
  - Smoke asserts services are unchanged after the blocked API call.
  - Smoke verifies a blocked audit event exists.

### AC5: Confirmed apply mutates LocalOS only
- Status: PASS
- Proof:
  - Live output returned `confirmed_apply_status=completed` and `applied_count=2`.
  - Smoke validates `userservices.optimized_name` values were updated.

### AC6: Audit event boundary
- Status: PASS
- Proof:
  - Live output returned `blocked_audit_event=true` and `completed_audit_event=true`.
  - Smoke asserts completed audit metadata has `external_writes_performed=false`, `credit_charged=false`, and `explicit_confirmation=true`.

### AC7: No extra charge on apply
- Status: PASS
- Proof:
  - Live output returned `ledger_after_generate=1` and `ledger_after_apply=1`.
  - Live output returned `credit_charged=false`.

### AC8: Lint guardrail
- Status: PASS
- Proof:
  - `scripts/lint_backend_baseline.sh` now py-compiles the smoke script.
  - It also checks required self-contained smoke markers and rejects imports from `tests/`.

## Commands run
- `python3 -m py_compile scripts/smoke_operator_services_apply_api.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_operator_services_optimization.py tests/test_approval_boundaries_audit.py tests/test_operator_paid_action_adapter.py tests/test_operator_review_reply_bulk.py tests/test_operator_paid_executor.py tests/test_operator_manual_publish.py`
- `scripts/lint_backend_baseline.sh`
- `cat scripts/smoke_operator_services_apply_api.py | ssh ... 'cd /opt/seo-app && docker compose exec -T app ...'`
- Server verification: `docker compose ps`, app/worker logs, root `curl -I`, frontend index.

## Raw artifacts
- .agent/tasks/operator-services-apply-smoke-20260524/raw/build.txt
- .agent/tasks/operator-services-apply-smoke-20260524/raw/test-unit.txt
- .agent/tasks/operator-services-apply-smoke-20260524/raw/test-integration.txt
- .agent/tasks/operator-services-apply-smoke-20260524/raw/lint.txt
- .agent/tasks/operator-services-apply-smoke-20260524/raw/screenshot-1.png

## Known gaps
- Authenticated browser click automation remains a future UI smoke; this task closes the authenticated API smoke and boundary smoke.
