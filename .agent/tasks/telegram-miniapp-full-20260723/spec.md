# Task Spec: telegram-miniapp-full-20260723

## Metadata
- Task ID: telegram-miniapp-full-20260723
- Created: 2026-07-23T20:21:13+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Довести LocalOS Telegram Mini App до полного scope-aware управления ежедневными сценариями бизнеса, сети и платформы с preview/confirm, уведомлениями, E2E, commit/push/deploy

## Acceptance criteria
- AC1: Bootstrap и каждый mobile API повторно разрешают business/network/platform scope; переданный клиентом business_id не определяет цели.
- AC2: Сегодня, Задачи, Отзывы и Оператор работают на реальных данных; история Оператора восстанавливается, задачи показывают progress/retry или честный недоступный статус.
- AC3: Отзывы поддерживают единые counts/list filters, выбор, persisted preview, confirm/idempotency, редактирование, копирование и ручную отметку публикации.
- AC4: Карточки, Контент и Услуги имеют нативные мобильные list/detail/review сценарии; изменения проходят persisted preview/confirm либо остаются явно read-only при отсутствии provider adapter.
- AC5: Финансы и Партнёрства имеют нативные очереди и безопасные ежедневные действия; импорт/отправка/массовость требуют preview и подтверждения.
- AC6: ИИ-сотрудники показывают blueprint/run/progress/result/approval; платный запуск требует preview, подтверждение и идемпотентность.
- AC7: Настройки доступны по текущему scope, Диагностика доступна только суперадмину; технические метрики не попадают в обычные саммари.
- AC8: Capability manifest показывает только available или осмысленные read_only модули; hidden модули не рендерятся и не открываются deep link.
- AC9: Telegram `/start` остаётся коротким, MenuButton открывает Mini App, scope/object deep links перепроверяются сервером, повторные callbacks безопасны.
- AC10: Frontend проходит 360x800 и 393x852, keyboard/safe-area/back/offline/error/stale проверки; нет desktop-переходов.
- AC11: Backend tests покрывают три роли, scope tampering, counts/list, pagination, preview expiry/confirm/idempotency/mass targets и approval bypass.
- AC12: Изменения закоммичены, отправлены в GitHub и GitVerse, частично развернуты по runbook; production smoke и свежая независимая проверка успешны.

## Constraints
- PostgreSQL/Docker runtime; SQLite не используется.
- Никаких изменений production-данных без отдельного разрешения; schema только Alembic и с backup.
- Publish/send/payment/delete/import/apply/bulk/provider-write требуют review и manual confirm вне AI prompt.
- DeepSeek маршрутизирует и готовит preview, но не подтверждает действие.
- Не заявлять provider write, которого нет; использовать copy/manual publication boundary.
- Сохранять текущие пользовательские и параллельные изменения в dirty worktree/server.
- Не использовать TypeScript type casts (`as`) и не вводить второй доменный runtime.

## Non-goals
- Автономная внешняя публикация без реального provider adapter.
- Переписывание существующих desktop API и бизнес-логики.
- Несвязанный редизайн desktop-кабинета.
- Производственные изменения бизнес-данных во время проверки.

## Verification plan
- Build: `npm --prefix frontend run build`; Python compile для изменённых модулей.
- Unit tests: mobile scope/actions/modules/reviews/operator/task/notification тесты.
- Integration tests: Flask test client + PostgreSQL/Docker там, где нужен runtime; production unauth/auth-safe smoke без мутаций.
- Lint: `git diff --check`, отсутствие новых casts/transition-all, targeted ESLint если baseline позволяет.
- Manual checks: Browser 360x800 и 393x852; review preview; each manifest module; BackButton; production compose/logs/curl/endpoints.
