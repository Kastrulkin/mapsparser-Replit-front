# Task Spec: operator-sprint2-telegram-attention-20260520

## Metadata
- Task ID: operator-sprint2-telegram-attention-20260520
- Created: 2026-05-20T11:51:25+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 2: connect the LocalOS Operator cached attention brief to the existing owner Telegram control surface. Reuse the Sprint 1 Operator core for the client_today / 'Что требует моего внимания сегодня?' flow, keep it cached-data only, do not execute paid refreshes, AI generation, provider writes, schema migrations, or deployment unless explicitly requested later. Update docs and proof evidence.

## Acceptance criteria
- AC1: Telegram owner-bot `client_today` callback and free-text today intent use the shared Sprint 1 Operator attention core.
- AC2: Telegram output clearly states cached-data mode, no paid actions executed, and manual publication boundary for map replies.
- AC3: Client intent classifier recognizes `Что требует моего внимания сегодня?` as the today/attention intent.
- AC4: No paid refresh, AI generation, external provider write, schema migration, production data change, commit, push, or deploy is performed.
- AC5: Operator documentation records Sprint 2 Telegram transport coverage without implying full freeform chat, public MCP, or provider write support.
- AC6: Proof-loop evidence records changed files and validation checks.

## Constraints
- Reuse the existing `services.operator_attention.build_attention_brief` core.
- Keep Telegram as a transport-specific formatter only.
- Preserve Sprint 0 consent/action taxonomy and Sprint 1 cached-data boundary.
- Do not deploy unless the user explicitly asks later.

## Non-goals
- Implement freeform LLM Operator chat.
- Implement paid refresh consent storage or charging.
- Implement Telegram paid actions.
- Implement provider publication or external writes.
- Add schema migrations.

## Verification plan
- Build: not required; backend/Telegram Python-only change.
- Unit tests: `python3 -m pytest -q tests/test_telegram_dashboard_copy.py tests/test_operator_attention.py`.
- Integration tests: not run; production Telegram polling requires live bot token/runtime.
- Lint/compile: `python3 -m py_compile src/services/telegram_dashboard.py src/services/telegram_response_router.py src/telegram_bot.py`.
- Manual checks: grep for Operator/unsupported-claim boundaries.
