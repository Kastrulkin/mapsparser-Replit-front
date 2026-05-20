# Evidence Bundle: operator-sprint4-consent-policy-20260520

## Summary
- Overall status: PASS
- Last updated: 2026-05-20T13:45:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added Alembic migration `alembic_migrations/versions/20260520_add_operator_consent_policies.py`.
  - Migration creates `operatorconsentpolicies` with business/action uniqueness, consent mode check, nonnegative limits, user attribution, and timestamps.
  - No credit ledger, provider execution, AI generation, or publication schema was changed.
- Gaps:
  - Production migration was not applied in this local Sprint 4 run.

### AC2
- Status: PASS
- Proof:
  - Added `src/services/operator_consent_policy.py`.
  - `validate_consent_policy_payload` rejects unknown action keys, invalid modes, invalid limits, and `auto_with_limits` without explicit positive action/day limits.
  - `tests/test_operator_consent_policy.py` covers defaults, required limits, valid auto policy, and unknown actions.
- Gaps:
  - Runtime spend checks remain future execution work.

### AC3
- Status: PASS
- Proof:
  - Added `GET /api/operator/consent-policy?business_id=<id>`.
  - Added `PUT /api/operator/consent-policy/<action_key>`.
  - Both routes reuse `require_auth_from_request` and `verify_business_access`.
- Gaps:
  - API integration test with a live Postgres fixture was not added; service behavior is unit-tested.

### AC4
- Status: PASS
- Proof:
  - `build_attention_brief` loads `map_reviews_refresh` consent policy and passes it into the paid action offer.
  - `build_paid_action_offer` now includes `current_consent_policy`.
  - Existing attention and paid action tests assert the policy is included.
- Gaps:
  - Missing table falls back to `ask_each_time`, intentionally preserving pre-migration behavior.

### AC5
- Status: PASS
- Proof:
  - `/dashboard/operator` paid action cards now render consent mode controls, auto-limit inputs, saved-policy messaging, and a save action.
  - UI keeps explicit copy that Sprint 4 does not execute or charge paid actions.
  - `npm run build` passed.
- Gaps:
  - No browser screenshot was captured in this run.

### AC6
- Status: PASS
- Proof:
  - Verification commands passed.
  - No Apify calls, model generation, credit ledger writes, or external publication code paths were added.
  - Docs explicitly state Sprint 4 persists policy only.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest -q tests/test_operator_consent_policy.py tests/test_operator_paid_actions.py tests/test_operator_attention.py tests/test_telegram_dashboard_copy.py` -> PASS, 22 tests.
- `python3 -m py_compile src/services/operator_consent_policy.py src/services/operator_paid_actions.py src/services/operator_attention.py src/api/operator_api.py src/services/telegram_dashboard.py alembic_migrations/versions/20260520_add_operator_consent_policies.py` -> PASS.
- `python3 -m alembic -c alembic.ini heads` -> PASS, single head `20260520_001`.
- `npm run build` in `frontend/` -> PASS.
- `git diff --check` -> PASS.

## Raw artifacts
- .agent/tasks/operator-sprint4-consent-policy-20260520/raw/build.txt
- .agent/tasks/operator-sprint4-consent-policy-20260520/raw/test-unit.txt
- .agent/tasks/operator-sprint4-consent-policy-20260520/raw/test-integration.txt
- .agent/tasks/operator-sprint4-consent-policy-20260520/raw/lint.txt
- .agent/tasks/operator-sprint4-consent-policy-20260520/raw/screenshot-1.png

## Known gaps
- Sprint 4 intentionally does not execute paid refresh, estimate actual Apify run cost, charge credits, generate AI content, or publish to external maps.
- Production deployment and migration application were not requested in this turn.
