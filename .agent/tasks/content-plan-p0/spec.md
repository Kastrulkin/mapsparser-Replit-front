# Task Spec: content-plan-p0

## Metadata
- Task ID: content-plan-p0
- Created: 2026-04-30T09:34:17+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Внедрить P0 контент-план в Новости и сторис: schema, policy, context, skeleton generation, API, UI вкладка, draft->usernews linkage

## Acceptance criteria
- AC1: Пользователь в разделе `Работа с картами → Новости и сторис` может открыть вкладку `Контент-план`, собрать контент-план для текущего бизнеса или сетевого scope, увидеть tariff-aware горизонты `30/60/90`, сгенерировать skeleton плана, отредактировать item, сгенерировать draft и создать запись в `usernews`.

## Constraints
- Соблюдать текущий Docker/Postgres runtime и структуру проекта.
- Не ломать существующий генератор новостей и историю новостей.
- Ограничение по тарифам должно проверяться и на frontend, и на backend.

## Non-goals
- Автопубликация новостей.
- Drag-and-drop календарь.
- Bulk actions и learning loop.
- Полный rollout на прод в этой итерации.

## Verification plan
- Build: `npm run build`
- Unit tests: `python3 -m pytest -q tests/test_content_plan_policy.py tests/test_content_plan_generation.py`
- Integration tests: точечные не запускались в этой итерации
- Lint: отдельный линтер не запускался, используется `python3 -m py_compile`
- Manual checks: проверить наличие вкладки `Контент-план` и сценариев item actions после локального запуска
