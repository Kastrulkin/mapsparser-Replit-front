# Task Spec: telegram-bot-phase1

## Metadata
- Task ID: telegram-bot-phase1
- Created: 2026-04-21T14:13:35+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Telegram bot phase 1: guest/client mode, audit intake, link normalization, feature request flow, groundwork for partnership entrypoint

## Acceptance criteria
- AC1: Непривязанный пользователь Telegram видит guest-меню вместо bind-only заглушки и может запустить быстрый аудит карточки из чата.
- AC2: Входящие ссылки на карты проходят нормализацию и мягкую валидацию; бот принимает поддерживаемые ссылки и возвращает понятную ошибку для неподдерживаемых.
- AC3: Привязанный пользователь видит в Telegram новые client-control точки входа для партнёрств и запроса автоматизации, а запрос автоматизации сохраняется в БД.
- AC4: Изменения задеплоены на production backend: новая таблица применена миграцией, `app/worker` подняты, runtime Telegram bot использует обновлённый source file.

## Constraints
- Не ломать существующий Telegram control flow для привязанных пользователей.
- Не вводить новый отдельный Telegram-бот; расширять существующий `src/telegram_bot.py`.
- Не дублировать логику нормализации ссылок, а переиспользовать текущий backend pipeline.
- Production schema менять только через Alembic и с резервной копией БД.

## Non-goals
- Полноценный compare-with-competitor flow в этом этапе не обязателен; допускается placeholder.
- Полный prospecting UI в Telegram не переносится; нужен только краткий entrypoint/status.
- Инфраструктурный обход блокировки Telegram API не входит в этот кодовый этап.

## Verification plan
- Build:
  - `PYTHONPATH=src python3 -m py_compile src/telegram_bot.py src/services/telegram_lead_intake.py src/services/bot_feature_requests.py`
- Unit tests:
  - `PYTHONPATH=src python3 - <<'PY' ... parse_map_links_from_text(...) ... PY`
- Integration tests:
  - Production deploy of changed backend files only
  - `cd /opt/seo-app && docker compose ps`
  - `cd /opt/seo-app && docker compose logs --since 5m app`
  - `cd /opt/seo-app && curl -I http://localhost:8000`
  - `cd /opt/seo-app && docker compose exec -T postgres psql -U beautybot -d local -c "SELECT version_num FROM alembic_version;"`
  - `cd /opt/seo-app && docker compose exec -T postgres psql -U beautybot -d local -c "SELECT to_regclass('public.botfeaturerequests');"`
- Lint:
  - Python syntax compile as narrow lint gate
- Manual checks:
  - import helper functions inside server runtime venv
  - inspect runtime bot log after restart attempt
