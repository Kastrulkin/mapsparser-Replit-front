# Task Spec: partnership-partner-pipeline-20260617

## Metadata
- Task ID: partnership-partner-pipeline-20260617
- Created: 2026-06-17T09:14:35+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Партнёр в карточке компании → ссылка на Яндекс.Карты → парсинг → аудит → ссылка на аудит в карточке партнёра → синхронизация в prospectingleads на этап Кандидаты; исключить партнёров жилых комплексов; добавить signup from audit context.

## Acceptance criteria
- AC1: Partner cards can store source company, partner identity, Yandex Maps match state, parse state, public audit URL, and linked lead id.
- AC2: Residential-complex partners are explicitly skipped and are not synced into leads.
- AC3: Non-residential partner cards with a confirmed/found Yandex Maps URL can be synced into `prospectingleads` with `intent=partnership_outreach`, candidate-like status, and source-company metadata.
- AC4: Partner cards can enqueue parsing through the existing parsequeue/shadow-business flow.
- AC5: Partner cards can generate a public audit and store `audit_public_url`/`audit_slug`; public audit payload carries partnership signup context.
- AC6: Batch processing reports found/ambiguous/not_found/skipped/synced/parsed/audited/failed counts.

## Constraints
- Do not modify production data.
- Use Alembic for schema changes.
- Reuse `prospectingleads`; do not introduce a second outreach lead pipeline.
- Keep risky external sends/publishing out of scope.

## Non-goals
- Frontend UI for partner-card management.
- Production enrichment run for Весёлая расчёска, Органика, Новамед.
- Provider credentials/config changes.

## Verification plan
- Build: `python3 -m py_compile src/api/admin_prospecting.py alembic_migrations/versions/20260617_add_partnership_partner_cards.py`
- Unit tests: `python3 -m pytest -q tests/test_partnership_partner_cards.py tests/test_admin_prospecting_audit_payload.py tests/test_prospecting_service_normalize.py`
- Integration tests: not run against live DB; no production data approval.
- Lint: py_compile plus targeted tests.
- Manual checks: inspect endpoint docs and diff.
