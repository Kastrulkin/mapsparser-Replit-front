# Task Spec: beauty-service-quality-audit-stage5-20260505

## Metadata
- Task ID: beauty-service-quality-audit-stage5-20260505
- Created: 2026-05-05T16:08:00+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- README.md
- AGENTS.md
- agents/autonomous_development_brief.md

## Original task statement
Этап 5: аудит и управление качеством услуг. Добавить backend endpoint `/api/services/seo-audit` со сводкой качества, UI фильтр “Требуют доработки” и причины проблем, повторную генерацию с причиной, Telegram-сводку.

## Acceptance criteria
- AC1: Backend endpoint `/api/services/seo-audit` returns totals for all services, good, needs_review, fallback, missing SEO keywords, weak-only matches, guardrail failures, and no-keywords.
- AC2: `/dashboard/card` shows a quality summary and supports filtering services that require review.
- AC3: Each problematic service displays concrete reason labels such as lost keyword, weak match only, fallback, no SEO keywords, unchanged draft, or guardrail reason.
- AC4: Re-generation of problematic services sends a reason-aware instruction to the service optimization prompt.
- AC5: Telegram exposes a concise service quality summary and a way to trigger service optimization flow.
- AC6: Regression tests cover backend quality classification and frontend quality helpers.

## Constraints
- No database schema migration.
- No production data mutation.
- Keep implementation incremental and reuse existing service list/optimization flows.
- Avoid adding new `as` typecasts in changed code.

## Non-goals
- Full background batch worker for automatic regeneration.
- Persisting quality audit snapshots.
- Fixing unrelated global TypeScript errors.

## Verification plan
- Backend tests: `./venv/bin/python -m pytest -q tests/test_service_keyword_scoring.py tests/test_beauty_service_optimization.py`
- Backend compile: `python3 -m py_compile src/core/service_keyword_scoring.py src/api/services_api.py src/telegram_bot.py src/main.py`
- Frontend targeted test: `cd frontend && ./node_modules/.bin/sucrase-node scripts/test-card-services-logic.ts`
- Frontend production build: `cd frontend && npm run build:all`
- Informational TypeScript check: `cd frontend && ./node_modules/.bin/tsc -p tsconfig.app.json --noEmit`
- Production checks: backend endpoint smoke, frontend bundle grep, `docker compose ps`, logs, `curl -I http://localhost:8000`.
