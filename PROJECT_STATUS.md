# Статус проекта SEO с Реплит на Курсоре

**Последнее обновление:** 2 марта 2026

## 🎯 Текущий фокус

### 1. Базовая платформа уже собрана
- OpenClaw ↔ LocalOS integration roadmap (Phase 1–9) завершён.
- Работают:
  - Action Orchestrator + policy + ledger
  - human-in-the-loop
  - M2M callback receiver / outbox / retry / DLQ
  - diagnostics / incident snapshot / support export / recovery flows
  - unified audit timeline
  - Telegram control surface
  - multi-channel routing (Telegram / WhatsApp / Maton bridge)

### 2. Следующий продуктовый трек
- supervised outreach для поиска и аккуратного первого касания потенциальных клиентов
- режим только с ручным подтверждением на каждом этапе

## ✅ Что уже есть в production

### OpenClaw / LocalOS
- Capability execution и tenant-scoped orchestration
- Billing accounting и reconciliation
- Approval flow в Telegram
- Support / recovery отчёты и экспорт
- Multi-channel control center в UI
- Maton adapter в unified channel router

### Telegram
- Guided `/control` entrypoint
- `reviews.reply`, `services.optimize`, `news.generate`
- `status`, `actions`, `action_status`
- `support_export`, `recovery_report`
- queue pending approvals + approve/reject inline

### Карты и метрики
- Исправлен production drift в `_get_map_metrics`: runtime снова читает `cards.overview` как text/json в Python, без `overview->>` в SQL
- Hotfix синхронизирован в live containers (`app`, `worker`)

## 🔄 В работе

### Supervised Outreach MVP
- Админский раздел `Поиск клиентов` уже существует как ранняя заготовка
- Сейчас он умеет:
  - запускать поиск через Apify
  - сохранять лиды
  - менять статус
- Текущая реализация пока черновая и требует переработки в staged pipeline
- Sprint 0 foundation:
  - security hardening (`auth` + `superadmin-only`)
  - Yandex-first sourcing via Apify actor `m_mamaev/yandex-maps-places-scraper`
  - async search jobs instead of long synchronous HTTP requests

### Что планируется следующим
- Перевести поиск на Yandex-first source:
  - Apify actor `m_mamaev/yandex-maps-places-scraper`
- Сделать staged UI:
  - найденные кандидаты
  - shortlist
  - выбранные для контакта
  - черновики сообщений
  - очередь отправки
  - результаты / learning loop
- Добавить строгий manual approval на каждом шаге
- Стартовый лимит отправки: 10 в день

## 🧱 Архитектурные ориентиры

### Канонический runtime
- Docker Compose
- PostgreSQL
- Server path: `/opt/seo-app`
- Основные сервисы:
  - `app`
  - `worker`
  - `postgres`

### Следующий data model для outreach
- `outreach_leads`
- `outreach_lead_reviews`
- `outreach_message_drafts`
- `outreach_send_batches`
- `outreach_send_queue`
- `outreach_reactions`
- `outreach_learning_examples`

### Роль OpenClaw в outreach
OpenClaw должен выполнять только capability-задачи:
- `leads.score`
- `leads.channel_enrich`
- `outreach.draft_first_message`
- `outreach.classify_reply`
- `outreach.suggest_next_step`

Workflow и источник правды по аутричу должны оставаться в LocalOS.

## 📝 Важные замечания
- `src/api/admin_prospecting.py` сейчас требует security-hardening:
  - добавить auth
  - ограничить superadmin-only
- Текущий `ProspectingManagement` — это не финальный outreach UI, а переходный экран
- Для server hotfix всегда проверять live file в контейнере (`/app/src/...`), а не только host copy
- Entry-point migrations теперь должны идти через advisory lock, иначе одновременный restart `app` и `worker` может повторно дать migration deadlock.
