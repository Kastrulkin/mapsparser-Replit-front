# LocalOS ↔ OpenClaw Contract (Phase 1)

Версия: `1.0.0-phase1`

Этот документ фиксирует минимальный рабочий контракт для Phase 1:
- Action Orchestrator в LocalOS
- policy + pre-check лимитов
- ledger-биллинг
- capabilities: `reviews.reply`, `services.optimize`

## Endpoints (LocalOS)

1. `POST /api/capabilities/execute`
2. `POST /api/capabilities/actions/{action_id}/decision`
3. `GET /api/capabilities/actions/{action_id}`
4. `GET /api/capabilities/actions?tenant_id=&status=&limit=&offset=`
5. `GET /api/capabilities/actions/{action_id}/billing`
6. `POST /api/openclaw/capabilities/execute` (M2M ingress from OpenClaw)

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

## Примеры

См. JSON в этой директории:
- `request.execute.services.optimize.pending.json`
- `response.execute.pending_human.json`
- `request.decision.rejected.json`
- `response.decision.rejected.json`
- `response.action.status.rejected.json`
