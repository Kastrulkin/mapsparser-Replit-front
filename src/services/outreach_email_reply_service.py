from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json

from pg_db_utils import get_db_connection
from services.outreach_email_adapter import EmailAdapterError, fetch_replies, normalize_email
from services.outreach_safety_service import classify_inbound_event, record_sender_health_event


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _reference_tokens(reply: dict[str, Any]) -> set[str]:
    raw = " ".join(
        str(reply.get(key) or "")
        for key in ("in_reply_to", "references", "body")
    )
    return {token.strip().lower() for token in re.findall(r"<[^<>\s]+>", raw)}


def _load_email_senders(limit: int, sender_account_id: str | None = None) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT *
            FROM outreach_sender_accounts
            WHERE channel = 'email'
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


def _load_queue_candidates(
    sender_account_id: str,
    campaign_id: str | None = None,
) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT q.id, q.lead_id, q.workstream_id, q.campaign_touch_id,
                   q.provider_message_id, q.recipient_value, q.sent_at,
                   touch.contact_point_id, touch.sequence_index,
                   touch.campaign_id, campaign.status AS campaign_status
            FROM outreachsendqueue q
            JOIN outreach_campaign_touches touch ON touch.id = q.campaign_touch_id
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            WHERE q.sender_account_id = %s
              AND q.channel = 'email'
              AND q.provider_name = 'native_email'
              AND q.delivery_status IN ('sent', 'delivered')
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


def _match_queue_item(reply: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    references = _reference_tokens(reply)
    for candidate in candidates:
        message_id = str(candidate.get("provider_message_id") or "").strip().lower()
        if message_id and message_id in references:
            return candidate
    from_email = normalize_email(reply.get("from_email"))
    occurred_at = reply.get("occurred_at")
    body_lower = str(reply.get("body") or "").lower()
    for candidate in candidates:
        recipient = normalize_email(candidate.get("recipient_value"))
        sent_at = candidate.get("sent_at")
        if occurred_at and sent_at and occurred_at < sent_at - timedelta(minutes=5):
            continue
        if recipient and (recipient == from_email or recipient in body_lower):
            return candidate
    return None


def _record_sender_sync_event(
    cursor: Any,
    *,
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


def _record_technical_event(
    queue_item: dict[str, Any],
    sender: dict[str, Any],
    reply: dict[str, Any],
    classification: dict[str, Any],
) -> str:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT touch.*, campaign.scope_type, campaign.business_id,
                   campaign.workstream_id, workstream.workstream_type
            FROM outreach_campaign_touches touch
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id = campaign.workstream_id
            WHERE touch.id = %s
            FOR UPDATE OF touch
            """,
            (queue_item.get("campaign_touch_id"),),
        )
        touch = _dict(cursor.fetchone())
        if not touch:
            conn.rollback()
            return "unmatched"
        cursor.execute(
            """
            INSERT INTO outreach_inbound_events (
                id, campaign_id, touch_id, lead_id, workstream_id,
                sender_account_id, channel, provider_event_id, event_type,
                classification, is_human, stops_campaign, confidence,
                raw_payload_json, classified_by, occurred_at, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, 'email', %s, 'provider_event',
                %s, FALSE, FALSE, %s, %s, 'system', %s, NOW()
            )
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                str(uuid.uuid4()), touch.get("campaign_id"), touch.get("id"),
                queue_item.get("lead_id"), touch.get("workstream_id"), sender.get("id"),
                reply.get("provider_event_id"), classification["classification"],
                classification["confidence"],
                Json({
                    "subject": reply.get("subject"),
                    "body": str(reply.get("body") or "")[:10000],
                    "from_email": reply.get("from_email"),
                    "auto_submitted": reply.get("auto_submitted"),
                    "precedence": reply.get("precedence"),
                    "mailbox_uid": reply.get("mailbox_uid"),
                }),
                reply.get("occurred_at"),
            ),
        )
        if not cursor.fetchone():
            conn.rollback()
            return "duplicate"
        event_class = classification["classification"]
        if event_class == "out_of_office":
            cursor.execute(
                """
                UPDATE outreach_campaigns
                SET status = 'paused', stop_reason = 'out_of_office',
                    needs_attention_reason = 'out_of_office', updated_at = NOW()
                WHERE id = %s AND status IN ('approved', 'active')
                """,
                (touch.get("campaign_id"),),
            )
            cursor.execute(
                """
                UPDATE outreach_campaign_touches
                SET status = 'paused', preflight_reason = 'out_of_office', updated_at = NOW()
                WHERE campaign_id = %s
                  AND sequence_index > %s
                  AND status IN ('approved', 'scheduled', 'queued', 'awaiting_manual_send')
                """,
                (touch.get("campaign_id"), touch.get("sequence_index")),
            )
            cursor.execute(
                """
                UPDATE outreachsendqueue
                SET delivery_status = 'paused', preflight_reason = 'out_of_office',
                    error_text = 'out_of_office', updated_at = NOW()
                WHERE campaign_touch_id IN (
                    SELECT id FROM outreach_campaign_touches
                    WHERE campaign_id = %s AND status = 'paused'
                )
                  AND delivery_status IN ('queued', 'retry')
                """,
                (touch.get("campaign_id"),),
            )
            cursor.execute(
                """
                UPDATE lead_workstreams
                SET lifecycle_status = 'needs_attention', status_reason = 'out_of_office',
                    next_step = 'Проверить дату возврата или возобновить вручную',
                    state_changed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (touch.get("workstream_id"),),
            )
        elif event_class in {"bounce", "permanent_delivery_failure"}:
            if touch.get("contact_point_id"):
                cursor.execute(
                    """
                    UPDATE lead_contact_points
                    SET verification_status = 'invalid', updated_at = NOW()
                    WHERE id = %s
                    """,
                    (touch.get("contact_point_id"),),
                )
            cursor.execute(
                """
                UPDATE outreach_campaign_touches
                SET status = 'failed', preflight_reason = %s,
                    delivery_json = delivery_json || %s, updated_at = NOW()
                WHERE id = %s
                """,
                (
                    event_class, Json({"email_delivery_event": event_class}), touch.get("id"),
                ),
            )
            record_sender_health_event(
                cursor,
                sender_account_id=str(sender.get("id") or ""),
                event_type="bounce",
                provider_code=event_class,
                touch_id=str(touch.get("id") or "") or None,
                metrics={"provider_event_id": reply.get("provider_event_id")},
            )
        cursor.execute(
            """
            INSERT INTO outreach_campaign_events (
                id, campaign_id, touch_id, event_type, reason_code,
                payload_json, created_at
            ) VALUES (%s, %s, %s, 'inbound_technical_event', %s, %s, NOW())
            """,
            (
                str(uuid.uuid4()), touch.get("campaign_id"), touch.get("id"),
                event_class, Json({
                    "provider_event_id": reply.get("provider_event_id"),
                    "subject": reply.get("subject"),
                }),
            ),
        )
        conn.commit()
        return "recorded"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _record_human_reply(
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
    }.get(classification["classification"])
    raw_reply = str(reply.get("body") or reply.get("subject") or "").strip()
    reaction, reaction_error = _record_reaction(
        str(queue_item.get("id") or ""),
        raw_reply,
        outcome,
        "email_reply_sync",
        "system:email_reply_sync",
        provider_name="native_email",
        provider_account_id=str(sender.get("id") or ""),
        provider_message_id=str(reply.get("provider_event_id") or ""),
        reply_created_at=reply.get("occurred_at"),
        prefer_ai=False,
        inbound_classification_override=classification["classification"],
        inbound_payload={
            "subject": reply.get("subject"),
            "auto_submitted": reply.get("auto_submitted"),
            "precedence": reply.get("precedence"),
        },
    )
    if reaction:
        return "recorded"
    return "duplicate" if reaction_error == "Reaction already recorded" else "failed"


def sync_email_replies(
    *,
    sender_limit: int = 25,
    per_sender_limit: int = 100,
    sender_account_id: str | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    senders = _load_email_senders(sender_limit, sender_account_id=sender_account_id)
    summary = {
        "success": True,
        "picked": len(senders),
        "fetched": 0,
        "matched": 0,
        "imported": 0,
        "technical": 0,
        "duplicates": 0,
        "unmatched": 0,
        "failed": 0,
        "sender_account_id": sender_account_id,
        "campaign_id": campaign_id,
        "sender_results": [],
    }
    for sender in senders:
        sender_id = str(sender.get("id") or "")
        try:
            since_at = sender.get("last_reply_sync_at")
            if not isinstance(since_at, datetime):
                since_at = datetime.now(timezone.utc) - timedelta(days=30)
            replies = fetch_replies(
                sender,
                since_at=since_at - timedelta(minutes=10),
                limit=per_sender_limit,
            )
            candidates = _load_queue_candidates(sender_id, campaign_id=campaign_id)
            sender_imported = 0
            sender_unmatched = 0
            for reply in replies:
                summary["fetched"] += 1
                queue_item = _match_queue_item(reply, candidates)
                if not queue_item:
                    summary["unmatched"] += 1
                    sender_unmatched += 1
                    continue
                summary["matched"] += 1
                classification = classify_inbound_event({
                    "subject": reply.get("subject"),
                    "body": reply.get("body"),
                    "raw_reply": reply.get("body"),
                    "auto_submitted": reply.get("auto_submitted"),
                    "precedence": reply.get("precedence"),
                })
                if classification["is_human"]:
                    status = _record_human_reply(queue_item, sender, reply, classification)
                else:
                    status = _record_technical_event(queue_item, sender, reply, classification)
                    if status == "recorded":
                        summary["technical"] += 1
                if status == "recorded":
                    summary["imported"] += 1
                    sender_imported += 1
                elif status == "duplicate":
                    summary["duplicates"] += 1
                elif status == "unmatched":
                    summary["unmatched"] += 1
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
                _record_sender_sync_event(
                    cursor,
                    sender_account_id=sender_id,
                    event_type="reply_sync_succeeded",
                    payload={
                        "fetched": len(replies),
                        "imported": sender_imported,
                        "unmatched": sender_unmatched,
                    },
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
                "fetched": len(replies),
                "imported": sender_imported,
            })
        except Exception as exc:
            summary["failed"] += 1
            error_code = getattr(exc, "code", "email_reply_sync_failed")
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
                _record_sender_sync_event(
                    cursor,
                    sender_account_id=sender_id,
                    event_type="reply_sync_failed",
                    payload={"error_code": error_code},
                )
                if isinstance(exc, EmailAdapterError):
                    health_event = "auth_invalid" if exc.code == "email_auth_invalid" else "delivery_failed"
                    record_sender_health_event(
                        cursor,
                        sender_account_id=sender_id,
                        event_type=health_event,
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
