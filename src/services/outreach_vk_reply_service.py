from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json

from pg_db_utils import get_db_connection
from services.outreach_safety_service import classify_inbound_event, record_sender_health_event
from services.outreach_vk_adapter import (
    VkOutreachAdapterError,
    ensure_vk_outreach_config,
    fetch_vk_replies,
)


def _load_vk_senders(limit: int, sender_account_id: str | None = None) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT *
            FROM outreach_sender_accounts
            WHERE channel = 'vk'
              AND status = 'connected'
              AND outreach_enabled = TRUE
              AND COALESCE((capabilities_json->>'direct_send')::boolean, FALSE) = TRUE
              AND COALESCE((capabilities_json->>'reply_sync')::boolean, FALSE) = TRUE
        """
        params: list[Any] = []
        if sender_account_id:
            query += " AND id = %s"
            params.append(sender_account_id)
        query += " ORDER BY COALESCE(last_reply_sync_at, created_at) ASC LIMIT %s"
        params.append(max(1, min(int(limit or 25), 200)))
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _load_queue_candidates(sender_account_id: str, campaign_id: str | None) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT q.id, q.lead_id, q.workstream_id, q.campaign_touch_id,
                   q.provider_message_id, q.recipient_value, q.sent_at,
                   q.provider_name, touch.campaign_id
            FROM outreachsendqueue q
            JOIN outreach_campaign_touches touch ON touch.id = q.campaign_touch_id
            WHERE q.sender_account_id = %s
              AND q.channel = 'vk'
              AND q.provider_name IN ('vk_user_api', 'vk_community_api')
              AND q.delivery_status IN ('sent', 'delivered')
              AND q.recipient_value IS NOT NULL
              AND q.sent_at >= NOW() - INTERVAL '45 days'
        """
        params: list[Any] = [sender_account_id]
        if campaign_id:
            query += " AND touch.campaign_id = %s"
            params.append(campaign_id)
        query += " ORDER BY q.sent_at DESC LIMIT 1000"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _record_sync_event(
    cursor: Any,
    sender_account_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_sender_account_events (
            id, sender_account_id, event_type, payload_json, created_at
        ) VALUES (%s, %s, %s, %s, NOW())
        """,
        (str(uuid.uuid4()), sender_account_id, event_type, Json(payload)),
    )


def _record_reply(
    queue_item: dict[str, Any],
    sender: dict[str, Any],
    reply: dict[str, Any],
    classification: dict[str, Any],
) -> str:
    from api.admin_prospecting import _record_reaction

    outcome = {
        "interested": "positive",
        "question": "question",
        "not_interested": "hard_no",
        "unsubscribe": "hard_no",
        "complaint": "hard_no",
        "human_unknown": "question",
    }.get(classification["classification"], "question")
    reaction, reaction_error = _record_reaction(
        str(queue_item.get("id") or ""),
        str(reply.get("body") or "").strip(),
        outcome,
        "vk_reply_sync",
        "system:vk_reply_sync",
        provider_name=str(queue_item.get("provider_name") or "vk_user_api"),
        provider_account_id=str(sender.get("id") or ""),
        provider_message_id=str(reply.get("provider_event_id") or ""),
        reply_created_at=reply.get("occurred_at"),
        prefer_ai=False,
        inbound_classification_override=classification["classification"],
        inbound_payload={"peer_id": reply.get("peer_id"), "from_id": reply.get("from_id")},
    )
    if reaction:
        return "recorded"
    return "duplicate" if reaction_error == "Reaction already recorded" else "failed"


def sync_vk_replies(
    *,
    sender_limit: int = 25,
    per_conversation_limit: int = 50,
    sender_account_id: str | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    senders = _load_vk_senders(sender_limit, sender_account_id=sender_account_id)
    summary = {
        "success": True,
        "picked": len(senders),
        "fetched": 0,
        "imported": 0,
        "duplicates": 0,
        "failed": 0,
        "sender_account_id": sender_account_id,
        "campaign_id": campaign_id,
        "sender_results": [],
    }
    for sender in senders:
        sender_id = str(sender.get("id") or "")
        sender_fetched = 0
        sender_imported = 0
        try:
            _config, refreshed_encrypted = ensure_vk_outreach_config(sender)
            if refreshed_encrypted:
                refresh_conn = get_db_connection()
                try:
                    refresh_cursor = refresh_conn.cursor()
                    refresh_cursor.execute(
                        """
                        UPDATE outreach_sender_accounts
                        SET auth_data_encrypted = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (refreshed_encrypted, sender_id),
                    )
                    refresh_conn.commit()
                    sender["auth_data_encrypted"] = refreshed_encrypted
                except Exception:
                    refresh_conn.rollback()
                    raise
                finally:
                    refresh_conn.close()
            candidates = _load_queue_candidates(sender_id, campaign_id)
            for candidate in candidates:
                sent_at = candidate.get("sent_at")
                if not isinstance(sent_at, datetime):
                    sent_at = datetime.now(timezone.utc)
                replies = fetch_vk_replies(
                    sender,
                    peer_id=str(candidate.get("recipient_value") or ""),
                    sent_after=sent_at,
                    after_message_id=str(candidate.get("provider_message_id") or "") or None,
                    limit=per_conversation_limit,
                )
                for reply in replies:
                    sender_fetched += 1
                    summary["fetched"] += 1
                    classification = classify_inbound_event({
                        "body": reply.get("body"),
                        "raw_reply": reply.get("body"),
                    })
                    status = _record_reply(candidate, sender, reply, classification)
                    if status == "recorded":
                        sender_imported += 1
                        summary["imported"] += 1
                    elif status == "duplicate":
                        summary["duplicates"] += 1
                    else:
                        summary["failed"] += 1
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE outreach_sender_accounts
                    SET last_reply_sync_at = NOW(), reply_sync_error = NULL, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (sender_id,),
                )
                _record_sync_event(
                    cursor,
                    sender_id,
                    "reply_sync_succeeded",
                    {"fetched": sender_fetched, "imported": sender_imported},
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            summary["sender_results"].append({
                "sender_account_id": sender_id,
                "status": "ok",
                "fetched": sender_fetched,
                "imported": sender_imported,
            })
        except Exception as exc:
            summary["failed"] += 1
            error_code = getattr(exc, "code", "vk_reply_sync_failed")
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE outreach_sender_accounts
                    SET reply_sync_error = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (error_code, sender_id),
                )
                _record_sync_event(cursor, sender_id, "reply_sync_failed", {"error_code": error_code})
                if isinstance(exc, VkOutreachAdapterError):
                    record_sender_health_event(
                        cursor,
                        sender_account_id=sender_id,
                        event_type="auth_invalid" if "auth" in exc.code else "delivery_failed",
                        provider_code=error_code,
                        metrics={"reply_sync_failed": True},
                    )
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                conn.close()
            summary["sender_results"].append({
                "sender_account_id": sender_id,
                "status": "failed",
                "error_code": error_code,
            })
    summary["success"] = summary["failed"] == 0
    return summary
