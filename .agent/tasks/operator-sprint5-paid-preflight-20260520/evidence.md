# Evidence Bundle: operator-sprint5-paid-preflight-20260520

## Summary
- Overall status: PASS
- Last updated: 2026-05-20T19:22:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/services/operator_paid_preflight.py`.
  - Preflight supports `map_reviews_refresh` through the shared `PAID_ACTIONS` registry, so future paid action keys can reuse the same gate.
- Gaps:
  - Actual execution remains intentionally disabled.

### AC2
- Status: PASS
- Proof:
  - Preflight validates action key, positive estimated credits, `users.credits_balance`, consent mode, disabled policy, explicit consent for `ask_each_time`, and action/day/month limits for `auto_with_limits`.
  - `tests/test_operator_paid_preflight.py` covers allowed, missing estimate, disabled policy, insufficient balance, over-limit, and unknown action paths.
- Gaps:
  - Historical daily/monthly spend reservation is not implemented yet; preflight returns a warning.

### AC3
- Status: PASS
- Proof:
  - Service returns `execution_status=preflight_only`, `execution_enabled=False`, `can_execute_now=False`, `paid_actions_performed=False`, `credit_charged=False`, and `external_calls_performed=False`.
  - No parsequeue insertion, Apify call, AI generation, credit ledger write, or external write code was added.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Added `POST /api/operator/paid-actions/<action_key>/preflight`.
  - Route reuses auth and business access checks before calling the preflight service.
- Gaps:
  - No live Flask integration fixture was added; service behavior is covered by unit tests.

### AC5
- Status: PASS
- Proof:
  - `/dashboard/operator` paid action cards now include estimated credits, explicit one-time consent, a preflight button, and result rendering.
  - Frontend production build passed.
- Gaps:
  - No screenshot captured in this run.

### AC6
- Status: PASS
- Proof:
  - `tests/test_operator_paid_preflight.py` covers all requested states.
  - Verification commands below passed.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest -q tests/test_operator_paid_preflight.py tests/test_operator_consent_policy.py tests/test_operator_paid_actions.py tests/test_operator_attention.py tests/test_telegram_dashboard_copy.py` -> PASS, 28 tests.
- `python3 -m py_compile src/services/operator_paid_preflight.py src/api/operator_api.py src/services/operator_consent_policy.py src/services/operator_paid_actions.py src/services/operator_attention.py` -> PASS.
- `npm run build` in `frontend/` -> PASS.
- `git diff --check` -> PASS.

## Raw artifacts
- .agent/tasks/operator-sprint5-paid-preflight-20260520/raw/build.txt
- .agent/tasks/operator-sprint5-paid-preflight-20260520/raw/test-unit.txt
- .agent/tasks/operator-sprint5-paid-preflight-20260520/raw/test-integration.txt
- .agent/tasks/operator-sprint5-paid-preflight-20260520/raw/lint.txt
- .agent/tasks/operator-sprint5-paid-preflight-20260520/raw/screenshot-1.png

## Known gaps
- Sprint 5 intentionally does not execute Apify, create parsequeue jobs, reserve credits, charge credits, generate AI content, or publish externally.
- Historical daily/monthly usage accounting is not implemented; preflight checks configured ceilings against the current estimate and reports a warning.
