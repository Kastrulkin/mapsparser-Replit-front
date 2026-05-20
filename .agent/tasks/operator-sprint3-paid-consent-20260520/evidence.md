# Evidence Bundle: operator-sprint3-paid-consent-20260520

## Summary
- Overall status: PASS
- Last updated: 2026-05-20T13:05:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `src/services/operator_paid_actions.py` with `PAID_ACTIONS`.
  - Registry covers `map_reviews_refresh`, `review_replies_generate`, `news_generate`, `social_post_generate`, and `services_optimize`.
  - `tests/test_operator_paid_actions.py::test_paid_action_registry_covers_operator_paid_actions` passed.
- Gaps:
  - None for proposal-only Sprint 3.

### AC2
- Status: PASS
- Proof:
  - `build_paid_action_offer` returns consent modes, cost source, provider, status `proposal_only`, Apify multiplier, and estimate fields.
  - `build_attention_brief` now includes `paid_action_offers`.
  - Tests assert proposal-only status, x10 multiplier, and no invented price when no estimate exists.
- Gaps:
  - Real provider estimate ingestion is a non-goal for Sprint 3.

### AC3
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/OperatorPage.tsx` renders paid action offers as proposal-only cards.
  - `services.telegram_dashboard._format_operator_attention_text` includes the paid refresh offer text.
  - Tests assert Telegram copy says paid actions were not performed and manual map publication remains true.
- Gaps:
  - No browser screenshot was captured because this sprint is code/test verified and the build passed.

### AC4
- Status: PASS
- Proof:
  - Offer copy uses "точная стоимость появится после оценки" when no estimate is available.
  - `paid_actions_performed` remains `False`; no Apify, ledger, generation, or publication code paths were added.
  - Documentation explicitly states Sprint 3 does not execute paid actions.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Updated `docs/agents/localos-operator.md` and `docs/agents/index.md`.
  - Verification commands below passed.
- Gaps:
  - None.

## Commands run
- `python3 -m pytest -q tests/test_operator_paid_actions.py tests/test_operator_attention.py tests/test_telegram_dashboard_copy.py` -> PASS, 18 tests.
- `python3 -m py_compile src/services/operator_paid_actions.py src/services/operator_attention.py src/services/telegram_dashboard.py` -> PASS.
- `npm run build` in `frontend/` -> PASS.

## Raw artifacts
- .agent/tasks/operator-sprint3-paid-consent-20260520/raw/build.txt
- .agent/tasks/operator-sprint3-paid-consent-20260520/raw/test-unit.txt
- .agent/tasks/operator-sprint3-paid-consent-20260520/raw/test-integration.txt
- .agent/tasks/operator-sprint3-paid-consent-20260520/raw/lint.txt
- .agent/tasks/operator-sprint3-paid-consent-20260520/raw/screenshot-1.png

## Known gaps
- Sprint 3 intentionally does not persist consent policy, execute Apify, estimate actual Apify run cost, charge credits, generate AI content, or publish to external maps.
