# Task Spec: operator-ai-router-polish-20260524

## Metadata
- Task ID: operator-ai-router-polish-20260524
- Created: 2026-05-24T19:08:57+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Доделать Operator AI fallback router: card refresh UX, ai_router UI cost, no raw_response, cheap gate, endpoint integration tests, manual review guard; Telegram parity оставить отдельным этапом

## Acceptance criteria
- AC1: Operator refresh copy says card refresh, not only reviews.
- AC2: Operator UI exposes paid AI-router classification cost.
- AC3: AI-router public payload does not expose raw model response.
- AC4: Cheap gate prevents smalltalk from calling paid AI-router.
- AC5: `/api/operator/chat` fallback path has endpoint-level tests.
- AC6: `manual_review_add_and_reply` fallback cannot create a review without explicit review text.

## Constraints
- Telegram parity is a non-goal for this task and remains a separate next step.
- No external writes or automatic map publishing.
- Preserve rule-based routing before GigaChat fallback.

## Non-goals
- Deploy, push, or commit.
- Telegram owner-bot routing changes.
- DB schema changes.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit/integration tests: focused Operator pytest suite including `/api/operator/chat` tests.
- Lint/baseline: `bash scripts/lint_backend_baseline.sh`
- Static checks: `py_compile`, `git diff --check`
