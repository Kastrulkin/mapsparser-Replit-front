# Task Spec: finance-crm-confirmed-import-resources-stage16-17-20260512

## Metadata
- Task ID: finance-crm-confirmed-import-resources-stage16-17-20260512
- Created: 2026-05-12T15:40:49+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этапы 16-17: безопасный импорт после CRM preview и schedule/resources mapping

## Acceptance criteria
- AC1: CRM sync cannot write data until the user has run preview and sends the matching fresh preview token.
- AC2: If CRM data changes after preview, sync refuses to import and asks for a new preview.
- AC3: CRM appointments with resource/workplace fields produce workplace finance rows with booked minutes and revenue.
- AC4: Existing finance CRM, import, and KPI tests keep passing.
- AC5: Finance CRM panel makes the safe flow clear: preview first, then confirmed import.

## Constraints
- Keep existing DB tables and import pipeline.
- Do not add real provider credentials or destructive data operations.
- Preserve current YCLIENTS/Altegio adapter surface.

## Non-goals
- Full live CRM authentication test without partner/user tokens.
- New Alembic migration.
- Full schedule availability sync when provider schedule payload is unavailable.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: `python3 -m pytest tests/test_finance_crm.py -q`.
- Integration tests: `python3 -m pytest tests/test_finance_crm.py tests/test_finance_imports.py tests/test_finance_kpis.py -q`.
- Lint: `npm exec -- eslint src/components/FinanceCrmPanel.tsx` in `frontend`.
- Manual checks: review backend preview-token guard and UI button state.
