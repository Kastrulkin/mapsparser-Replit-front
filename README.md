# LocalOS - операционный слой для локального бизнеса

## Описание

LocalOS помогает владельцам и управляющим локального бизнеса держать под контролем то, что влияет на заявки и выручку: карточки на картах, услуги, отзывы, новости и контент, финансы, средний чек, партнёрства, локации и supervised automation.

Система начиналась как SEO-анализатор карточек, но текущий продукт уже работает как операционный слой: находит слабые места, предлагает конкретные действия, готовит черновики и изменения, проводит рискованные операции через ручное подтверждение и сохраняет историю результата.

**Целевая аудитория**: владельцы и управляющие локальных бизнесов, салоны красоты, мастера, студии, сети локаций, специалисты по локальному SEO, а также внутренние и внешние AI-агенты, которым нужен безопасный доступ к рабочим процессам бизнеса.

**Инвариант продукта**: публикации, внешние отправки, массовые действия, платежи, изменения в сторонних системах и действия от имени бизнеса проходят через явное подтверждение человека. LocalOS автоматизирует подготовку, проверку и контролируемое выполнение, но не должен описываться как полностью автономная система публикаций или платежей.

## Возможности

### Карты и аудит карточки
- Парсинг и обновление данных карточек: название, адрес, рейтинг, отзывы, услуги, фото, публичные поля и метрики.
- Поддержка Яндекс/Яндекс.Бизнес, Google Business Profile, 2ГИС и Apify-пайплайнов там, где конкретный источник реализован.
- Аудит карточки, вертикальные профили качества, gap-анализ, рекомендации, публичные audit-offer/sales-room страницы и история изменений.
- Очередь парсинга, статусы задач, retry/recovery, captcha/error visibility и smoke-проверки для надёжности.
- Сетевой режим: родительский бизнес, локации, network dashboard, network-wide reviews и история метрик.

### Услуги и меню услуг
- Управление услугами, категориями, ценами, описаниями, SEO-вариантами и источниками данных.
- Оптимизация названий и описаний услуг через suggestions, preview и явное подтверждение.
- Рабочее сокращение меню услуг: LocalOS предлагает группы похожих услуг, пользователь редактирует итоговые названия/категории/описания, затем применяет изменения вручную.
- При группировке исходные услуги мягко архивируются через `is_active = false`, новые объединённые услуги создаются в LocalOS; внешние карты не меняются автоматически.
- Для салонов красоты поддерживаются практические паттерны группировки: лазерная эпиляция, инъекционная косметология, волосы, рубцы, перманентный макияж, подология и акции как отдельный контур.

### Отзывы и репутация
- Хранение внешних отзывов, подсчёт unanswered/with-response, карточные сигналы репутации и freshness.
- Генерация черновиков ответов на отзывы, bulk reply drafts и история подготовленных ответов.
- Ручная публикация: LocalOS помогает скопировать/пометить ответ как опубликованный, но не должен обещать автономную публикацию на карты без реализованного provider write flow и approval.

### Контент, новости и публичные материалы
- Генерация черновиков новостей для карт, social post drafts, content history и работа с контент-планами.
- VK-сообщество можно подключить ключом с правом на стену для контролируемой публикации подтверждённых текстовых постов. Фото пока проходят отдельный supervised flow; подключение и подготовка поста сами по себе ничего не публикуют.
- Разделение обычных услуг и акций/сезонных предложений там, где это поддержано пользовательским workflow.
- Публичные статьи, кейсы, документы, discovery pages, AI visibility content и конверсионные audit/sales-room материалы.
- Business website и контекст бизнеса используются как входные данные для генерации и рекомендаций.

### Финансы, средний чек и подписки
- Финансовый дашборд: выручка, расходы, маржа, break-even, загрузка, no-show, rebooking, история KPI и управленческие рекомендации.
- Работа со средним чеком: упаковка услуг, допродажи, диапазоны цен и сценарии роста выручки через понятное меню.
- Импорты: ручной ввод, файлы/фото, AI-нормализация, preview, duplicate checks и controlled apply.
- Агентские finance writes создаются как предложения и применяются только после approval, лимитов и audit.
- Subscription/access controls, блокировка неактивных пользователей и биллинг agent/operator actions.

### Партнёрства и supervised outreach
- Единый путь для потенциальных клиентов LocalOS и партнёров бизнеса: поиск/импорт → карточка → парсинг → аудит/matching → контактное обогащение → evidence ledger → founder-led personalization → versioned draft цепочки → approval → контролируемые касания → первый ответ.
- Лиды остаются в `prospectingleads`; `lead_workstreams` разделяет `localos_sales` и `client_partnership`, не создавая вторую CRM.
- Контакты нормализуются из карты, raw/enrich payload и официального сайта с provenance. Website collector проверяет публичные contact/about/team pages, ссылки, формы и JSON-LD.
- Telegram entity API отличает личный аккаунт, bot, broadcast channel и группы. Публичные каналы становятся источниками радара и не используются как DM-получатели; посты сохраняются как evidence.
- Поддерживаются три явных sender mode: `localos` использует подтверждённую founder story LocalOS; `partner_business` пишет от лица бизнеса через его аккаунт; `localos_for_partner` после явного разрешения бизнеса также пишет от лица этого бизнеса, но доставляет сообщение через platform-scoped аккаунт LocalOS. Во внешнем тексте `localos_for_partner` используется голос «мы ваши соседи» без упоминания LocalOS, его founder story, кейсов или коммерческого оффера; технический отправитель и разрешение сохраняются во внутреннем audit trail.
- До генерации LocalOS применяет hard gates, считает fit/signal/readiness/priority, выбирает подтверждённый offer и trust strategy и возвращает `write_now`, `observe`, `needs_contact`, `needs_sender_setup`, `needs_evidence` или `excluded` с причинами.
- LocalOS создаёт до трёх evidence-bound вариантов персонализации и проверяет removal, bridge, fact, freshness, specificity, proof integrity, human tone и один CTA. При нехватке фактов возвращается `needs_evidence`, а не общий шаблон.
- В карточке лида компактный календарь заранее показывает номер шага, абсолютные дату и время, канал и служебный статус касания; полный текст каждого шага редактируется прямо в заметной секции «История сообщений». Дата первого сообщения задаётся явно, следующие рассчитываются по интервалам; изменение текста или расписания создаёт новую версию и требует повторного approval, но само по себе ничего не отправляет.
- Автоматические adapters предусмотрены для Telegram, email и VK-сообщества. VK-отправитель подключается ключом сообщества с правом на сообщения; получатель видит фактическое имя и аватар сообщества. Право отправки по умолчанию выключено, а reply sync читает только диалоги фактических VK-кампаний LocalOS. Личный MAX-аккаунт можно добавить по номеру как manual sender: LocalOS готовит текст и хранит историю, но не пишет и не читает личные диалоги. WhatsApp, SMS и другие каналы пока участвуют как manual touches. Любая внешняя отправка требует approval и повторного runtime preflight; любой ответ останавливает будущие касания.
- Целевая модель VK — одно подключённое сообщество с независимыми разрешениями «Публикации» и «Аутрич». В текущей beta это ещё два отдельных binding: `externalbusinessaccounts` с правом `wall` для постов и `outreach_sender_accounts` с правом `messages` для сообщений. Один ключ сообщества можно выдать с обоими правами, но до унификации он вводится и проверяется в двух соответствующих карточках настроек.
- Публичные материалы VK можно использовать как дополнительное trust evidence: например, честно сообщить, что в сообществе публикуются практические материалы для предпринимателей. Это не заменяет lead-specific персонализацию и не скрывает фактическое имя отправителя; для platform outreach публичное название сообщества должно соответствовать LocalOS.
- Приватная `sales_room` готовится вместе с качественным черновиком и переиспользуется в отношениях. После положительного ответа создаётся черновик приглашения; публичный доступ и отправка требуют отдельных явных действий.
- В «Чатах» есть stateless аутрич-песочница: decision trace, выбор offer/trust, preview цепочки и симуляция ответа работают без production-записей и provider calls.
- Outcome events связываются со стратегией, каналом, evidence, offer и trust strategy через learning loop. История пригодна для оценки связок и будущего обучения, но автоматический fine-tuning модели не заявляется.

### Operator и Telegram control surface
- `/dashboard/operator` собирает в одну очередь действия по отзывам, новостям, услугам, партнёрствам, refresh jobs, approvals и billing visibility.
- Operator доступен через web dashboard и Telegram owner-bot как разные поверхности одного governed core.
- Утренняя сводка суперадмина показывает конкретные публикации и касания аутрича на день, разделяет реально поставленные в автоматическую очередь действия и ручные шаги и даёт прямые ссылки в рабочие разделы. Синхронизация ответов работает независимо от включения новых автоматических отправок. Человеческий ответ на касание создаёт отдельное оперативное уведомление с исходным сообщением и текстом ответа; stop-on-reply применяется до уведомления.
- Поддерживаются cached briefs, генерация черновиков, map refresh requests, retry/recovery visibility, manual publication helpers и Telegram follow-ups.
- Telegram owner-bot работает в guest/client mode. После привязки он и Mini App используют тот же Operator Core и единый масштаб `бизнес` / `сеть` / `платформа`: реальное саммари, поиск точек, избранное, approvals, безопасные переходы в сложные разделы и scope-aware уведомления.
- Telegram и внешние social API используют единый Grimbird proxy на OpenClaw после успешной сетевой проверки.

### AI-агенты и OpenClaw
- Публично это один продукт «Агенты»: простой конструктор создаёт `AgentBlueprint` с compiled workflow. `AIAgents` остаётся persona/voice и legacy chat configuration, а не вторым runtime.
- `/dashboard/agents` показывает реестр ИИ-сотрудников, тип запуска, результат, историю, версии, подключения и одно следующее действие. Типы: `one_off` (без автозапуска, можно повторить), `manual` и `scheduled`.
- Тест использует candidate version; рабочий запуск `manual`/`scheduled` использует только явно включённую active version. Версию можно проверить, активировать и вернуть предыдущую.
- Параметры каждого запуска строятся из `inputs_schema_json`; служебные поля скрыты, а backend повторно валидирует payload.
- В controlled beta run идемпотентно ставится в durable queue, выполняется worker-ом, поддерживает heartbeat, retry/recovery и polling. Preview бесплатен; working run резервирует до 2 кредитов и списывает фактическую стоимость в пределах резерва.
- Результат нормализован в `business_result`/`result_state`; approval показывается только для текущего run перед реальным внешним действием. Старые ожидания решения supersede-ятся.
- Сертифицированные beta-capabilities охватывают read/draft/safe internal write: Google Sheets read, drafts для отзывов/новостей/услуг, content-plan draft, appointments read, support export и партнёрский analysis/draft. Request-only writes не активируются как beta workflow.
- OpenClaw / ActionOrchestrator остаётся execution boundary для policy, approval, billing, audit, callbacks и recovery. Provider не является пользовательской моделью агента.
- Production остаётся cohort beta: async runtime ограничен `AGENT_BETA_BUSINESS_IDS`; scheduler включён для двух безопасных read-only canary Riderra. Четыре последовательных реальных дня обоих расписаний подтверждены 20–23 июля 2026 года; семидневный gate продолжается до 26 июля. Массовый self-service запуск пока не заявляется.

### Интеграции и внешние write-действия
- Google Business Profile подключается через OAuth; production-доступ зависит от статуса Google API approval и конкретного включённого capability.
- Для повторной заявки создан отдельный Google Cloud project `localos-gbp` (`649313441761`) и агентская организация `LocalOS`. В группу `Клиенты LocalOS` добавлена подтверждённая карточка клиента «Веселая расческа», проспект Энгельса, 154, с ролью менеджера без передачи основного владения.
- Заявка на Basic API Access отправлена 18 июля 2026 года, Google case `7-6688000041542`; заявленный срок проверки — 7–10 рабочих дней. До одобрения новый OAuth-клиент не заменяет текущий production-клиент.
- AI-agent webhooks для Telegram и WhatsApp Business API используют business-level настройки и не обходят policy/approval.
- Любой publish/send/payment/delete/bulk mutation/provider write требует явного review/approval и должен быть описан как поддержанный только после реализации, тестов и deployment checks.

### Архитектура Telegram-ботов и уведомлений

- **Глобальный бот BeautyBot (`TELEGRAM_BOT_TOKEN`)**
  - Используется по умолчанию для всех уведомлений владельцам салонов и как основной control-surface в Telegram.
  - Владелец привязывает свой Telegram к аккаунту (поле `telegram_id` в таблице `Users`).
  - Бот работает в двух режимах:
    - `guest mode`: быстрый аудит карточки по ссылке, вход с рекламы, первичный lead magnet.
    - `client mode`: меню управления LocalOS из Telegram (статус, партнёрства, feature requests, approvals и т.д.).
- **Боты конкретных бизнесов (`telegram_bot_token` в таблице `Businesses`)**
  - Нужны только если салон хочет **свой брендированный бот** для клиентов и ИИ-агента.
  - Используются в webhooks ИИ-агента (`/api/webhooks/telegram`), когда бот общается напрямую с клиентами.
  - В уведомлениях владельцу (support-запросы, бронирования) поле `telegram_bot_token` опционально: если заполнено — уведомление может уйти через бот салона, если нет — через глобальный BeautyBot.
- **Текущий production runtime**
  - Основной owner-bot запускается как `openclaw-localos-telegram-bot.service`.
  - Telegram Bot API и внешние social HTTP API направляются через Grimbird HTTP proxy на OpenClaw.
  - Telethon/userbot использует Grimbird SOCKS5 proxy.
  - На LocalOS используются private endpoints `192.168.0.177:10809` и `192.168.0.177:10808`; loopback endpoints допустимы только на OpenClaw.
- **Простой сценарий**
  - Для большинства случаев достаточно одного глобального бота BeautyBot; `telegram_bot_token` заполняется только там, где действительно нужен свой брендированный вход для клиентов/ИИ-агента.

## Технический стек

- **Backend**: Python 3.11, Flask 2.3
- **Frontend**: TypeScript, React 18, Vite 7, TailwindCSS 3.4, Radix UI, shadcn/ui
- **Парсинг**: Selenium, Playwright, BeautifulSoup, pandas
- **AI**: GigaChat API, Transformers, Hugging Face API
- **LLM routing**: GigaChat Max for Russian customer-facing copy; cohort-gated DeepSeek Pro/Flash for analysis, classification, compiler, documents and tables. Financial arithmetic, validation, approval and execution remain inside LocalOS.
- **Semantic memory**: разрешённые knowledge-документы индексируются через GigaChat Embeddings в PostgreSQL/pgvector; tenant-safe hybrid retrieval добавляет provenance-контекст для услуг, отзывов, контента и бизнес-рекомендаций. Rollout и ограничения описаны в `docs/SEMANTIC_MEMORY_ROLLOUT.md`.
- **Инфраструктура**: Docker, Docker Compose, Nginx, systemd, venv (для локальных тестов)
- **База данных (runtime)**: PostgreSQL 16 в Docker
  - **Legacy**: SQLite (`src/reports.db`) используется только для старых отчётов и вспомогательных скриптов
  - **Основные таблицы (в PostgreSQL - имена в нижнем регистре)**: users, businesses, userservices, parsequeue, cards, externalbusinessaccounts, businessmaplinks, businessmetricshistory, externalbusinessstats, externalbusinessreviews; AIAgents, AIAgentConversations, AIAgentMessages, Bookings
  - **Иерархия**: Users → Businesses → все остальные данные (все привязано к `business_id`)
  - **AI/communication tables**: `AIAgents`, `AIAgentConversations`, `AIAgentMessages`, `agent_blueprints`, `agent_runs`, `agent_approvals` и связанные runtime/audit таблицы
  - **Безопасность**: Alembic migrations, production backups перед schema changes, tenant scope, approval/audit boundaries
- **Внешние интеграции**: Яндекс.Бизнес, Google Business Profile, 2ГИС (с шифрованием auth_data)

### Авторизация и блокировка пользователей (PostgreSQL)

- В таблице **users** используются флаги:
  - **`is_active`** (BOOLEAN, по умолчанию TRUE) — блокировка аккаунта (например, при неоплате); при `FALSE` вход и доступ к API запрещены.
  - **`is_verified`** (BOOLEAN, по умолчанию TRUE) — верификация пользователя (email и т.п.); используется в логике авторизации и отображении.
  - **`is_superadmin`** (BOOLEAN, по умолчанию FALSE) — доступ ко всем бизнесам и админ-функциям.
- **Поведение API:**
  - **401 Unauthorized** — неверные логин/пароль, отсутствующий или недействительный токен.
  - **403 Forbidden** — пользователь заблокирован (`is_active = FALSE`); в теле ответа: `{"error": "account_blocked", "message": "user is blocked"}`.
- Миграции, добавляющие эти колонки, применяются при старте контейнеров (Flask-Migrate в entrypoint). После обновления кода с новыми миграциями выполните: `docker compose up -d --build`.

## Порты и сервисы

📖 **Подробная информация**: см. [PORTS_AND_SERVICES.md](./PORTS_AND_SERVICES.md)

| Сервис | Порт | Описание |
|--------|------|----------|
| Фронтенд (Dev) | `3000` | Vite dev server |
| Фронтенд (Prod) | `80/443` | Nginx (статический фронтенд) |
| Бэкенд API | `8000` | Flask API сервер |
| Бот управления | - | `openclaw-localos-telegram-bot.service` (host runtime polling) |
| Бот обмена отзывами | - | Systemd сервис (polling) |
| Grimbird HTTP proxy | `192.168.0.177:10809` | Telegram Bot API и внешние social HTTP API с LocalOS host |
| Grimbird SOCKS5 proxy | `192.168.0.177:10808` | Telethon/MTProto с LocalOS host |

## Документация

- 📖 [Порты и сервисы](./PORTS_AND_SERVICES.md) — схема портов, проверка процессов
- 🔄 [Алгоритм обновления](./ALGORITHM_UPDATE.md) — порядок применения изменений
- 🧭 [Product Operating Model](./PRODUCT.md) — продуктовый канон LocalOS, роли пользователей, agent model и approval-инварианты
- 🎛️ [Product Design Rules](./DESIGN.md) — процесс audit → distill → shape → implement → harden → polish и правила product UI
- 🤖 [Agents Product UI Audit](./docs/AGENTS_PRODUCT_UI_AUDIT.md) — рабочий аудит `/dashboard/agents` как product cockpit
- 🧭 [LLM Routing Rollout](./docs/LLM_ROUTING_ROLLOUT.md) — безопасное включение, пилотные метрики и rollback GigaChat / DeepSeek
- 🧪 [Agents Beta Production Status](./docs/AGENTS_BETA_PRODUCTION_STATUS.md) — датированные production-доказательства, pilot-метрики и открытые gates
- 🎨 [Брендбук личного кабинета LocalOS](./docs/DASHBOARD_DESIGN_BRANDBOOK.md) — дизайн-паттерны, UX-принципы и каноничные dashboard-примитивы
- 🤖 [Настройка Telegram-ботов](./TELEGRAM_BOTS_SETUP.md) — установка и запуск ботов
- 🌐 [Grimbird Proxy Runbook](./docs/TELEGRAM_PROXY_RUNBOOK.md) — маршруты Telegram и внешних API через OpenClaw
- 🏗️ [Архитектура БД](./database_schema_design.md) — структура базы данных
- 📊 [Полная структура БД](./database_schema.md) — детальная документация (PostgreSQL)
- 🔧 [План оптимизации БД](./DB_OPTIMIZATION_PLAN.md) — исторический план оптимизации схемы
- 🔗 [Настройка внешних интеграций](./INTEGRATIONS_SETUP.md) — Яндекс.Бизнес, Google Business, 2ГИС, VK-публикации и VK-аутрич
- 🗺️ [Google Business Profile: production и повторная заявка](./docs/GOOGLE_BUSINESS_PROFILE_LOCALOS_SETUP.md) — OAuth-клиенты, агентская организация, case Google и checklist после одобрения
- 🤝 [Roadmap поиска партнёрств](./docs/PARTNERSHIP_ROADMAP_BACKLOG.md) — P0–P10, включая fallback-режим импорта партнёров файлом
- ✉️ [Founder-led мультиканальный аутрич](./docs/OUTREACH_SYSTEM.md) — поиск, контакты, сигналы, sender identity, персонализация, approval, stop-on-reply и learning loop
- 🧩 [Архитектура агентов LocalOS v1](./docs/LOCALOS_AGENT_ARCHITECTURE_V1.md) — канон Agent/Persona/Blueprint/Compiled Workflow/OpenClaw и инвентаризация существующих блоков
- 🧑‍💼 [Модель интерфейса агентов Compiled AI](./docs/AGENTS_INTERFACE_MODEL_COMPILED_AI.md) — агенты как ИИ-сотрудники, IA раздела и путь create → test → approve → enable → running
- 🤖 [10 популярных примеров агентов](./docs/agents/popular-account-examples.md) — стартовый набор draft/templates для каждого аккаунта
- 🧠 [Compiled AI Architecture v1](./docs/LOCALOS_COMPILED_AI_ARCHITECTURE_V1.md) — текущий DSL, version/run contracts, capability certification, queue/billing runtime и rollout gates
- 🧠 [Compiled AI Envelope over OpenClaw v1](./docs/LOCALOS_COMPILED_AI_ENVELOPE_OVER_OPENCLAW_V1.md) — LocalOS как product/policy/billing/audit слой поверх OpenClaw runtime
- 🧭 [Политика аудита карточки](./docs/CARD_AUDIT_IDEAL.md) — идеал карточки, пороги, веса и правила gap-анализа
- 🏨 [Hospitality-аудит карточки](./docs/CARD_AUDIT_HOSPITALITY_V1.md) — отдельный reasoning-режим для hotel/resort/apartment stay
- 🧠 [Система audit-profile](./docs/CARD_AUDIT_PROFILE_SYSTEM_V1.md) — общая модель сильного аудита по вертикалям: hospitality, wellness, medical, beauty и др.
- 🤖 [LocalOS for AI Agents](./docs/agents/index.md) — краткий вход для AI-агентов: доступные действия, approval, gaps и machine-readable manifests

### Поиск партнёрств: geo-search и fallback-импорт

Партнёрский поток поддерживает geo-search через доступный provider и сохраняет каноничный fallback на случай недоступности или ограничений provider:
- список партнёров загружается в LocalOS файлом (`CSV/JSON/JSONL`);
- LocalOS выполняет валидацию/очистку и хранит source of truth + статусы;
- OpenClaw получает уже подготовленные `seed_items` для capability-вызовов (`search/enrich/draft`) без самостоятельных бизнес-решений.

## Установка

### Через Docker (основной сценарий)

1. Установите Docker и Docker Compose.
2. Клонируйте репозиторий на машину (dev или сервер).
3. Создайте `.env` в корне проекта (переменные для PostgreSQL и секреты; пример — ниже в секции «Docker»).
4. Запустите сервисы:
   ```bash
   docker compose up -d --build
   ```
5. Backend будет доступен на `http://localhost:8000` (или на соответствующем хосте/порте сервера).

Детали конфигурации контейнеров и миграций — в разделе **Docker** ниже.

### Локальная разработка без Docker (опционально)

Этот режим нужен только для отладки отдельных модулей (например, unit‑тестов) без поднятия контейнеров.

1. Клонируйте репозиторий.
2. Создайте и активируйте виртуальное окружение:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements.test.txt
   ```
3. Для Playwright‑парсера (если запускаете его с хоста) выполните:
   ```bash
   python3 -m playwright install
   ```

Запуск всего приложения (API, воркер, БД) в этом режиме **не рекомендуется**; для runtime используйте Docker.

## Запуск

### Через Docker (рекомендуется)

```bash
docker compose up --build        # сборка и запуск в foreground
docker compose up -d             # запуск в фоне
```

- Backend API: `http://localhost:8000`
- Миграции применяются автоматически в entrypoint контейнеров `app` и `worker`.

### Локальные тесты без Docker

Для быстрого прогона unit‑тестов (в том числе проверки валидации результата парсинга):

```bash
source venv/bin/activate
pytest -q tests/test_parsed_payload_validation.py
```

Для полного прогона тестов (A–I) и gate‑тестов `/api/client-info` см. раздел **Тестирование** ниже и секцию «Gate‑тесты и smoke в Docker».

## Docker

Окружение одинаково запускается локально и на сервере: приложение и PostgreSQL в разных контейнерах, данные БД хранятся в volume.

**Сервисы:**
- **postgres** — PostgreSQL 16, данные в volume `pgdata`
- **app** — backend (Flask, порт 8000); при старте ждёт Postgres и выполняет `flask db upgrade`
- **worker** — воркер очереди (тот же образ); при старте тоже выполняет миграции, затем запуск воркера

### Frontend Dist Source Of Truth

- Канонический хостовый путь для production frontend: `frontend/dist`
- Канонический runtime path в контейнере `app`: `/app/frontend/dist`
- Flask раздаёт SPA именно из `FRONTEND_DIST_DIR` и в Docker Compose он должен указывать на `/app/frontend/dist`
- Для фронтенд-hotfix используйте:
  - локальная проверка: `scripts/verify_frontend_dist_integrity.sh frontend/dist`
  - выкладка: `scripts/deploy_frontend_dist.sh --build`

Не используйте как production source of truth:

- `dist/` в корне репозитория
- старый внешний web-root вне Docker runtime
- временные каталоги `tmp_frontend_dist*`

Миграции (Flask-Migrate) применяются автоматически в entrypoint контейнеров app и worker. Таблицы (в т.ч. `parsequeue`) создаются при первом запуске.

**Локальный запуск:**

```bash
# Сборка и запуск в foreground
docker compose up --build

# Или в фоне
docker compose up -d
```

Backend будет доступен на `http://localhost:8000`. Проверка: `curl -s http://localhost:8000/health`.

**Запуск на сервере (VPS):**

1. Установите Docker и Docker Compose на сервер.
2. Склонируйте репозиторий (или скопируйте проект) в каталог на сервере.
3. При необходимости создайте `.env` в корне проекта:
   ```bash
   POSTGRES_USER=beautybot
   POSTGRES_PASSWORD=<надёжный_пароль>
   POSTGRES_DB=beautybot
   ```
4. Запустите:
   ```bash
   docker compose up -d --build
   ```
5. Данные PostgreSQL сохраняются в volume `pgdata`; при пересоздании контейнеров данные не теряются.

**Gate-тесты и smoke в Docker:**

Тесты запускаются **из контейнера app** (не с хоста). Для gate-тестов с testcontainers нужны test-only overrides:
- доступ к Docker daemon (в `docker-compose.test.yml` пробрасывается `/var/run/docker.sock`, задаётся `DOCKER_HOST=unix:///var/run/docker.sock`);
- `extra_hosts: host.docker.internal:host-gateway` — чтобы контейнер app мог достучаться до Postgres testcontainers;
- переменная окружения `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal`.

Отдельная команда для gate-тестов client-info:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml exec app python -m pytest -q tests/test_client_info_gate.py
```

Перед первым запуском установите тестовые зависимости в контейнере: `docker compose exec app pip install -r requirements.test.txt`.

Каноничный воспроизводимый запуск Agent и prospecting тестов, не зависящий от архитектуры локального Python:

```bash
scripts/test_agents_docker.sh
```

Скрипт монтирует текущий checkout в `/app`, поэтому пересборка image для каждой правки не нужна.

Проверка Knowledge Layer, включая применение Alembic-миграции в временном PostgreSQL:

```bash
scripts/test_knowledge_docker.sh
```

```bash
# Smoke DatabaseManager
docker compose run --rm app python scripts/smoke_db_manager.py

# Smoke client-info
docker compose run --rm app python scripts/smoke_client_info_gate.py
```

Для smoke в `DATABASE_URL` подставляется подключение к контейнеру `postgres`; убедитесь, что контейнеры postgres и app подняты (`docker compose up -d`).

**Важно:** Бизнес-логика и runtime-код не зависят от Docker; меняется только способ запуска и переменные окружения. Подробнее: [docs/DOCKER_DEPLOY.md](./docs/DOCKER_DEPLOY.md).

### Миграции (Flask-Migrate)

Схема БД управляется через Flask-Migrate (Alembic). Миграции лежат в каталоге `alembic_migrations/` (кастомные скрипты — в `migrations/`).

**Локально** (при наличии Postgres и `DATABASE_URL` в `.env`):

```bash
export FLASK_APP=src.main:app
export PYTHONPATH="$(pwd)/src:$(pwd)"
flask db upgrade
```

Создать новую миграцию после изменения моделей/схемы:

```bash
flask db migrate -m "описание"
flask db upgrade
```

**В Docker** миграции выполняются в entrypoint перед запуском app и worker; вручную:

```bash
docker compose run --rm app flask db upgrade
```

**Одноразовый перенос данных SQLite → Postgres** (когда схема в Postgres уже создана Alembic):

```bash
# В Docker: указать путь к файлу SQLite (например, смонтированный или скопированный legacy.db)
docker compose exec -e SQLITE_PATH=/app/legacy.sqlite app python scripts/migrate_sqlite_to_postgres.py

# Локально
SQLITE_PATH=./src/reports.db DATABASE_URL=postgresql://user:pass@localhost/db python scripts/migrate_sqlite_to_postgres.py

# Только счётчики, без записи
python scripts/migrate_sqlite_to_postgres.py --dry-run

# Выборочно таблицы
python scripts/migrate_sqlite_to_postgres.py --tables users,businesses,userservices
```

Подробности: комментарий вверху `scripts/migrate_sqlite_to_postgres.py`. После переноса smoke `scripts/smoke_client_info_gate.py` должен находить бизнесы (не выводить «нет ни одного бизнеса»).

### Правила работы со схемой БД и миграциями

- **Runtime не использует SQLAlchemy** — доступ к БД идёт через psycopg2. SQLAlchemy и Flask-Migrate используются только для миграций.
- **Миграции** лежат в `alembic_migrations/` (не в стандартной `migrations/`). Initial-миграция `20250207_initial_parsequeue.py` уже применена и не должна изменяться.
- **Данные в БД терять нельзя.** Вносить только минимально необходимые изменения. Ничего не удалять из существующих таблиц (users, businesses, parsequeue).
- **Изменения схемы — только через новую Alembic-миграцию:** новая ревизия; в `upgrade()` — безопасный DDL (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`); в `downgrade()` — откат только изменений этой ревизии.
- **Runtime-код** (psycopg2, SQL-запросы) не переписывать без необходимости. Не менять `entrypoint.sh`, Docker-логику и порядок запуска контейнеров.
- **Новая таблица / колонка / индекс:** сначала миграция, затем минимальная адаптация runtime-кода.
- **Исправление ошибки:** определить, DDL это или логика; DDL → миграция; логика → аккуратный патч без изменения контракта БД.
- **Обратная совместимость** с уже развёрнутой БД. Код должен быть готов к повторному `flask db upgrade` (no-op при повторном запуске).

### Backend: парсинг и внешние аккаунты (PostgreSQL)

В runtime все запросы к БД используют **имена таблиц в нижнем регистре** и плейсхолдеры **`%s`** (psycopg2). Результаты парсинга карт и синхронизаций пишутся в **cards** (source of truth), а не в MapParseResults.

- **Очередь парсинга**: таблица **parsequeue**; задачи создаются через `POST /api/admin/yandex/sync/business/<id>` (при наличии ссылки на карты или аккаунта Яндекс.Бизнес). Воркер обрабатывает задачи и сохраняет результат в **cards** через `DatabaseManager.save_new_card_version`.
- **Внешние аккаунты**: таблица **externalbusinessaccounts**; API: `GET/POST /api/business/<id>/external-accounts`. Upsert по `(business_id, source)`; при создании обязателен `auth_data` (строка или JSON-объект); в ответе `auth_data` не возвращается. В dev в ответах может быть `_debug` (tableName, saved_fields, action и т.п.).
- **2ГИС**: `POST /api/admin/2gis/sync/business/<id>` возвращает **501** с JSON `{ "success": false, "message": "2ГИС синк пока не реализован", "where": "admin_sync_business_2gis" }` (без 404 и без падения).
- **Ошибки API**: при любом исключении ответ — JSON с полями `success: false`, `error`, `error_type`; в режиме `app.debug` добавляется `traceback`. Нет ответов с телом «Критическая ошибка: 0» или HTML.

## Тестирование (PostgreSQL + HITL worker)

**Основной путь (один раз установить зависимости, затем запускать тесты):**

```bash
pip install -r requirements.test.txt
pytest -q
```

При **доступном Docker** (daemon запущен, `docker.from_env().ping()` успешен) прогоняются все gate-тесты для `/api/client-info`: **A–B–C–D–E–F–H** (с Postgres в testcontainers и применением миграций `flask db upgrade`) и статический тест **G** (проверка отсутствия PRAGMA/ClientInfo в runtime). Skip только если Docker реально недоступен. Дополнительно есть unit‑тест **I** (валидация результата парсинга), который не требует Docker и БД.

Что проверяется:

- корректное сохранение состояний `captcha / waiting / resume / expired` в таблице **parsequeue**
  (`tests/test_worker_captcha_flow.py`, `tests/test_worker_resume_flow.py`, `tests/test_worker_expired_flow.py`);
- поведение оркестратора `parser_interception.parse_yandex_card` в HITL-режиме
  (парковка/закрытие сессий, обработка `captcha_session_lost`) в `tests/test_parser_orchestrator.py`;
- gate-тесты `/api/client-info`: GET/POST по business_id, идемпотентность, пустые ссылки, GET без business_id, 404, отсутствие PRAGMA/ClientInfo в `src/`, видимость данных в новой транзакции (`tests/test_client_info_gate.py`).

Особенности:

- тесты поднимают временный PostgreSQL через `testcontainers.postgres`; боевая БД не затрагивается;
- перед gate-тестами выполняется `flask db upgrade` (таблицы users, businesses, parsequeue, businessmaplinks и др. создаются миграциями);
- каждое тестовое окружение использует свою схему `test_<uuid>` и таблицу **parsequeue**;
- Playwright в тестах не запускается — все вызовы браузера и парсера замоканы.

### Smoke-тесты

Быстрые проверки без поднятия testcontainers.

**1. Smoke-тест DatabaseManager (PostgreSQL)**

Проверяет основные методы `DatabaseManager` после миграции на Postgres: подключение, чтение пользователей/бизнесов/отчётов/услуг, версионирование карточек.

```bash
# Требуется DATABASE_URL в .env
python scripts/smoke_db_manager.py
```

Проверяется: подключение к БД, `get_user_by_email`, `get_businesses_by_owner`, `get_business_by_id`, `get_reports_by_business`, `get_services_by_business`, версионирование карточек (`save_new_card_version`, `get_latest_card_by_business`, `get_card_history_by_business`). В конце выводится счётчик вида `X/7 тестов прошли`.

**2. Smoke-тест результатов парсинга (SQLite)**

Проверяет наличие данных парсинга для тестового бизнеса (например, «Oliver»): количество услуг и отзывов в `reports.db`. Использует SQLite, не Postgres.

```bash
# Запуск из корня проекта; нужен файл reports.db в текущей директории
python tests/smoke_test_parsing_results.py
```

### Gate-тесты для /api/client-info

Входят в общий прогон `pytest -q` (см. выше). Проверяют, что эндпоинт работает только через Postgres (businessmaplinks + businesses), без PRAGMA/ClientInfo.

**Запуск gate-тестов:** A–H (с testcontainers) выполняются **внутри контейнера app**. На хосте должен быть доступ к Docker daemon; testcontainers-настройки вынесены в `docker-compose.test.yml`, чтобы production compose не монтировал Docker socket. Команда:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml exec app python -m pytest -q tests/test_client_info_gate.py
```

(Предварительно: `docker compose exec app pip install -r requirements.test.txt`.) Локально на хосте (без Docker) можно по-прежнему запускать:

```bash
pip install -r requirements.test.txt
pytest tests/test_client_info_gate.py -v
```

- **A** — GET с `business_id` → 200, ссылки из businessmaplinks.
- **B** — POST mapLinks → 200, затем GET возвращает те же ссылки.
- **C** — два одинаковых POST → в businessmaplinks ровно N строк (идемпотентность).
- **D** — POST с пустыми mapLinks → 0 строк, GET → пустой список.
- **E** — GET без business_id → данные первого бизнеса пользователя.
- **F** — GET с несуществующим business_id → 404.
- **G** — статический тест: в runtime (`src/`, без `scripts` и `migrate_*.py`) нет вхождений `PRAGMA table_info(ClientInfo)`, `FROM ClientInfo`, `INTO ClientInfo`.
- **H** — после POST данные читаются из нового соединения (проверка commit).
- **I** — unit‑тест для `parsed_payload_validation.validate_parsed_payload` и хелперов (`_has_content`, `_resolve_categories`, one‑of `title_or_name`, `quality_score`): `tests/test_parsed_payload_validation.py`. Запуск: `pytest -q tests/test_parsed_payload_validation.py` (локально в venv, без Docker и БД).

**Smoke (локальный DATABASE_URL, для dev/stage):**

```bash
# Требуется DATABASE_URL в .env
python scripts/smoke_client_info_gate.py
```

## Деплой на сервер

### 1. Server Runtime

На текущем проде `localos.pro` systemd-сервисы для `app` и `worker` не используются как основная схема запуска. Канонический runtime:

- `docker compose`
- `postgres`, `app`, `worker` как отдельные контейнеры
- frontend раздаётся Flask из `/app/frontend/dist`

Старые примеры с non-Docker runtime сохранены только как legacy-контекст и не должны использоваться как актуальная инструкция деплоя.

#### Telegram-боты
- Бот для управления аккаунтом: см. [TELEGRAM_BOTS_SETUP.md](./TELEGRAM_BOTS_SETUP.md)
- Бот для обмена отзывами: см. [TELEGRAM_BOTS_SETUP.md](./TELEGRAM_BOTS_SETUP.md)

### 2. Переменные окружения

Создайте файл `.env` в корне проекта:
```bash
# Telegram боты
TELEGRAM_BOT_TOKEN=токен_для_Beautybotpor_bot
TELEGRAM_REVIEWS_BOT_TOKEN=токен_для_beautyreviewexchange_bot

# Grimbird на OpenClaw; включать после проверки firewall/private route
TELEGRAM_HTTP_PROXY=http://192.168.0.177:10809
OUTBOUND_HTTP_PROXY=http://192.168.0.177:10809
TELEGRAM_USERBOT_PROXY=socks5://192.168.0.177:10808

# API
API_BASE_URL=http://localhost:8000

# GigaChat (для AI функций)
GIGACHAT_CLIENT_ID=ваш_client_id
GIGACHAT_CLIENT_SECRET=ваш_client_secret

# Optional DeepSeek pilot. Safe defaults keep routing disabled.
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_REASONING=deepseek-v4-pro
DEEPSEEK_MODEL_FAST=deepseek-v4-flash
LLM_ROUTER_ENABLED=false
LLM_SHADOW_MODE=false
# Maximum parallel background comparisons in each app/worker process.
LLM_SHADOW_MAX_CONCURRENCY=4
# Comma-separated business ids allowed to send public/redacted data to DeepSeek.
LLM_DEEPSEEK_BUSINESS_IDS=

# Шифрование для внешних интеграций (Яндекс.Бизнес, Google Business, 2ГИС)
# ВАЖНО: Используйте случайную строку длиной 32+ символов для продакшена!
EXTERNAL_AUTH_SECRET_KEY=ваш_секретный_ключ_для_шифрования_32_символа_минимум

# Режим тестирования внешних интеграций (без реальных запросов к кабинетам)
# Установите в 1 для тестирования с демо-данными
YANDEX_BUSINESS_FAKE=0

# SMTP (для отправки email)
SMTP_SERVER=mail.hosting.reg.ru
SMTP_PORT=587
SMTP_USERNAME=info@beautybot.pro
SMTP_PASSWORD=ваш_пароль
```

### 3. Запуск сервисов
```bash
systemctl daemon-reload
systemctl enable seo-worker
systemctl start seo-worker
systemctl enable openclaw-localos-telegram-bot
systemctl start openclaw-localos-telegram-bot
systemctl enable telegram-reviews-bot
systemctl start telegram-reviews-bot
```

### 4. Проверка работы
```bash
# Проверить все сервисы
systemctl status seo-worker
systemctl status openclaw-localos-telegram-bot
systemctl status telegram-reviews-bot
systemctl status nginx

# Проверить порты
lsof -i :8000  # Бэкенд API
lsof -i :80    # Nginx HTTP
lsof -i :443   # Nginx HTTPS
```

## Как коммитить изменения

1. **Проверьте статус**: `git status -sb`.
2. **Добавьте файлы**: `git add <путь>`. Для массового добавления используйте `git add .`.
3. **Создайте коммит**: `git commit -m "Краткое описание изменений"`.
4. **Подготовьте токен**:
   - Установите переменную окружения `export GITHUB_TOKEN=<ваш токен>`, либо
   - Однократно сохраните креды: `git config credential.helper store` и выполните `git credential fill`/`approve`.
5. **Отправьте изменения**:
   ```bash
   git push https://$GITHUB_TOKEN@github.com/Kastrulkin/mapsparser-Replit-front.git main
   ```
   или, если helper уже настроен: `git push origin main`.
6. **Безопасность**: не добавляйте токен в коммит и не храните его в репозитории. Для временных сессий можно экспортировать токен только на время пуша.

## Структура проекта

```
├── src/                    # Исходный код бэкенда
│   ├── main.py            # Flask API сервер
│   ├── worker.py          # Воркер для обработки очереди
│   ├── telegram_bot.py    # Global Telegram bot: guest/client control surface
│   ├── telegram_reviews_bot.py  # Бот для обмена отзывами
│   ├── templates/         # Шаблоны для HTML-отчётов
│   ├── services/          # Сервисы (GigaChat и др.)
│   ├── core/              # Core модули
│   │   ├── db_helpers.py  # Helper функции для БД
│   │   ├── telegram_network.py # Telegram-only proxy routing helpers
│   │   └── helpers.py     # Общие helper функции
│   ├── reports.db         # База данных SQLite (51 таблица на сервере, 46 локально)
│   └── migrate_*.py       # Миграции БД (оптимизация структуры)
├── frontend/              # Веб-интерфейс (React + Vite)
│   ├── src/              # Исходники React
│   └── dist/             # Собранный фронтенд
├── migrations/            # Миграции базы данных
├── db_backups/            # Резервные копии БД (автоматические бэкапы перед миграциями)
├── prompts/              # Промпты для AI
├── .cursor/              # Документация и правила проекта
│   └── docs/             # Архитектурные решения, верификация, упрощение
└── .env                  # Переменные окружения
```

### Структура базы данных

**Текущее состояние:**
- **51 таблица** на сервере / **46 таблиц** локально
- **Основные категории таблиц:**
  - **Пользователи и авторизация**: Users, UserSessions, UserLoginHistory
  - **Бизнесы**: Businesses, Networks, BusinessMapLinks
  - **Услуги и контент**: UserServices, UserNews, UserExamples (объединены из UserNewsExamples, UserReviewExamples, UserServiceExamples)
  - **Финансы**: FinancialTransactions, FinancialMetrics, ROIData
  - **Парсинг**: parsequeue (очередь задач), cards (результаты парсинга — source of truth в PG), externalbusinessaccounts, externalbusinessreviews, externalbusinessposts, externalbusinessphotos, externalbusinessstats
  - **AI и интеграции**: AIAgents, AIAgentConversations, ChatGPTUserSessions, TokenUsage
  - **Бронирования**: Bookings, StripePayments, CRMIntegrations
  - **Telegram**: TelegramBindTokens, ReviewExchangeParticipants
  - **Оптимизация**: BusinessOptimizationWizard, PricelistOptimizations, GrowthStages, GrowthTasks

**План оптимизации (3 этапа):**
1. ✅ **Добавление индексов** - ускорение запросов в 5-10 раз (`migrate_add_missing_indexes.py`)
2. ⏳ **Удаление дублирующих таблиц** - ClientInfo, GigaChatTokenUsage, Cards (`migrate_remove_duplicate_tables.py`)
3. ⏳ **Объединение похожих таблиц** - UserExamples уже объединены (`migrate_merge_examples_tables.py`)

**Ожидаемый результат:** 40-41 таблица (упрощение схемы, устранение дублирования)

**Принципы:**
- Все данные привязаны к `business_id` (не к `user_id`)
- `user_id` используется только для авторизации
- Суперадмин видит все бизнесы, обычные пользователи - только свои
- Автоматические бэкапы перед миграциями через `safe_migrate()`

## Ограничения и требования

- **Браузер**: Для парсинга требуется установленный Google Chrome или Chromium
- **Капча**: Если Яндекс.Карты требуют капчу — попробуйте сменить прокси или User-Agent
- **Воркер**: Обрабатывает задачи из таблицы **parsequeue** каждые 5 минут; результаты парсинга пишутся в **cards** (PostgreSQL)
- **База данных**: SQLite — для продакшена рекомендуется PostgreSQL
- **Память**: Playwright требует достаточно памяти для запуска браузера

## Обновление проекта

📖 **Подробная инструкция**: см. [ALGORITHM_UPDATE.md](./ALGORITHM_UPDATE.md)

**Кратко (РЕКОМЕНДУЕТСЯ):**

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

Канонический frontend runbook:

- `docs/FRONTEND_DEPLOY_RUNBOOK.md`

**Вручную:**
1. После product UI изменений → проверить guard `scripts/ci_gate_product_ui.sh`
2. После изменений в `frontend/src/*` → пересобрать `cd frontend && npm run build`
3. Проверить целостность `bash scripts/verify_frontend_dist_integrity.sh frontend/dist`
4. Обновить продовый dist через `bash scripts/deploy_frontend_dist.sh`
5. После backend-изменений → синхронизировать `src/` и перезапустить только нужный контейнер через `docker compose restart app` или `docker compose restart worker`

## Интеграция с внешними источниками (Яндекс.Бизнес, Google Business, 2ГИС)

### Настройка Яндекс.Бизнес

Для подключения личного кабинета Яндекс.Бизнес через админскую панель:

1. **Войдите в личный кабинет Яндекс.Бизнес** в браузере
2. **Скопируйте cookies** из браузера:
   - Откройте DevTools (F12) → вкладка "Application" (Chrome) или "Storage" (Firefox)
   - Найдите раздел "Cookies" → выберите домен `business.yandex.ru` или `yandex.ru`
   - Скопируйте все cookies в формате: `yandexuid=...; Session_id=...; yandex_login=...; и т.д.`
3. **В админской панели** (Пользователи и бизнесы → кнопка "Настройки"):
   - Вставьте cookies в поле "Cookies / Токен сессии"
   - Опционально: укажите `external_id` (ID организации в Яндекс.Бизнес) и `display_name`
   - Нажмите "Сохранить"

**Формат данных для Яндекс.Бизнес:**
- **Cookies**: строка вида `yandexuid=123456789; Session_id=abc123def456; yandex_login=user@example.com`
- **external_id** (опционально): ID организации в Яндекс.Бизнес (можно найти в URL кабинета)
- **display_name** (опционально): название организации для удобства

**Для тестирования без реальных запросов:**
- Установите в `.env`: `YANDEX_BUSINESS_FAKE=1`
- В этом режиме воркер будет использовать демо-данные вместо реальных запросов к кабинету
- Данные авторизации всё равно можно указать (они будут сохранены, но не использованы)

**Примечание:** 
- Данные авторизации (cookies) шифруются перед сохранением в БД с помощью `cryptography`
- Для продакшена обязательно установите `EXTERNAL_AUTH_SECRET_KEY` в `.env` (случайная строка 32+ символов)

### Настройка 2ГИС

Аналогично Яндекс.Бизнес:
1. Войдите в личный кабинет 2ГИС
2. Скопируйте cookies из браузера
3. Вставьте в админской панели в разделе "2ГИС"

## ❓ Troubleshooting (Решение проблем)

### Ошибка `TypeError: Failed to fetch` на фронтенде / Белый экран

**Симптомы:**
- В консоли браузера: `TypeError: Failed to fetch` при запросах к API.
- Белый экран или бесконечная загрузка дашборда.
- Backend запущен и доступен через `curl`, но фронтенд его не видит.

**Причина:**
Часто возникает на macOS, где `localhost` разрешается в IPv6 адрес `::1`, а Flask сервер слушает только IPv4 `127.0.0.1`. Vite Proxy пытается подключиться по IPv6 и получает `Connection Refused`.

**Решение:**
В файле `frontend/vite.config.ts` принудительно укажите IP `127.0.0.1` вместо `localhost`:

```typescript
// frontend/vite.config.ts
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000', // Используйте IP вместо localhost
    changeOrigin: true,
    secure: false,
  },
},
```

### Ошибка `missing_title` или зависание парсинга

**Причина:**
Яндекс часто выдает CAPTCHA, которую headless-браузер не может пройти, либо изменились селекторы на странице.

**Решение:**
1. Проверьте `worker.log`. Если видите `⚠️ Обнаружена captcha!`, откройте ссылку из лога в обычном браузере и пройдите капчу вручную.
2. Если капчи нет, но ошибка остается — возможно, Яндекс изменил верстку. Обновите селекторы в `src/yandex_maps_scraper.py`. 
