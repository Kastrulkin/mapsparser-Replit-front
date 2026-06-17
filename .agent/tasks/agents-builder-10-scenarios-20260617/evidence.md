# Evidence Bundle: agents-builder-10-scenarios-20260617

## Summary
- Overall status: PASS
- Last updated: 2026-06-17T13:20:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `test_agent_builder_understands_core_user_scenarios_without_cross_domain_questions`.
  - Manual scenario check covered: reviews_to_telegram, daily_reminder, sheets_to_telegram, orders_without_status, negative_reviews, map_content_plan, services_check, finance_import, partner_search, booking_control.
  - Final observed categories: custom, custom, custom, tables, reviews, custom, services, custom, partnerships, communications.
- Gaps:
  - Google Sheets -> Telegram still asks for table/link and Telegram destination when the user did not specify them; this is intentional.

### AC2
- Status: PASS
- Proof:
  - Scenario test asserts non-outreach scenarios do not receive lead/prospectingleads questions.
  - Partner scenario is classified as `partnerships`, not generic outreach.
- Gaps:
  - None known.

### AC3
- Status: PASS
- Proof:
  - Daily Telegram reminder and reviews-to-Telegram scenarios now reach `needs_connection / choose_route` with `telegram_destination`.
  - Reviews-to-Telegram keeps `external_reviews` as a source.
- Gaps:
  - Telegram connection itself still has to be configured by the user/account.

### AC4
- Status: PASS
- Proof:
  - Google Sheets -> Telegram asks `google_sheets_target`.
  - Finance import asks `google_sheets_target` and keeps `localos_finance` source.
- Gaps:
  - None known.

### AC5
- Status: PASS
- Proof:
  - `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q` passed with 160 tests.
  - `npm run build` passed.
- Gaps:
  - Build emitted existing Browserslist/Rollup annotation warnings only.

## Commands run
- `PYTHONPATH=src venv/bin/python - <<'PY' ... build_agent_builder_state for 10 prompts ... PY`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py::test_agent_builder_understands_core_user_scenarios_without_cross_domain_questions -q`
- `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- `cd frontend && npm run build`

## Raw artifacts
- .agent/tasks/agents-builder-10-scenarios-20260617/raw/build.txt
- .agent/tasks/agents-builder-10-scenarios-20260617/raw/test-unit.txt
- .agent/tasks/agents-builder-10-scenarios-20260617/raw/test-integration.txt
- .agent/tasks/agents-builder-10-scenarios-20260617/raw/lint.txt
- .agent/tasks/agents-builder-10-scenarios-20260617/raw/screenshot-1.png

## Known gaps
- Production deploy still needs to be performed after commit/push.
