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
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/smoke_openclaw_m2m_reconciliation.sh
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

Для детальной диагностики конкретного action (status + billing + timeline + support-package):
```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ACTION_ID='<action_id>' ./scripts/diagnose_openclaw_integration.sh
```

Скрипт собирает:
- runtime статус контейнеров и свежие логи `app/worker`
- `capabilities/health`
- `capabilities/health/trend`
- `callbacks/metrics`
- `callbacks/outbox`
- `capabilities/support-export` (каноничный markdown support bundle)
- `capabilities/support-export/send-history`
- `capabilities/support-export/send-history/export` (каноничный markdown support-send history)
- `capabilities/actions/{action_id}/lifecycle-summary` (если задан `ACTION_ID`)
- `capabilities/actions/{action_id}/incident-snapshot` (если задан `ACTION_ID`)
- `capabilities/actions/{action_id}/incident-report` (если задан `ACTION_ID`)
- `capabilities/actions/{action_id}/support-package` (если задан `ACTION_ID`)

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
- `OPENCLAW_CALLBACK_ALERT_NOTIFY_ENABLED` (default `true`)
- `OPENCLAW_CALLBACK_ALERT_SCAN_INTERVAL_SEC` (default `180`)
- `OPENCLAW_CALLBACK_ALERT_NOTIFY_INTERVAL_SEC` (default `900`)
- `OPENCLAW_CALLBACK_ALERT_NOTIFY_WINDOW_MINUTES` (default `60`)
- `OPENCLAW_CALLBACK_ALERT_NOTIFY_MAX_TENANTS` (default `100`)
- `OPENCLAW_BILLING_RECONCILE_ENABLED` (default `true`)
- `OPENCLAW_BILLING_RECONCILE_INTERVAL_SEC` (default `900`)
- `OPENCLAW_BILLING_RECONCILE_WINDOW_MINUTES` (default `120`)
- `OPENCLAW_BILLING_RECONCILE_LIMIT` (default `200`)
- `OPENCLAW_BILLING_RECONCILE_MAX_TENANTS` (default `100`)
- `OPENCLAW_BILLING_RECONCILE_ALERT_ENABLED` (default `true`)
- `OPENCLAW_BILLING_RECONCILE_ALERT_INTERVAL_SEC` (default `1800`)
- `OPENCLAW_BILLING_RECONCILE_ALERT_MIN_ISSUES` (default `1`)
- `OPENCLAW_SUPERADMIN_TELEGRAM_IDS` (optional CSV of Telegram chat IDs, fallback if `users.telegram_id` is unavailable)

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

4. `billing_reconcile` сигналит расхождения:
- проверить `GET /api/openclaw/capabilities/billing/reconcile`;
- сверить `billing_ledger` vs `action_requests.billing_json` vs `tokenusage`;
- после правок снова прогнать `./scripts/smoke_openclaw_m2m_reconciliation.sh`.

### Repair helper: `missing_settle` (dry-run first)

Проверка (без изменений в БД):

```bash
cd /opt/seo-app
python3 scripts/repair_openclaw_missing_settle.py \
  --tenant-id <business_id> \
  --window-minutes 43200
```

Применение (только после проверки dry-run):

```bash
cd /opt/seo-app
python3 scripts/repair_openclaw_missing_settle.py \
  --tenant-id <business_id> \
  --window-minutes 43200 \
  --apply
```

## 8) DLQ replay / outbox cleanup

Повторно отправить `dlq` (или `dlq+retry`) в очередь:

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ACTION=replay INCLUDE_RETRY=true ./scripts/manage_openclaw_outbox.sh
```

Удалить старые `sent` записи из outbox:

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ACTION=cleanup OLDER_THAN_MINUTES=1440 LIMIT=1000 ./scripts/manage_openclaw_outbox.sh
```

## 9) One-Click Smoke + Recovery

Для быстрого прогона и самовосстановления callback-контура (smoke + metrics + replay/re-dispatch + diagnose):

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/openclaw_ops_smoke_recover.sh
```

Параметры:
- `WINDOW_MINUTES` (default `60`) — окно метрик callback
- `RECOVERY_ATTEMPTS` (default `2`) — число попыток replay+dispatch
- `STRICT` (default `1`) — если алерты остались после recovery, скрипт завершится с `exit 2`
- `SNAPSHOT_LIMIT` (default `2`) — сколько проблемных `action_id` показывать в before/after snapshot
- `SEND_TELEGRAM_REPORT=1` — после recovery отправить краткий ops-report суперадмину через `./scripts/send_openclaw_ops_report.sh`

Прямой вызов sender:

```bash
REPORT_FILE=/tmp/openclaw_ops_report.txt ./scripts/send_openclaw_ops_report.sh
```

UI recovery:
- `Настройки -> Integrations -> Связь ИИ-агентов с системой -> Восстановить + отчёт`
- `Настройки -> Integrations -> Связь ИИ-агентов с системой -> В Telegram`
- backend endpoint: `POST /api/capabilities/callbacks/recovery-report`
- делает `replay (include_retry=true)` + tenant-scoped `dispatch`, возвращает краткий recovery report и, при `send_telegram_report=true`, отправляет его суперадмину в Telegram.

UI support export:
- `Настройки -> Integrations -> Связь ИИ-агентов с системой -> Support в Telegram`
- backend endpoint: `POST /api/capabilities/support-export/send`
- отправляет суперадмину каноничный `support bundle` по текущему tenant (и выбранному `action_id`, если он есть).
- аудит отправок:
  - `GET /api/capabilities/support-export/send-history`
  - `GET /api/capabilities/support-export/send-history/export?format=json|markdown`
- в UI доступны каноничные выгрузки:
  - `Экспорт JSON`
  - `Экспорт MD`

Unified audit timeline:
- `GET /api/capabilities/audit-timeline`
- `GET /api/openclaw/audit-timeline`
- объединяет в одном tenant-scoped потоке:
  - `action_request`
  - `action_transition`
  - `callback_attempt`
  - `recovery_run`
  - `support_send`

## 10) Reproducible Server Deploy (Phase 2)

Единый сценарий деплоя app/worker + верификация + OpenClaw smoke/recovery:

```bash
cd /opt/seo-app
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/deploy_openclaw_phase2.sh
```

Параметры:
- `SKIP_BUILD=1` — пропустить сборку и выполнить только restart + verify
- `BUILD_RETRIES` (default `3`) — число попыток сборки `app/worker`
- `BUILD_RETRY_SLEEP_SEC` (default `20`) — пауза между попытками сборки

Примечание по серверной сборке:
- В Dockerfile включён fallback apt-зеркал с приоритетом `mirror.yandex.ru` для стабильной сборки в текущей сети.
- Для длительного полного build используйте `tmux`:

```bash
tmux new -s phase2-build
cd /opt/seo-app
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/deploy_openclaw_phase2.sh | tee /tmp/phase2_full_deploy.log
```

## 11) Final Acceptance (Phase 2)

Итоговый приёмочный прогон в одном запуске:

```bash
cd /opt/seo-app
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/acceptance_openclaw_phase2.sh
```

Скрипт проверяет:
- runtime health (`HEAD /`)
- `capabilities` smoke
- `outbox` smoke
- `billing reconciliation` smoke
- outbox alerts + `capabilities/health.ready=true`

## 12) Final Acceptance (Phase 3)

Итоговый приёмочный прогон support/ops слоя:

```bash
cd /opt/seo-app
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/acceptance_openclaw_phase3.sh
```

Скрипт дополнительно проверяет:
- `support-export` markdown
- `support-send history export` markdown
- финальный `health.ready=true`
```
