# Task Spec: beauty-service-seo-keyword-stage2-20260505

## Metadata
- Task ID: beauty-service-seo-keyword-stage2-20260505
- Created: 2026-05-05T14:21:04+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- agents/autonomous_development_brief.md
- README.md

## Original task statement
Этап 2: продолжить план после beauty stage 1. Улучшить SEO-проверку ключей и словоформ на /dashboard/card: exact/normalized/close/missing, beauty словарь близких форм, убрать false negative "SEO-ключи не найдены". Дополнительно усилить guardrails по результатам ручной проверки, чтобы beauty/cosmetology генерация не добавляла неподтвержденные зоны/медицинские обещания.

## Acceptance criteria
- AC1: Frontend keyword matching for service suggestions distinguishes exact, normalized, and close beauty matches.
- AC2: Existing UI helper `getMatchedKeywords` no longer returns empty for obvious Russian wordforms and close beauty synonyms.
- AC3: Beauty guardrails reject unconfirmed medical claims and added treatment zones in generated names/descriptions.
- AC4: Implementation stays scoped to beauty service optimization and /dashboard/card service helpers, without schema changes; any production cleanup must be targeted, backed up, and limited to bad generated service suggestions.
- AC5: Regression checks cover beauty keyword matching and live-log guardrail failure pattern.

## Constraints
- Do not make beauty rules global for all business types.
- Do not change database schema.
- Do not modify production data except targeted cleanup of bad generated service suggestions after explicit user approval and CSV backup.
- Follow repository code standard: no typecasts and no `as` in new code.

## Non-goals
- Full morphological NLP service integration.
- Full UI redesign of the services table.
- Broad cleanup of unrelated frontend TypeScript errors.

## Verification plan
- Backend unit tests: `./venv/bin/python -m pytest -q tests/test_beauty_service_optimization.py`
- Backend compile check: `python3 -m py_compile src/core/beauty_service_optimization.py src/core/service_optimization_verticals.py src/main.py`
- Frontend targeted regression: `cd frontend && ./node_modules/.bin/sucrase-node scripts/test-card-services-logic.ts`
- Frontend typecheck: `cd frontend && ./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` as informational because the current repo has pre-existing unrelated TS errors.
- Production verification: `docker compose ps`, app logs, `curl -I http://localhost:8000`, targeted backend guardrail smoke, and frontend bundle dictionary check.
