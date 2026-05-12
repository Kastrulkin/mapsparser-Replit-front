# Task Spec: finance-finish-plan-20260512

## Metadata
- Task ID: finance-finish-plan-20260512
- Created: 2026-05-12T16:33:44+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Добить оставшиеся пункты плана финансового модуля: CRM schedules/resources, действия LocalOS из рекомендаций, импорт UX, проверки, commit/push/deploy readiness

## Acceptance criteria
- AC1: Finance recommendations include concrete LocalOS next actions with valid dashboard routes.
- AC2: CRM adapter layer can represent schedules/resources and normalize available workplace time.
- AC3: Import wizard prevents importing stale/unverified mappings and explains the flow.
- AC4: Documentation describes the final CRM/resource validation checklist.
- AC5: Targeted finance tests, lint and frontend production build pass.

## Constraints
- Keep the finance module incremental; do not introduce full ERP/BI scope.
- Do not change production data in local verification.
- Do not add global CRM assumptions beyond the adapter contract.

## Non-goals
- Real CRM credentials or live CRM sync for a customer.
- New database schema beyond the migration already prepared for finance stage 1.
- Large redesign of the finance screen.

## Verification plan
- Build: frontend production build.
- Unit tests: finance KPI, imports, CRM adapter tests.
- Integration tests: CRM preview/normalization covered by fixture tests.
- Lint: targeted frontend finance components.
- Manual checks: local browser smoke for route accessibility; auth gate expected without login.
