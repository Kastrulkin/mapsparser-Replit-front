# OpenClaw ↔ LocalOS Phase 1 Ops Runbook

## 0) Рабочая директория (обязательно)

Все команды ниже выполняются только из:

```bash
cd /opt/seo-app
```

## 1) Быстрый health-check runtime

```bash
docker compose ps
docker compose logs --since 5m app | tail -n 200
docker compose logs --since 5m worker | tail -n 200
curl -I http://localhost:8000
```

## 2) Smoke M2M + outbox

Требуются переменные:
- `OPENCLAW_TOKEN`
- `TENANT_ID`

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/smoke_openclaw_m2m_outbox.sh
```

## 3) Проверка outbox-метрик и алертов

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/check_openclaw_outbox_alerts.sh
```

Коды возврата:
- `0` — критичных алертов нет
- `2` — в метриках есть алерты (DLQ/stuck retry/low success)

## 4) One-click диагностика интеграции

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/diagnose_openclaw_integration.sh
```

Скрипт собирает:
- runtime статус контейнеров и свежие логи `app/worker`
- `capabilities/health`
- `capabilities/health/trend`
- `callbacks/metrics`
- `callbacks/outbox`

Коды возврата:
- `0` — интеграция в норме
- `2` — есть деградация (alerts/DLQ/stuck retry)

## 5) Ручной диспетч callback outbox

```bash
curl -sS -X POST \
  -H "X-OpenClaw-Token: ${OPENCLAW_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"batch_size":50}' \
  "http://localhost:8000/api/openclaw/callbacks/dispatch"
```

## 6) Основные env-параметры

- `OPENCLAW_LOCALOS_TOKEN` — M2M auth token
- `OPENCLAW_CALLBACK_SIGNING_SECRET` — подпись callback payload (HMAC SHA256)
- `OPENCLAW_CALLBACK_DISPATCH_ENABLED` (default `true`)
- `OPENCLAW_CALLBACK_DISPATCH_INTERVAL_SEC` (default `15`)
- `OPENCLAW_CALLBACK_DISPATCH_BATCH_SIZE` (default `50`)
- `OPENCLAW_CALLBACK_RETRY_STUCK_MINUTES` (default `15`)
- `OPENCLAW_CALLBACK_DLQ_ALERT_THRESHOLD` (default `1`)
- `OPENCLAW_CALLBACK_STUCK_RETRY_ALERT_THRESHOLD` (default `1`)
- `OPENCLAW_CALLBACK_SUCCESS_RATE_MIN` (default `90`)

## 7) Failure triage

1. `callbacks/dispatch` показывает рост `dlq`:
- проверить доступность callback URL из контейнера `app`;
- проверить корректность `X-LocalOS-Signature` в стороне OpenClaw;
- проверить лимиты/таймауты на стороне OpenClaw endpoint.

2. `stuck_retry > 0`:
- проверить, что worker крутится и `_dispatch_openclaw_callback_outbox_if_due` вызывается;
- проверить env `OPENCLAW_CALLBACK_DISPATCH_ENABLED/INTERVAL_SEC`.

3. `delivery_success_rate` падает:
- смотреть `action_callback_outbox.last_error`;
- сверять по tenant/каналу проблемные callback URL.
