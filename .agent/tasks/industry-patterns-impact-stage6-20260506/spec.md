# Task Spec: industry-patterns-impact-stage6-20260506

## Metadata
- Task ID: industry-patterns-impact-stage6-20260506
- Created: 2026-05-06T13:59:35+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 6 системы паттернов: измерение влияния active-паттернов на оптимизатор. Нужно логировать применение active-паттернов, считать базовые impact-метрики по результатам service optimization, показывать health active-паттернов в Telegram и готовить suspicious candidates для отключения.

## Acceptance criteria
- AC1: Active industry patterns are loaded as structured versions before service optimization and recorded when they are used in the optimizer prompt.
- AC2: Service optimization records result metrics for active patterns: total services, good, needs_review, fallback, guardrails, pattern_fit, missing keywords, weak matches, no keywords.
- AC3: Superadmin Telegram flow exposes a health screen for active patterns and allows suspicious patterns to be disabled from that screen.
- AC4: Production schema is migrated safely with a backup before adding impact-event storage.
- AC5: Relevant tests and smoke checks pass, with unrelated full-suite failures documented.

## Constraints
- Do not apply or disable patterns automatically.
- Human-in-the-loop remains required for active pattern decisions.
- Keep existing industry pattern prompts and beauty guardrails as priority layers.
- Use Alembic for schema changes.

## Non-goals
- Statistical A/B attribution.
- Automatic rollback of suspicious patterns.
- Frontend dashboard for impact analytics.

## Verification plan
- Build: Python AST/syntax checks locally and in container.
- Unit tests: industry pattern, service keyword, beauty guardrail, service regeneration, worker quality, content plan tests.
- Integration tests: production migration and smoke checks.
- Manual checks: Telegram bot service active, `/` returns 200, new table exists, app/worker logs clean.
