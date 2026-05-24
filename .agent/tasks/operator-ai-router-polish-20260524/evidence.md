# Evidence Bundle: operator-ai-router-polish-20260524

## Summary
- Overall status: PASS
- Last updated: 2026-05-24T19:08:57+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `refresh_reviews_from_operator` now says “платное read-only обновление карточки” and lists базовая информация, отзывы, услуги, новости and other source fields.
- Gaps:
  - API route names still include `/reviews/refresh-*`; this is internal/backward-compatible and was not changed.

### AC2
- Status: PASS
- Proof:
  - Operator UI renders `AI-разбор команды: -N кредит` when `operator_result.ai_router.credit_charged` is true.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `operator_intent_ai_router` no longer returns `raw_response`; tests assert it is absent.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - `should_use_ai_intent_router` allows Operator-like commands and skips “привет”, “спасибо”, and “?”.
  - `/api/operator/chat` smalltalk test asserts AI-router is not called and no credit is charged.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Added `/api/operator/chat` tests for rule-based refresh, smalltalk cheap gate, AI fallback card refresh, and manual-review guard.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - AI fallback intent `manual_review_add_and_reply` now requires explicit review text markers before creating a review.
  - Endpoint test asserts “надо ответить людям” does not create a review.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile src/api/operator_api.py src/services/operator_intent_ai_router.py src/services/operator_fresh_reviews.py src/services/operator_paid_actions.py`
- `PYTHONPATH=src:. python3 -m pytest -q tests/test_operator_chat_fallback_api.py tests/test_operator_intent_ai_router.py tests/test_operator_fresh_reviews.py tests/test_operator_capabilities.py tests/test_operator_manual_review.py tests/test_operator_review_reply_bulk.py tests/test_operator_news_generation.py tests/test_operator_social_post_generation.py tests/test_operator_services_optimization.py`
- `git diff --check`
- `npm --prefix frontend run build`
- `bash scripts/lint_backend_baseline.sh`

## Raw artifacts
- .agent/tasks/operator-ai-router-polish-20260524/raw/build.txt
- .agent/tasks/operator-ai-router-polish-20260524/raw/test-unit.txt
- .agent/tasks/operator-ai-router-polish-20260524/raw/test-integration.txt
- .agent/tasks/operator-ai-router-polish-20260524/raw/lint.txt
- .agent/tasks/operator-ai-router-polish-20260524/raw/screenshot-1.png

## Known gaps
- Telegram parity remains a separate task by request.
