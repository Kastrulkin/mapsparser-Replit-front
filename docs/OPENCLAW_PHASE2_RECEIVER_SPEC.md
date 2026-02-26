# OpenClaw Phase 2: M2M Callback Receiver (Spec)

## Цель

Принять callback-события из LocalOS в OpenClaw c:
- проверкой подписи;
- защитой от replay;
- дедупликацией доставки;
- гарантией идемпотентной обработки.

## Endpoint (OpenClaw)

- `POST /m2m/localos/callbacks`

Обязательные headers:
- `X-LocalOS-Event-Id`
- `X-LocalOS-Event-Timestamp` (ISO8601 UTC)
- `X-LocalOS-Dedupe-Key`
- `X-LocalOS-Signature` (hex SHA256)

Body: JSON payload callback из LocalOS.

## Signature Validation

Shared secret:
- `OPENCLAW_CALLBACK_SIGNING_SECRET`
- fallback: `OPENCLAW_LOCALOS_TOKEN`

Canonical string:
- `"{event_id}.{event_ts}.{canonical_json(payload)}"`
- `canonical_json`: `sort_keys=True`, separators `(",", ":")`, UTF-8

Expected signature:
- `hex(hmac_sha256(secret, canonical_string))`

## Replay Guard

Отклонять события, если:
- `abs(now_utc - event_ts) > 300s` (конфигурируемое окно, default 5 минут)

Рекомендованный response:
- `401` invalid signature
- `409` duplicate/replayed event
- `400` invalid timestamp/header

## Dedupe / Idempotency

Хранить dedupe state по `X-LocalOS-Dedupe-Key`.

Минимальная таблица OpenClaw:
- `localos_callback_receipts`
  - `id` UUID PK
  - `event_id` TEXT UNIQUE
  - `dedupe_key` TEXT UNIQUE
  - `received_at` TIMESTAMP
  - `processed_at` TIMESTAMP NULL
  - `status` TEXT (`received|processed|failed`)
  - `payload_json` JSONB
  - `last_error` TEXT NULL

Правило:
- если `dedupe_key` уже есть в `processed|received` — вернуть `200` (идемпотентный ack) без повторной бизнес-обработки.

## Processing Contract

События:
- `pending_human`
- `approved`
- `rejected`
- `expired`
- `completed`

Payload должен содержать:
- `action_id`
- `tenant_id`
- `event_type`
- `trace_id` (если есть)
- `billing` (для `completed`)

## Ack Semantics

- Возвращать `200` только после коммита receipt + обработки (или безопасного идемпотентного short-circuit).
- При временной ошибке — `5xx`, чтобы LocalOS отправил retry.

## Monitoring

Минимальные метрики OpenClaw receiver:
- callbacks_received_total
- callbacks_processed_total
- callbacks_deduplicated_total
- callbacks_signature_failed_total
- callbacks_replay_rejected_total
- callbacks_processing_failed_total

