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
6. `GET /api/capabilities/actions/{action_id}/timeline?limit=&offset=&source=&event_type=&status=&search=&only_problematic=`
7. `GET /api/capabilities/actions/{action_id}/callback-attempts?limit=&offset=&success=&event_type=`
8. `GET /api/capabilities/actions/{action_id}/support-package?limit=&offset=&source=&event_type=&status=&search=&only_problematic=&full=`
9. `GET /api/capabilities/actions/{action_id}/diagnostics-bundle?limit=&offset=&source=&event_type=&status=&search=&only_problematic=&full=&attempts_limit=&attempts_offset=&attempts_success=&attempts_event_type=&attempts_full=`
9.1 `GET /api/capabilities/actions/{action_id}/lifecycle-summary?limit=&offset=&source=&event_type=&status=&search=&only_problematic=&full=`
9.2 `GET /api/capabilities/actions/{action_id}/incident-report` (canonical markdown snapshot for support/export)
9.3 `GET /api/capabilities/actions/{action_id}/incident-snapshot` (canonical structured JSON snapshot for support automation)
9. `POST /api/openclaw/capabilities/execute` (M2M ingress from OpenClaw)
10. `GET /api/openclaw/capabilities/actions/{action_id}` (M2M read status)
11. `GET /api/openclaw/capabilities/actions/{action_id}/billing` (M2M read billing)
12. `GET /api/openclaw/capabilities/actions/{action_id}/timeline?tenant_id=&limit=&offset=&source=&event_type=&status=&search=&only_problematic=` (M2M read timeline)
13. `GET /api/openclaw/capabilities/actions/{action_id}/callback-attempts?tenant_id=&limit=&offset=&success=&event_type=` (M2M callback delivery attempts, includes `summary` + `event_type_breakdown`)
14. `GET /api/openclaw/capabilities/actions/{action_id}/support-package?tenant_id=&limit=&offset=&source=&event_type=&status=&search=&only_problematic=&full=` (M2M aggregated diagnostics)
15. `GET /api/openclaw/capabilities/actions/{action_id}/diagnostics-bundle?tenant_id=&limit=&offset=&source=&event_type=&status=&search=&only_problematic=&full=&attempts_limit=&attempts_offset=&attempts_success=&attempts_event_type=&attempts_full=` (M2M full diagnostics bundle)
15.1 `GET /api/openclaw/capabilities/actions/{action_id}/lifecycle-summary?tenant_id=&limit=&offset=&source=&event_type=&status=&search=&only_problematic=&full=` (M2M lifecycle aggregate)
15.2 `GET /api/openclaw/capabilities/actions/{action_id}/incident-report?tenant_id=` (M2M canonical markdown snapshot for support/export)
15.3 `GET /api/openclaw/capabilities/actions/{action_id}/incident-snapshot?tenant_id=` (M2M canonical structured JSON snapshot for support automation)
16. `GET /api/openclaw/capabilities/actions?tenant_id=&status=&limit=&offset=` (M2M read list)
17. `GET /api/openclaw/capabilities/catalog` (M2M capability discovery)
18. `GET /api/openclaw/capabilities/health?tenant_id=&window_minutes=` (M2M integration readiness)
19. `GET /api/openclaw/capabilities/health/trend?tenant_id=&window_minutes=&limit=` (M2M health trend/history)
19.1 `GET /api/openclaw/capabilities/support-export?tenant_id=&action_id=&format=` (M2M canonical support bundle for ops/export)
20. `POST /api/openclaw/capabilities/actions/{action_id}/decision` (M2M human decision)
21. `POST /api/openclaw/callbacks/dispatch` (M2M callback dispatcher)
22. `GET /api/openclaw/callbacks/outbox?tenant_id=&status=&limit=&offset=` (M2M outbox inspect)
23. `GET /api/openclaw/callbacks/metrics?tenant_id=&window_minutes=` (M2M outbox metrics)
23.1 `GET /api/openclaw/callbacks/recovery-history?tenant_id=&limit=` (M2M recovery audit trail)
23.2 `GET /api/openclaw/callbacks/recovery-history/export?tenant_id=&limit=&format=` (M2M canonical recovery history export)
23.3 `GET /api/openclaw/capabilities/support-export/send-history?tenant_id=&limit=` (M2M support-send audit trail)
23.4 `GET /api/openclaw/capabilities/support-export/send-history/export?tenant_id=&limit=&format=` (M2M canonical support-send history export)
24. `GET /api/openclaw/capabilities/billing/reconcile?tenant_id=&window_minutes=&limit=` (M2M ledger/tokenusage reconciliation)
25. `POST /api/openclaw/callbacks/outbox/replay` (M2M replay DLQ/retry to pending)
26. `POST /api/openclaw/callbacks/outbox/cleanup` (M2M cleanup old sent callbacks)
27. `GET /api/capabilities/callbacks/metrics?tenant_id=&window_minutes=` (user dashboard metrics)
28. `GET /api/capabilities/health?tenant_id=&window_minutes=` (user health snapshot)
29. `GET /api/capabilities/health/trend?tenant_id=&window_minutes=&limit=` (user health trend/history)
30. `GET /api/capabilities/billing/reconcile?tenant_id=&window_minutes=&limit=` (user billing reconciliation)
31. `POST /api/capabilities/callbacks/outbox/replay` (user replay DLQ/retry to pending)
32. `POST /api/capabilities/callbacks/outbox/cleanup` (user cleanup old sent callbacks)
33. `POST /api/capabilities/callbacks/recovery-report` (user replay + dispatch + report, optional Telegram notify)
34. `GET /api/capabilities/callbacks/recovery-history?tenant_id=&limit=` (user recovery audit trail)
35. `GET /api/capabilities/callbacks/recovery-history/export?tenant_id=&limit=&format=` (user canonical recovery history export)
36. `GET /api/capabilities/support-export?tenant_id=&action_id=&format=` (user canonical support bundle for ops/export)
37. `POST /api/capabilities/support-export/send` (user manual send of support bundle to superadmin Telegram)
38. `GET /api/capabilities/support-export/send-history?tenant_id=&limit=` (user audit trail for manual support bundle sends)
39. `GET /api/capabilities/support-export/send-history/export?tenant_id=&limit=&format=` (user canonical support-send history export)

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
- `POST /api/openclaw/callbacks/outbox/replay` переводит `dlq` (и опционально `retry`) в `pending` для повторной доставки
- `POST /api/openclaw/callbacks/outbox/cleanup` удаляет старые `sent` события из outbox (housekeeping)
- token-auth тот же (`X-OpenClaw-Token`)
- автоматический фоновый dispatch выполняется в `worker` по таймеру
- env-параметры фонового dispatch:
  - `OPENCLAW_CALLBACK_DISPATCH_ENABLED` (default `true`)
  - `OPENCLAW_CALLBACK_DISPATCH_INTERVAL_SEC` (default `15`)
  - `OPENCLAW_CALLBACK_DISPATCH_BATCH_SIZE` (default `50`)

Для billing reconciliation endpoints:
- `GET /api/openclaw/capabilities/billing/reconcile` (M2M token-auth)
- `GET /api/capabilities/billing/reconcile` (user session auth)
- сверяет `billing_ledger` (`reserve/settle/release`) c `action_requests.billing_json` и агрегатом `tokenusage`
- возвращает `summary.tokenusage_minus_settled` и список action-level issues

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
- `scripts/smoke_openclaw_m2m_reconciliation.sh`
  - Проверяет M2M endpoint billing reconciliation.
- `scripts/diagnose_openclaw_integration.sh`
  - One-click диагностика для support/ops:
    - runtime (`docker compose ps`, logs, `curl -I`)
    - M2M `health`, `health_trend`, `callbacks/metrics`, `callbacks/outbox`
  - Код выхода:
    - `0` — ready
    - `2` — degraded (alerts/DLQ/stuck retry)

## CI Gate (Phase 2.2)

- `scripts/ci_gate_openclaw_phase2.sh` (canonical):
  - duplicate suffix guard
  - py_compile critical backend files
  - `tests/test_capabilities_api_phase1.py`
  - syntax-check smoke scripts
  - в `CI` режиме M2M smoke обязателен (требует `OPENCLAW_TOKEN`, `TENANT_ID`)
- `scripts/ci_gate_openclaw_phase1.sh`:
  - backward-compat wrapper to `ci_gate_openclaw_phase2.sh`
- `scripts/manage_openclaw_outbox.sh`
  - `ACTION=replay` для requeue `dlq/retry`
  - `ACTION=cleanup` для удаления старых `sent`
