# Evidence Bundle: operator-sprints-15-19-20260521

## Summary
- Overall status: PASS
- Last updated: 2026-05-21T14:05:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/operator_manual_review.py` implements manual review extraction, review insert, reply generation, and draft upsert.
  - `tests/test_operator_manual_review.py` covers completed review add plus generated draft response.
- Gaps:
  - Direct provider publication remains intentionally unavailable.

### AC2
- Status: PASS
- Proof:
  - Manual review reply generation uses `build_paid_action_preflight`, `reserve_paid_action_credits`, and `finalize_reserved_action_credits`.
  - Tests cover successful 1-credit charge, insufficient balance blocking, and generation-failure release.
- Gaps:
  - Provider-cost settlement is not part of paid compute reply generation.

### AC3
- Status: PASS
- Proof:
  - `frontend/src/pages/dashboard/OperatorPage.tsx` adds the chat-command card.
  - `src/main.py` returns reply draft fields on external reviews.
  - `frontend/src/components/ReviewReplyAssistant.tsx` seeds and displays stored draft text.
  - Browser sanity check opened `/dashboard/operator`; unauthenticated local app rendered and redirected to login instead of a blank page.
- Gaps:
  - Authenticated visual QA of the Operator card was not run in this local task; production build passed.

### AC4
- Status: PASS
- Proof:
  - `src/telegram_bot.py` detects the manual review intent and routes it into `process_operator_chat_message`.
  - Telegram records audit events and returns the same manual-publication boundary to the user.
- Gaps:
  - No live Telegram message was sent during local verification.

### AC5
- Status: PASS
- Proof:
  - `src/services/operator_map_refresh.py` defaults `OPERATOR_APIFY_REFRESH_ENABLED = False`.
  - `tests/test_operator_map_refresh.py` verifies disabled blocking, missing-link blocking, and controlled enqueue when monkeypatched enabled.
- Gaps:
  - Real Apify execution and actual-cost credit settlement remain future work.

### AC6
- Status: PASS
- Proof:
  - Updated `docs/agents/localos-operator.md`, `docs/agents/index.md`, and `docs/agents/tool-registry.md`.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/services/operator_manual_review.py src/services/operator_map_refresh.py src/services/operator_audit.py src/api/operator_api.py src/main.py src/telegram_bot.py tests/test_operator_manual_review.py tests/test_operator_map_refresh.py tests/test_operator_audit.py`
- `rg -n "\\bas\\b|typecast|::" src/services/operator_manual_review.py src/services/operator_map_refresh.py src/services/operator_audit.py src/api/operator_api.py tests/test_operator_manual_review.py tests/test_operator_map_refresh.py || true`
- `git diff --check`
- `python3 -m pytest -q tests/test_operator_manual_review.py tests/test_operator_map_refresh.py tests/test_operator_paid_action_adapter.py tests/test_operator_paid_executor.py tests/test_operator_credit_reservation.py tests/test_operator_paid_preflight.py tests/test_operator_consent_policy.py tests/test_operator_paid_actions.py tests/test_operator_attention.py tests/test_operator_audit.py tests/test_telegram_dashboard_copy.py`
- `npm run build`
- Browser sanity check: `http://127.0.0.1:5173/dashboard/operator`

## Raw artifacts
- .agent/tasks/operator-sprints-15-19-20260521/raw/build.txt
- .agent/tasks/operator-sprints-15-19-20260521/raw/test-unit.txt
- .agent/tasks/operator-sprints-15-19-20260521/raw/test-integration.txt
- .agent/tasks/operator-sprints-15-19-20260521/raw/lint.txt
- .agent/tasks/operator-sprints-15-19-20260521/raw/browser.txt
- .agent/tasks/operator-sprints-15-19-20260521/raw/screenshot-1.png

## Known gaps
- No commit, push, deploy, or production migration was performed.
- No direct map reply publication exists; users still copy/paste drafts manually.
- Apify refresh is represented by a disabled enqueue boundary only; actual provider execution and settlement are not enabled.
