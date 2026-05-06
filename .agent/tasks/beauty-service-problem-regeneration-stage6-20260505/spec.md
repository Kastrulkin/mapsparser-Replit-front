# Task Spec: beauty-service-problem-regeneration-stage6-20260505

## Metadata
- Task ID: beauty-service-problem-regeneration-stage6-20260505
- Created: 2026-05-05T17:35:09+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- README.md

## Original task statement
Этап 6: управляемая автоперегенерация проблемных услуг. Backend endpoint POST /api/services/regenerate-problematic, async job, UI кнопка и статус, Telegram-кнопка, защита от бесконечных циклов, история качества в существующий ledger/timeline без сложной новой схемы.

## Acceptance criteria
- AC1: Backend exposes `POST /api/services/regenerate-problematic` and job status endpoint; request selects only audit `needs_review` services and limits to 10 per run.
- AC2: Regeneration runs in a background job, passes audit reasons into existing service optimization, and returns/report tracks fixed, failed, manual review, and remaining counts.
- AC3: Repeated failed services are not regenerated forever; after the configured attempt limit they are marked for manual review in the job result.
- AC4: UI has a "Перегенерировать проблемные" control with "до 10 за запуск" context, polls job status, and refreshes services after completion.
- AC5: Telegram `/services_audit` card menu has a "Перегенерировать проблемные" button that starts the same backend job and replies with a short status.
- AC6: Quality history is recorded without a new complex DB schema, using existing AI learning/audit event storage.

## Constraints
- No production data cleanup or manual DB mutation during implementation.
- No schema migration for this stage.
- Keep changes scoped to service quality regeneration.
- Preserve existing `/api/services/optimize` behavior and reuse it rather than refactoring the whole optimizer.

## Non-goals
- Persistent cross-restart job queue.
- Full service quality history UI.
- Automatic authenticated test run against a real customer business.

## Verification plan
- Build: `npm run build:all`.
- Unit tests: `python3 -m pytest -q tests/test_beauty_service_optimization.py tests/test_service_keyword_scoring.py tests/test_service_problem_regeneration.py`.
- Integration checks: deploy changed backend files and frontend dist, verify route auth gates, app logs, Telegram service, and frontend bundle strings.
- Lint/compile: local `python3 -m py_compile`; runtime container source compile via `compile(...)` because `/app/src` is read-only for pycache.
