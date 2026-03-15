# Partnership Roadmap Backlog (LocalOS)

Дата: 11 марта 2026  
Статус: Active planning

## Цель
Запустить пользовательский трек `Поиск партнёрств` поверх текущего supervised outreach-пайплайна, без дублирования платформенных сущностей.

## Принципы
1. Единый Ralph loop для outreach + partnership.
2. Разделение по `intent`:
   - `client_outreach`
   - `partnership_outreach`
   - `operations`
3. Orchestrator/policy/billing/audit остаются едиными.

---

## Sprint P0: Unified Learning Foundation
Статус: backend done (11.03.2026), UI metric widgets pending
### Задачи
- Ввести единый `intent` во все agent/capability action.
- Начать запись learning-сигналов для edit/accept/reject/outcome.

### API
- `POST /api/ai/learning-events` (internal)

### Таблицы
- `ailearningevents` (new)
- добавить `intent` в черновики/события, где отсутствует

### Критерии приёмки
- Для services/reviews/news/outreach сохраняются learning-события.
- В админке доступны метрики `% accepted_raw`, `% edited_before_accept`.

---

## Sprint P1: Edit-before-accept (Operations agents)
Статус: backend endpoints done (11.03.2026), UI wiring pending
### Задачи
- Дать inline-редактирование перед принятием:
  - services optimization
  - review reply
  - news draft

### API
- `POST /api/services/optimize/accept`
- `POST /api/reviews/reply/accept`
- `POST /api/news/generate/accept`

### Таблицы
- reuse existing + запись в `ailearningevents`

### Критерии приёмки
- Принятие фиксирует `draft_text` и `final_text`.
- Метрика `% edited_before_accept` считается корректно.

---

## Sprint P2: Prompt Canonicalization
### Задачи
- Убрать runtime hardcoded prompts.
- Источник промптов: админ-панель + user preferences.

### API
- `GET /api/admin/prompts/:key`
- `POST /api/admin/prompts/:key/version`

### Таблицы
- `prompttemplates`
- `prompttemplateversions`

### Критерии приёмки
- `services/reviews/news` используют prompt из БД.
- В action/audit логах есть `prompt_version`.

---

## Sprint P3: Content Agent Evolution (News -> SMM)
### Задачи
- Расширить контент-агента:
  - current: `news.generate`
  - next: `social.post.generate`

### API
- `POST /api/content/social/generate`
- `POST /api/content/social/accept`

### Таблицы
- `contentdrafts` (new) или reuse drafts c `draft_type`

### Критерии приёмки
- Генерация 3 вариантов соцпоста.
- approve flow + learning capture.

---

## Sprint P4: UI “Поиск партнёрств” MVP
Статус: backend API done (11.03.2026), user UI pending
### Задачи
- Добавить пункт меню `Поиск партнёрств`.
- Экран ручного импорта ссылок компаний.

### API
- `POST /api/partnership/leads/import-links`
- `GET /api/partnership/leads`
- `PATCH /api/partnership/leads/:id`

### Таблицы
- reuse `prospectingleads`
- добавить `intent`, `partnership_stage`

### Критерии приёмки
- Пользователь добавляет список ссылок и ведёт стадии вручную.

---

## Sprint P5: Partnership Pipeline
Статус: backend API done (11.03.2026), UI orchestration pending
### Задачи
- Стадии:
  - `imported`
  - `audited`
  - `matched`
  - `proposal_draft_ready`
  - `approved_for_send`
  - `sent`

### API
- `POST /api/partnership/leads/:id/audit`
- `POST /api/partnership/leads/:id/match`
- `POST /api/partnership/leads/:id/draft-offer`

### Таблицы
- reuse `prospectingleads` + stage поля

### Критерии приёмки
- Один lead проходит end-to-end по стадиям без ручного SQL.

---

## Sprint P6: Partnership Match Agent
Статус: local backend MVP done (11.03.2026), OpenClaw capability wiring pending
### Задачи
- Ввести capability:
  - `partnership.audit_card`
  - `partnership.match_services`
  - `partnership.draft_offer`

### API
- через `POST /api/openclaw/capabilities/execute`

### Таблицы
- reuse action orchestration tables

### Критерии приёмки
- Возвращается структурированный результат:
  - `match_score`
  - `overlap`
  - `complement`
  - `risks`
  - `offer_angles`

---

## Sprint P7: Outbound Reuse for Partnership
### Задачи
- Переиспользовать текущий drafts/batch/queue/send.
- Развести client vs partnership по `intent` в UI.

### API
- reuse outreach endpoints + фильтры по `intent`

### Таблицы
- reuse `outreachmessagedrafts`, `outreachsendbatches`, `outreachsendqueue`

### Критерии приёмки
- Партнёрские отправки не смешиваются с клиентским аутричем.

---

## Sprint P8: OpenClaw Geo Search
### Задачи
- Подключить поиск компаний в радиусе X км через OpenClaw.

### API
- `partners.search_geo`
- `partners.enrich_contacts`

### Таблицы
- импорт в `prospectingleads` (`source=openclaw_geo`)

### Критерии приёмки
- Поиск по `city/radius/category` работает и продолжает pipeline.

---

## Sprint P9: Hardening + CI
### Задачи
- Контрактные тесты и smoke для partnership flow.
- Мониторинг ошибок/retry и прозрачность в UI.

### Реализация (в работе)
- Добавлен e2e smoke-скрипт:
  - `scripts/smoke_partnership_flow.py`
  - покрывает: import -> parse -> audit -> match -> draft -> approve -> batch -> outcome -> health
  - сохраняет JSON-экспорт отчёта (`/tmp/partnership_smoke_<ts>.json` по умолчанию)

### API
- health/trend/export для partnership routes

### Таблицы
- reuse monitoring/audit tables

### Критерии приёмки
- CI gate green.
- e2e smoke pass.

---

## Sprint P10: Rollout
### Задачи
- Ограниченный запуск на pilot-группе.
- Недельный цикл улучшений по Ralph loop.

### Критерии приёмки
- Стабильный SLA.
- Улучшение acceptance/reply метрик относительно baseline.
