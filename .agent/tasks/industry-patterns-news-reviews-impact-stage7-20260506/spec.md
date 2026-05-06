# Task Spec: industry-patterns-news-reviews-impact-stage7-20260506

## Metadata
- Task ID: industry-patterns-news-reviews-impact-stage7-20260506
- Created: 2026-05-06T14:17:09+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 7: расширить измерение active-паттернов с услуг на новости и ответы на отзывы

## Acceptance criteria
- AC1: Manual news generation records active industry pattern prompt usage and result quality metrics.
- AC2: Manual review reply generation records active industry pattern prompt usage and result quality metrics.
- AC3: Card automation news and review reply drafts record active pattern usage and result quality metrics.
- AC4: Content plan news draft generation records active pattern usage and result quality metrics.
- AC5: Telegram active-pattern health includes news/review metrics, not only service metrics.
- AC6: Relevant local tests and production smoke checks pass.

## Constraints
- Do not add a new schema migration; reuse `industry_pattern_impact_events` from stage 6.
- Do not auto-disable or auto-apply patterns.
- Keep HITL decisions in Telegram.

## Non-goals
- A/B attribution.
- Frontend dashboard.
- Automatic monthly report; that is the next stage.

## Verification plan
- Build: Python syntax checks for touched backend modules.
- Unit tests: industry patterns, content plan generation, worker quality, service/beauty regressions.
- Integration: production AST syntax check, restart app/worker/bot, HTTP smoke, logs.
