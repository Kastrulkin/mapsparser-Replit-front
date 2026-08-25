"""Retryable YouGile projection for inbound partner replies."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from typing import Any

from pg_db_utils import get_db_connection
from psycopg2.extras import Json


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
    task_id = str(context.get("external_task_id") or "")
    lead_name = str(context.get("lead_name") or "Партнёр").strip()
    if not task_id:
        query = urllib.parse.urlencode({"limit": 1000, "offset": 0})
        response = _request("GET", f"/tasks?{query}", token=token, base_url=base_url)
        tasks = response.get("content") if isinstance(response.get("content"), list) else []
        expected_titles = {lead_name.casefold(), f"сделка с {lead_name}".casefold()}
        matches = [
            task for task in tasks
            if str(task.get("title") or "").strip().casefold() in expected_titles
        ]
        if len(matches) > 1:
            raise RuntimeError("yougile_task_ambiguous")
        if matches:
            task_id = str(matches[0].get("id") or "")
        else:
            created = _request(
                "POST", "/tasks", token=token, base_url=base_url,
                payload={
                    "title": f"Сделка с {lead_name}",
                    "columnId": config.get("conversation_column_id"),
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
    description = (
        f"Канал: {payload.get('channel')}.\n"
        f"Ответ: {payload.get('reply_excerpt')}\n\n"
        f"Цифровая комната: {payload.get('room_url')}\n"
        f"LocalOS workstream: {payload.get('workstream_id')}"
    )
    is_refusal = str(payload.get("classification") or "") in {"not_interested", "unsubscribe", "complaint"}
    target_column_id = (
        config.get("refused_column_id") if is_refusal else config.get("conversation_column_id")
    ) or config.get("conversation_column_id")
    update_payload = {
        "title": f"Сделка с {lead_name}",
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
        (Json({"last_inbound_event_id": payload.get("inbound_event_id")}), payload.get("workstream_id")),
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
