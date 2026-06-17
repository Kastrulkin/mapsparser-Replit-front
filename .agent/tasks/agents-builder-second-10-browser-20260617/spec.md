# Task Spec: agents-builder-second-10-browser-20260617

## Metadata
- Task ID: agents-builder-second-10-browser-20260617
- Created: 2026-06-17T15:33:55+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Browser-use проверить 10 новых сценариев конструктора пользовательских агентов, пройти путь клиента, исправить UX/понимание и задеплоить

## Acceptance criteria
- AC1: Browser-use прогоняет 10 новых пользовательских сценариев создания агентов на `/dashboard/agents`.
- AC2: Конструктор не задаёт очевидно лишние уточнения и не уводит сценарии в чужие домены: лиды, Google Sheets, письма, отзывы или Telegram без явного запроса.
- AC3: Видимый preview показывает пользовательские источники и результат: финансы LocalOS, клиенты, точки сети, партнёрские ответы, дайджест проблем.
- AC4: Исправления покрыты регрессионными тестами, задеплоены на `localos.pro`, проверены браузером.

## Constraints
- Не менять production data.
- Не включать в коммит unrelated dirty changes.
- Для backend использовать partial deploy `src/services/*` и restart `app worker`.
- Для frontend использовать partial deploy `frontend/dist` в `app` container.

## Non-goals
- Не создавать реальные пользовательские агенты и не выполнять внешние отправки.
- Не перестраивать весь UI конструктора сверх исправлений понимания задачи и пользовательских labels.

## Verification plan
- Build: `npm --prefix frontend run build`.
- Unit tests: `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`.
- Manual checks: browser-use на prod для проблемных сценариев: счета, карточки клиентов, расходы, отзывы по филиалам, контент из отзывов, реактивация клиентов, партнёрские ответы, дайджест проблем.
- Server checks: `docker compose ps`, `curl -I http://localhost:8000`, app logs after browser pass.
