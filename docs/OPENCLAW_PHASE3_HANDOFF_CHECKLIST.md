# OpenClaw ↔ LocalOS Phase 3 Handoff Checklist

## Цель Phase 3

Закрыть production-ready support/ops слой поверх связки LocalOS ↔ OpenClaw:
- action diagnostics (`incident-report`, `incident-snapshot`)
- callback recovery audit trail
- support export bundle
- manual support bundle send в Telegram
- каноничные export endpoints для support/recovery истории

## Что должно быть готово

1. В UI блока `Настройки -> Integrations -> Связь ИИ-агентов с системой` доступны:
- `Восстановить + отчёт`
- `В Telegram`
- `Support в Telegram`
- export кнопки для:
  - recovery history
  - support history
  - support bundle
  - incident report / incident snapshot

2. На backend доступны endpoint'ы:
- `POST /api/capabilities/callbacks/recovery-report`
- `GET /api/capabilities/callbacks/recovery-history`
- `GET /api/capabilities/callbacks/recovery-history/export`
- `GET /api/capabilities/support-export`
- `POST /api/capabilities/support-export/send`
- `GET /api/capabilities/support-export/send-history`
- `GET /api/capabilities/support-export/send-history/export`

3. На M2M стороне доступны endpoint'ы:
- `GET /api/openclaw/capabilities/support-export`
- `GET /api/openclaw/capabilities/support-export/send-history`
- `GET /api/openclaw/capabilities/support-export/send-history/export`

4. Worker умеет:
- слать callback/billing alerts суперадмину
- прикладывать support bundle digest к alert-сообщениям

## Acceptance

Выполнять только из:

```bash
cd /opt/seo-app
```

Запуск:

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/acceptance_openclaw_phase3.sh
```

Скрипт проверяет:
- runtime health (`HEAD /`)
- `capabilities` smoke
- `outbox` smoke
- `billing reconciliation` smoke
- alert thresholds
- `support-export` markdown
- `support-send history export` markdown
- итоговый `health.ready=true`

## Ручной smoke для support/ops

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/diagnose_openclaw_integration.sh
```

Для deep-dive по конкретному action:

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ACTION_ID='<action_id>' ./scripts/diagnose_openclaw_integration.sh
```

## Признак завершения Phase 3

Phase 3 считается завершённой, когда:
- `./scripts/acceptance_openclaw_phase3.sh` проходит без ошибок на сервере;
- UI export/send действия работают без ручного SSH;
- support может получить:
  - текущий operational snapshot,
  - recovery history,
  - support-send history,
  - action-level incident snapshot
  через каноничные endpoints и UI.
