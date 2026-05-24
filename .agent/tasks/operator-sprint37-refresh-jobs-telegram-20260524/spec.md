# Task Spec: operator-sprint37-refresh-jobs-telegram-20260524

## Metadata
- Task ID: operator-sprint37-refresh-jobs-telegram-20260524
- Created: 2026-05-24T10:30:41+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 37: Telegram follow-up for Operator refresh jobs: owner bot can show recent map refresh statuses/results and suggest reply generation without bypassing credits or publishing

## Acceptance criteria
- AC1: Telegram owner-bot recognizes refresh job follow-up requests.
- AC2: Telegram can show recent refresh jobs with processing/completed/failed status, new review counts, and snippets.
- AC3: Telegram reviews menu exposes a status action for refresh jobs.
- AC4: The flow does not start parsing, bypass credits, publish replies, or write to external map providers.
- AC5: Docs and proof artifacts describe the Sprint 37 boundary.

## Constraints
- Reuse `services.operator_refresh_result.list_refresh_jobs`.
- Keep Telegram as a transport over the same Operator core.
- Keep publication manual.
- Do not add schema changes.

## Non-goals
- Starting a new paid refresh from the status command.
- Publishing replies to maps.
- Changing Apify settlement or billing behavior.

## Verification plan
- Build: `python3 -m py_compile src/services/telegram_dashboard.py src/services/telegram_response_router.py src/telegram_bot.py`
- Unit tests: `python3 -m pytest -q tests/test_telegram_dashboard_copy.py tests/test_operator_refresh_result.py tests/test_operator_fresh_reviews.py`
- Integration tests: same targeted Telegram/Operator suite.
- Lint: `git diff --check`
- Manual checks: inspect callback and text routing.
