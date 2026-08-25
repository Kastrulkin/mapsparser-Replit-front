"""Retryable YouGile projection for inbound partner replies."""

from __future__ import annotations

import json
import hashlib
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from pg_db_utils import get_db_connection
from psycopg2.extras import Json


def enqueue_touch_sent_projection(
    cursor: Any,
    *,
    queue_id: str | None = None,
    touch_id: str | None = None,
) -> bool:
    """Project a confirmed send through the outbox without creating a second CRM task."""
    if queue_id:
        cursor.execute(
            """
            SELECT queue.id, queue.lead_id, queue.workstream_id, queue.channel,
                   queue.provider_message_id, queue.sent_at,
                   touch.id AS touch_id, touch.sequence_index + 1 AS touch_number,
                   campaign.business_id, workstream.next_action_at,
                   room.id AS room_id, room.slug AS room_slug
            FROM outreachsendqueue queue
            JOIN outreach_campaign_touches touch ON touch.id = queue.campaign_touch_id
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id = campaign.workstream_id
            LEFT JOIN LATERAL (
                SELECT id, slug FROM sales_rooms
                WHERE workstream_id = queue.workstream_id
                ORDER BY created_at ASC LIMIT 1
            ) room ON TRUE
            WHERE queue.id = %s AND queue.delivery_status IN ('sent', 'delivered')
            LIMIT 1
            """,
            (queue_id,),
        )
    elif touch_id:
        cursor.execute(
            """
            SELECT touch.id, campaign.lead_id, campaign.workstream_id, touch.channel,
                   NULL::text AS provider_message_id, touch.updated_at AS sent_at,
                   touch.id AS touch_id, touch.sequence_index + 1 AS touch_number,
                   campaign.business_id, workstream.next_action_at,
                   room.id AS room_id, room.slug AS room_slug
            FROM outreach_campaign_touches touch
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id = campaign.workstream_id
            LEFT JOIN LATERAL (
                SELECT id, slug FROM sales_rooms
                WHERE workstream_id = campaign.workstream_id
                ORDER BY created_at ASC LIMIT 1
            ) room ON TRUE
            WHERE touch.id = %s AND touch.status IN ('manual_sent', 'sent', 'delivered')
            LIMIT 1
            """,
            (touch_id,),
        )
    else:
        return False
    row = cursor.fetchone()
    context = dict(row) if row else {}
    if not context or not context.get("room_id"):
        return False

    business_id = str(context.get("business_id") or "")
    if business_id:
        cursor.execute(
            """
            SELECT business_id FROM agent_integrations
            WHERE business_id = %s AND provider = 'yougile' AND status = 'active'
            ORDER BY updated_at DESC LIMIT 1
            """,
            (business_id,),
        )
        integration = cursor.fetchone()
    else:
        cursor.execute(
            """
            SELECT business_id FROM agent_integrations
            WHERE provider = 'yougile' AND status = 'active'
              AND COALESCE(config_json->>'default_for_platform', 'false') = 'true'
            ORDER BY updated_at DESC LIMIT 2
            """
        )
        integrations = cursor.fetchall() or []
        if len(integrations) == 1:
            integration = integrations[0]
        elif not integrations:
            cursor.execute(
                """
                SELECT business_id FROM agent_integrations
                WHERE provider = 'yougile' AND status = 'active'
                ORDER BY updated_at DESC LIMIT 2
                """
            )
            only_active_integrations = cursor.fetchall() or []
            integration = only_active_integrations[0] if len(only_active_integrations) == 1 else None
        else:
            integration = None
    if not integration:
        return False
    integration_payload = dict(integration)
    projection_business_id = str(integration_payload.get("business_id") or "")
    if not projection_business_id:
        return False

    event_id = str(uuid.uuid4())
    occurred_at = context.get("sent_at") or datetime.now(timezone.utc)
    event_payload = {
        "event_kind": "touch_sent",
        "touch_id": str(context.get("touch_id") or ""),
        "touch_number": int(context.get("touch_number") or 0),
        "workstream_id": str(context.get("workstream_id") or ""),
        "lead_id": str(context.get("lead_id") or ""),
        "channel": str(context.get("channel") or ""),
    }
    event_json = json.dumps(event_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event_hash = hashlib.sha256(event_json.encode("utf-8")).hexdigest()
    cursor.execute(
        """
        INSERT INTO communication_events (
            id, message_id, room_id, event_type, channel, provider_event_id,
            occurred_at, completeness_status, metadata_json,
            content_retention_until, metadata_retention_until, event_sha256, created_at
        ) VALUES (
            %s, NULL, %s, 'delivered', %s, %s, %s, 'complete', %s,
            NOW() + INTERVAL '1 year', NOW() + INTERVAL '2 years', %s, NOW()
        )
        """,
        (
            event_id, context.get("room_id"), context.get("channel"),
            context.get("provider_message_id"), occurred_at, Json(event_payload), event_hash,
        ),
    )
    outbox_payload = {
        **event_payload,
        "business_id": projection_business_id,
        "next_action_at": (
            context.get("next_action_at").isoformat()
            if hasattr(context.get("next_action_at"), "isoformat")
            else context.get("next_action_at")
        ),
        "room_url": f"https://localos.pro/room/{context.get('room_slug')}",
    }
    payload_json = json.dumps(outbox_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cursor.execute(
        """
        INSERT INTO communication_outbox (
            id, event_id, object_kind, payload_json, payload_sha256,
            status, attempts, next_attempt_at, created_at, updated_at
        ) VALUES (%s, %s, 'yougile_task_sync', %s, %s, 'pending', 0, NOW(), NOW(), NOW())
        ON CONFLICT (event_id, object_kind) DO NOTHING
        """,
        (
            str(uuid.uuid4()), event_id, Json(outbox_payload),
            hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        ),
    )
    return True


def _request(
    method: str,
    path: str,
    *,
    token: str,
    base_url: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{path.lstrip('/')}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "localos-outreach-reply-sync/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"yougile_http_{exc.code}:{detail}") from None
    return json.loads(body) if body else {}


def _deadline(value: str) -> dict[str, Any]:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return {"deadline": int(parsed.timestamp() * 1000), "withTime": False}


def _normalized_task_title(value: Any) -> str:
    return " ".join(re.sub(r"[^0-9a-zа-яё]+", " ", str(value or "").casefold()).split())


def _find_existing_task(tasks: list[dict[str, Any]], lead_name: str) -> dict[str, Any] | None:
    normalized_lead = _normalized_task_title(lead_name)
    expected = {
        normalized_lead,
        _normalized_task_title(f"Сделка с {lead_name}"),
    }
    exact = [task for task in tasks if _normalized_task_title(task.get("title")) in expected]
    if len(exact) > 1:
        raise RuntimeError("yougile_task_ambiguous")
    if exact:
        return exact[0]
    if not normalized_lead:
        return None
    partial = [
        task for task in tasks
        if f" {normalized_lead} " in f" {_normalized_task_title(task.get('title'))} "
    ]
    if len(partial) > 1:
        raise RuntimeError("yougile_task_ambiguous")
    return partial[0] if partial else None


def _touch_column_id(config: dict[str, Any], touch_number: int, *, response: bool = False) -> Any:
    mapping_key = "response_touch_column_ids" if response else "touch_column_ids"
    mapping = config.get(mapping_key) if isinstance(config.get(mapping_key), dict) else {}
    mapped = mapping.get(str(touch_number)) or mapping.get(touch_number)
    if mapped:
        return mapped
    ordinal = {1: "first", 2: "second", 3: "third", 4: "fourth"}.get(touch_number)
    if not ordinal:
        return None
    suffix = "response_column_id" if response else "touch_column_id"
    return config.get(f"{ordinal}_{suffix}")


def _target_column_id(config: dict[str, Any], payload: dict[str, Any]) -> Any:
    classification = str(payload.get("classification") or "")
    is_refusal = classification in {"not_interested", "unsubscribe", "complaint"}
    touch_number = int(payload.get("touch_number") or 0)
    event_kind = str(payload.get("event_kind") or "inbound_reply")
    if is_refusal:
        return config.get("refused_column_id") or config.get("conversation_column_id")
    if event_kind == "touch_sent" and touch_number:
        return _touch_column_id(config, touch_number)
    if event_kind == "inbound_reply" and touch_number:
        return (
            _touch_column_id(config, touch_number, response=True)
            or config.get("conversation_column_id")
        )
    return config.get("conversation_column_id")


def _task_description(payload: dict[str, Any]) -> str:
    touch_number = int(payload.get("touch_number") or 0)
    event_kind = str(payload.get("event_kind") or "inbound_reply")
    if event_kind == "touch_sent":
        result = f"Отправлено {touch_number}-е касание" if touch_number else "Касание отправлено"
    else:
        result = f"Ответили после {touch_number}-го касания" if touch_number else "Ответ получен; номер касания нужно уточнить"
    lines = [
        f"Этап: {result}.",
        f"Канал: {payload.get('channel') or 'не указан'}.",
    ]
    if payload.get("reply_excerpt"):
        lines.append(f"Ответ: {payload.get('reply_excerpt')}")
    lines.extend([
        "",
        f"Цифровая комната: {payload.get('room_url') or 'не создана'}",
        f"LocalOS workstream: {payload.get('workstream_id')}",
    ])
    return "\n".join(lines)


def _load_context(cursor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT integration.*, lead.name AS lead_name,
               task.external_task_id, task.external_url
        FROM agent_integrations integration
        JOIN prospectingleads lead ON lead.id = %s
        LEFT JOIN outreach_external_task_bindings task
          ON task.workstream_id = %s AND task.provider = 'yougile' AND task.status = 'active'
        WHERE integration.business_id = %s
          AND integration.provider = 'yougile' AND integration.status = 'active'
        ORDER BY integration.updated_at DESC LIMIT 1
        """,
        (payload.get("lead_id"), payload.get("workstream_id"), payload.get("business_id")),
    )
    row = cursor.fetchone()
    if not row:
        raise RuntimeError("yougile_integration_missing")
    return dict(row)


def _sync_task(cursor: Any, payload: dict[str, Any]) -> str:
    context = _load_context(cursor, payload)
    config = context.get("config_json") if isinstance(context.get("config_json"), dict) else {}
    secret_name = str(context.get("auth_ref") or "YOUGILE_API_KEY").strip()
    token = os.getenv(secret_name, "").strip()
    if not token:
        raise RuntimeError("yougile_secret_missing")
    base_url = str(config.get("api_base") or "https://ru.yougile.com/api-v2")
    target_column_id = _target_column_id(config, payload)
    if not target_column_id:
        raise RuntimeError("yougile_target_column_missing")
    task_id = str(context.get("external_task_id") or "")
    lead_name = str(context.get("lead_name") or "Партнёр").strip()
    task_title = f"Сделка с {lead_name}"
    if task_id:
        current_task = _request("GET", f"/tasks/{task_id}", token=token, base_url=base_url)
        task_title = str(current_task.get("title") or task_title).strip()
    if not task_id:
        query = urllib.parse.urlencode({"limit": 1000, "offset": 0})
        response = _request("GET", f"/tasks?{query}", token=token, base_url=base_url)
        tasks = response.get("content") if isinstance(response.get("content"), list) else []
        existing_task = _find_existing_task(tasks, lead_name)
        if existing_task:
            task_id = str(existing_task.get("id") or "")
            task_title = str(existing_task.get("title") or task_title).strip()
        else:
            created = _request(
                "POST", "/tasks", token=token, base_url=base_url,
                payload={
                    "title": f"Сделка с {lead_name}",
                    "columnId": target_column_id,
                    "assigned": [config.get("assignee_id")] if config.get("assignee_id") else [],
                    "description": "Карточка создана LocalOS после входящего ответа.",
                },
            )
            task_id = str(created.get("id") or "")
        if not task_id:
            raise RuntimeError("yougile_task_id_missing")
        cursor.execute(
            """
            INSERT INTO outreach_external_task_bindings (
                id, business_id, workstream_id, provider, external_task_id,
                external_url, status, created_at, updated_at
            ) VALUES (%s, %s, %s, 'yougile', %s, %s, 'active', NOW(), NOW())
            ON CONFLICT (workstream_id, provider) DO UPDATE
            SET external_task_id = EXCLUDED.external_task_id,
                external_url = EXCLUDED.external_url, status = 'active', updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), payload.get("business_id"), payload.get("workstream_id"), task_id,
                f"https://ru.yougile.com/team/{config.get('project_id') or ''}#task-{task_id}",
            ),
        )
    description = _task_description(payload)
    is_refusal = str(payload.get("classification") or "") in {"not_interested", "unsubscribe", "complaint"}
    update_payload = {
        "title": task_title,
        "columnId": target_column_id,
        "description": description,
        "assigned": [config.get("assignee_id")] if config.get("assignee_id") else [],
        "deadline": None if is_refusal or not payload.get("next_action_at") else _deadline(str(payload.get("next_action_at"))),
    }
    _request("PUT", f"/tasks/{task_id}", token=token, base_url=base_url, payload=update_payload)
    readback = _request("GET", f"/tasks/{task_id}", token=token, base_url=base_url)
    if str(readback.get("columnId") or "") != str(target_column_id or ""):
        raise RuntimeError("yougile_readback_column_mismatch")
    cursor.execute(
        """
        UPDATE outreach_external_task_bindings
        SET last_synced_at = NOW(), metadata_json = metadata_json || %s, updated_at = NOW()
        WHERE workstream_id = %s AND provider = 'yougile'
        """,
        (
            Json({
                "last_event_kind": payload.get("event_kind") or "inbound_reply",
                "last_inbound_event_id": payload.get("inbound_event_id"),
                "last_touch_id": payload.get("touch_id"),
                "last_touch_number": payload.get("touch_number"),
            }),
            payload.get("workstream_id"),
        ),
    )
    return task_id


def process_yougile_outbox(limit: int = 20) -> dict[str, int]:
    summary = {"picked": 0, "delivered": 0, "retried": 0}
    for _index in range(max(1, min(int(limit or 20), 100))):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM communication_outbox
                WHERE object_kind = 'yougile_task_sync'
                  AND status IN ('pending', 'retry') AND next_attempt_at <= NOW()
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                break
            item = dict(row)
            summary["picked"] += 1
            cursor.execute(
                """
                UPDATE communication_outbox
                SET status = 'processing', locked_at = NOW(), attempts = attempts + 1, updated_at = NOW()
                WHERE id = %s
                """,
                (item.get("id"),),
            )
            try:
                _sync_task(cursor, item.get("payload_json") or {})
                cursor.execute(
                    """
                    UPDATE communication_outbox
                    SET status = 'delivered', archived_at = NOW(), locked_at = NULL,
                        last_error = NULL, updated_at = NOW() WHERE id = %s
                    """,
                    (item.get("id"),),
                )
                summary["delivered"] += 1
            except Exception as exc:
                cursor.execute(
                    """
                    UPDATE communication_outbox
                    SET status = 'retry', next_attempt_at = NOW() +
                            (LEAST(60, POWER(2, LEAST(attempts, 6)))::text || ' minutes')::interval,
                        locked_at = NULL, last_error = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (str(exc)[:1000], item.get("id")),
                )
                summary["retried"] += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return summary
