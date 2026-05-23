# Evidence Bundle: operator-sprints21-25-20260523

## Summary
- Overall status: PASS
- Last updated: 2026-05-23T11:00:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added Operator Inbox service and `/api/operator/inbox`.
  - Added manual review reply publish-tracking service and endpoint.
  - Added web Operator Inbox UI with copy/open/mark-manual-published actions.
  - Kept map publication manual and external writes disabled.
  - Telegram manual-review flow now repeats the copy/paste publication boundary.
  - Updated agent docs and tool registry for Sprint 21-25.
- Gaps:
  - Real Apify execution and provider actual-cost settlement remain behind later controlled rollout.

## Commands run
- `python3 -m py_compile src/services/operator_inbox.py src/services/operator_manual_publish.py src/services/operator_manual_review.py src/services/operator_map_refresh.py src/api/operator_api.py src/telegram_bot.py`
- `python3 -m pytest -q tests/test_operator_inbox.py tests/test_operator_manual_publish.py tests/test_operator_manual_review.py tests/test_operator_paid_preflight.py tests/test_operator_credit_reservation.py tests/test_operator_paid_actions.py tests/test_operator_paid_executor.py tests/test_operator_map_refresh.py tests/test_operator_audit.py tests/test_telegram_dashboard_copy.py tests/test_telegram_response_router.py`
- `cd frontend && npm run build`
- `git diff --check`
- Browser smoke: opened `http://127.0.0.1:3000/dashboard/operator`; auth guard rendered login page without bundle crash.

## Raw artifacts
- .agent/tasks/operator-sprints21-25-20260523/raw/build.txt
- .agent/tasks/operator-sprints21-25-20260523/raw/test-unit.txt
- .agent/tasks/operator-sprints21-25-20260523/raw/test-integration.txt
- .agent/tasks/operator-sprints21-25-20260523/raw/lint.txt
- .agent/tasks/operator-sprints21-25-20260523/raw/screenshot-1.png

## Known gaps
- Real external map refresh through Apify is not enabled by default.
- Direct publishing to maps is still not supported; users copy/paste manually.
