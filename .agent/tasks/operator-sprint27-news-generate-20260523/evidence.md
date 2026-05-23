# Evidence Bundle: operator-sprint27-news-generate-20260523

## Summary
- Overall status: VALID
- Last updated: 2026-05-23T20:00:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added `services.operator_news_generation.generate_news_draft_from_operator`.
  - Added web chat routing for `news_generate` intent and `POST /api/operator/news/generate`.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Workflow calls `build_paid_action_preflight`, `reserve_paid_action_credits`, AI generation, `usernews` insert, and `finalize_reserved_action_credits`.
  - `tests/test_operator_news_generation.py::test_generate_news_draft_charges_and_saves_usernews`.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `tests/test_operator_news_generation.py::test_generate_news_draft_releases_when_generation_fails`.
  - `tests/test_operator_news_generation.py::test_generate_news_draft_releases_when_model_returns_empty_text`.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Result sets `external_writes_performed = False` and `manual_publication_only = True`.
  - UI copy says publication is manual.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - `OperatorPage.tsx` handles `news_draft` / `news_text`, copy action, and Inbox button for `news_generate`.
  - Frontend build succeeded; raw artifact: `raw/frontend-build.txt`.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - Updated `docs/agents/localos-operator.md`.
  - Updated `docs/agents/index.md`.
  - Updated `docs/agents/tool-registry.md`.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/services/operator_news_generation.py src/api/operator_api.py`
- `python3 -m pytest -q tests/test_operator_news_generation.py tests/test_operator_review_reply_bulk.py tests/test_operator_manual_review.py tests/test_operator_inbox.py tests/test_operator_paid_preflight.py tests/test_operator_credit_reservation.py tests/test_operator_paid_actions.py tests/test_operator_paid_executor.py tests/test_operator_map_refresh.py tests/test_operator_audit.py tests/test_telegram_dashboard_copy.py tests/test_telegram_response_router.py`
- `cd frontend && npm run build`
- `git diff --check`

## Raw artifacts
- .agent/tasks/operator-sprint27-news-generate-20260523/raw/build.txt
- .agent/tasks/operator-sprint27-news-generate-20260523/raw/test-unit.txt
- .agent/tasks/operator-sprint27-news-generate-20260523/raw/test-integration.txt
- .agent/tasks/operator-sprint27-news-generate-20260523/raw/lint.txt
- .agent/tasks/operator-sprint27-news-generate-20260523/raw/screenshot-1.png

## Known gaps
- Telegram parity, social post generation, services optimization, Apify actual-cost settlement, and fresh-review refresh remain later sprints from the user-approved plan.
