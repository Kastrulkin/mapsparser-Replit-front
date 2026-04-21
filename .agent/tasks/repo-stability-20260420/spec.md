# Task Spec: repo-stability-20260420

## Metadata
- Task ID: repo-stability-20260420
- Created: 2026-04-20T19:18:27+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- README.md

## Original task statement
Автономный stabilizing pass: найти и исправить архитектурные, логические и runtime-ошибки, чтобы проект стал устойчивее и быстрее

## Acceptance criteria
- AC1: Критичный runtime/backend source-of-truth должен быть нормализован локально: ключевые runtime-файлы и alembic revisions находятся в tracked state, а `scripts/check_backend_source_of_truth.sh` проходит без ошибок.
- AC2: Хрупкие admin-heavy фронтовые слои должны стать тоньше и устойчивее: `Dashboard.tsx` работает как orchestration-страница, а повторяющиеся detail/admin блоки вынесены или упрощены без регресса сборки.
- AC3: После изменений приложение должно успешно собираться и свежий фронтенд должен выкатываться на live без деградации базового health-check.

## Constraints
- Не делать рискованных изменений прод-данных.
- Использовать частичные выкладки вместо полного rebuild.
- Не ломать существующий outreach/admin workflow ради архитектурной чистоты.

## Non-goals
- Полная типизация всего фронтенда.
- Полная нормализация всего server git working tree за один проход.
- Большой backend schema refactor.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `python3 -m py_compile src/main.py src/worker.py src/stripe_integration.py src/api/admin_prospecting.py`
- Integration tests: `bash scripts/deploy_frontend_dist.sh` и его встроенная серверная верификация
- Lint: `cd frontend && ./node_modules/.bin/eslint src/pages/Dashboard.tsx src/components/dashboard/DashboardSections.tsx src/components/prospecting/OutreachDetailPanes.tsx src/pages/dashboard/AdminPage.tsx`
- Manual checks: live HTML должен ссылаться на новый `index-*.js`, а `curl -I http://localhost:8000` внутри deploy-пути должен возвращать `200 OK`
