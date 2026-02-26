# LocalOS ↔ OpenClaw Contract (Phase 1)

Версия: `1.1.0-phase2`

Этот документ фиксирует рабочий контракт LocalOS↔OpenClaw:
- Action Orchestrator в LocalOS
- policy + pre-check лимитов
- ledger-биллинг
- capabilities:
  - `reviews.reply`
  - `services.optimize`
  - `appointments.create`
  - `appointments.update`
  - `appointments.cancel`
  - `reminders.send`
  - `news.generate`
  - `sales.ingest`

## Endpoints (LocalOS)

1. `POST /api/capabilities/execute`
2. `POST /api/capabilities/actions/{action_id}/decision`
3. `GET /api/capabilities/actions/{action_id}`
4. `GET /api/capabilities/actions?tenant_id=&status=&limit=&offset=`
5. `GET /api/capabilities/actions/{action_id}/billing`
6. `POST /api/openclaw/capabilities/execute` (M2M ingress from OpenClaw)
7. `GET /api/openclaw/capabilities/actions/{action_id}` (M2M read status)
8. `GET /api/openclaw/capabilities/actions/{action_id}/billing` (M2M read billing)
9. `GET /api/openclaw/capabilities/actions?tenant_id=&status=&limit=&offset=` (M2M read list)
10. `GET /api/openclaw/capabilities/catalog` (M2M capability discovery)
11. `GET /api/openclaw/capabilities/health?tenant_id=&window_minutes=` (M2M integration readiness)
12. `GET /api/openclaw/capabilities/health/trend?tenant_id=&window_minutes=&limit=` (M2M health trend/history)
13. `POST /api/openclaw/capabilities/actions/{action_id}/decision` (M2M human decision)
14. `POST /api/openclaw/callbacks/dispatch` (M2M callback dispatcher)
15. `GET /api/openclaw/callbacks/outbox?tenant_id=&status=&limit=&offset=` (M2M outbox inspect)
16. `GET /api/openclaw/callbacks/metrics?tenant_id=&window_minutes=` (M2M outbox metrics)
17. `GET /api/capabilities/callbacks/metrics?tenant_id=&window_minutes=` (user dashboard metrics)
18. `GET /api/capabilities/health?tenant_id=&window_minutes=` (user health snapshot)
19. `GET /api/capabilities/health/trend?tenant_id=&window_minutes=&limit=` (user health trend/history)

## Обязательные поля envelope (`execute`)

- `tenant_id` — tenant бизнеса
- `actor` — кто инициировал действие
- `trace_id` — трассировка сквозного запроса
- `idempotency_key` — идемпотентность
- `capability` — имя capability
- `approval` — политика human-in-the-loop
- `billing` — billing настройки
- `payload` — бизнес-данные действия

Для M2M ingress (`/api/openclaw/capabilities/execute`) дополнительно:
- заголовок `X-OpenClaw-Token`
- backend проверяет совпадение с `OPENCLAW_LOCALOS_TOKEN`
- `actor.id` может не приходить: backend проставит `owner_id` tenant

Для M2M read endpoints:
- заголовок `X-OpenClaw-Token` обязателен
- `tenant_id` обязателен как query-параметр
- при несовпадении tenant/action возвращается ошибка (`TENANT_MISMATCH`/`TENANT_NOT_FOUND`)

Для M2M health endpoint:
- `GET /api/openclaw/capabilities/health`
- возвращает `status: ready|degraded`, `ready: bool`, блок `checks`:
  - `token_configured`
  - `callbacks_enabled`
  - `dlq_count`
  - `retry_backlog`
  - `stuck_retry`
- при вызове сохраняет snapshot в `openclaw_capability_health_history`

Для M2M health trend endpoint:
- `GET /api/openclaw/capabilities/health/trend`
- возвращает историю snapshot по tenant за окно `window_minutes`
- ограничение выдачи через `limit` (по умолчанию 200)

Для M2M decision endpoint:
- заголовок `X-OpenClaw-Token` обязателен
- `tenant_id` обязателен (JSON body или query)
- `decision`: `approved` | `rejected` | `expired`

Для callback outbox endpoints:
- `POST /api/openclaw/callbacks/dispatch` запускает отправку batch callback-событий
- `GET /api/openclaw/callbacks/outbox` возвращает состояние очереди по tenant
- `GET /api/openclaw/callbacks/metrics` возвращает метрики доставки (`sent/retry/dlq/pending/stuck_retry/success_rate`) + alerts
- token-auth тот же (`X-OpenClaw-Token`)
- автоматический фоновый dispatch выполняется в `worker` по таймеру
- env-параметры фонового dispatch:
  - `OPENCLAW_CALLBACK_DISPATCH_ENABLED` (default `true`)
  - `OPENCLAW_CALLBACK_DISPATCH_INTERVAL_SEC` (default `15`)
  - `OPENCLAW_CALLBACK_DISPATCH_BATCH_SIZE` (default `50`)

## Статусы action-machine

- `received`
- `validated`
- `policy_checked`
- `pending_human`
- `approved`
- `rejected`
- `expired`
- `reserved`
- `executing`
- `completed`
- `failed`

## Human-in-the-loop

- если политика требует подтверждения, `execute` возвращает `pending_human`
- решение отправляется через `/decision`:
  - `approved`
  - `rejected`
  - `expired`
- после решения актуальный статус доступен через `/actions/{action_id}`
- если действие в `pending_human` просрочено по `expires_at`, при чтении статуса/списка оно автоматически переходит в `expired`

## Billing / Ledger (Phase 1)

Леджер хранит записи:
- `reserve`
- `settle`
- `release`

Поля результата billing:
- `total_tokens`
- `cost`
- `tool_calls`
- `tariff_id`

Billing-summary endpoint:
- `reserved_tokens`
- `settled_tokens`
- `released_tokens`
- `inflight_reserved_tokens`
- `total_cost`

## Callback Outbox / Retry / DLQ

- callback события пишутся в `action_callback_outbox`
- поддерживаемые события: `pending_human`, `approved`, `rejected`, `expired`, `completed`
- статусы outbox:
  - `pending`
  - `retry`
  - `sending`
  - `sent`
  - `dlq`
- retry-политика: bounded exponential backoff (до 300 сек)
- после `max_attempts` запись переходит в `dlq`
- replay/idempotency delivery:
  - каждый callback event получает `dedupe_key` (`{action_id}:{event_type}` по умолчанию)
  - уникальный индекс `uq_action_callback_outbox_dedupe_key` блокирует повторную постановку одного и того же события
- callback headers для верификации на стороне OpenClaw:
  - `X-LocalOS-Event-Id`
  - `X-LocalOS-Event-Timestamp`
  - `X-LocalOS-Dedupe-Key` (stable event idempotency key, default `{action_id}:{event_type}`)
  - `X-LocalOS-Signature` (HMAC SHA256 от `event_id.timestamp.canonical_json(payload)`)
  - секрет подписи: `OPENCLAW_CALLBACK_SIGNING_SECRET` (fallback: `OPENCLAW_LOCALOS_TOKEN`)

## Примеры

См. JSON в этой директории:
- `request.execute.services.optimize.pending.json`
- `response.execute.pending_human.json`
- `request.decision.rejected.json`
- `response.decision.rejected.json`
- `response.action.status.rejected.json`

## Smoke Scripts

- `scripts/smoke_openclaw_m2m_capabilities.sh`
  - Проверяет M2M путь `health -> health_trend -> catalog -> execute -> status -> billing` (+ optional `decision`).
  - Обязательные env: `OPENCLAW_TOKEN`, `TENANT_ID`.
  - Опционально: `BASE_URL` (default `http://localhost:8000`).
- `scripts/smoke_openclaw_m2m_outbox.sh`
  - Проверяет outbox/dispatch/metrics callback-контура.
- `scripts/diagnose_openclaw_integration.sh`
  - One-click диагностика для support/ops:
    - runtime (`docker compose ps`, logs, `curl -I`)
    - M2M `health`, `health_trend`, `callbacks/metrics`, `callbacks/outbox`
  - Код выхода:
    - `0` — ready
    - `2` — degraded (alerts/DLQ/stuck retry)

## CI Gate (Phase 2.2)

- `scripts/ci_gate_openclaw_phase1.sh`:
  - duplicate suffix guard
  - py_compile critical backend files
  - `tests/test_capabilities_api_phase1.py`
  - syntax-check smoke scripts
  - в `CI` режиме M2M smoke обязателен (требует `OPENCLAW_TOKEN`, `TENANT_ID`)
