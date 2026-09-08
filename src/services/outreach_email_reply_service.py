from __future__ import annotations

import re
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json

from pg_db_utils import get_db_connection
from services.outreach_email_adapter import (
    COMPLETE_REPLY_MAILBOX_ROLES,
    DEFAULT_COMPLETE_SYNC_MESSAGE_LIMIT,
    EmailAdapterError,
    email_recipient_hashes,
    email_recipient_scope_fingerprint,
    fetch_complete_mailbox_window,
    fetch_mailbox_messages,
    fetch_replies,
    mailbox_identity_fingerprint,
    normalize_email,
    normalize_recipient_scope,
)
from services.outreach_reply_sync_receipt import (
    EMAIL_REPLY_SYNC_PROVIDER,
    EMAIL_REPLY_SYNC_RECEIPT_VERSION,
    EMAIL_REPLY_SYNC_SCOPE,
    build_email_reply_sync_receipt,
)
from services.outreach_reply_tracking_service import (
    business_tracking_enabled,
    record_bound_inbound_event,
    resolve_known_contact_binding,
    update_binding_cursor,
)
from services.outreach_safety_service import classify_inbound_event, record_sender_health_event


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _reference_tokens(reply: dict[str, Any]) -> set[str]:
    raw = " ".join(
        str(reply.get(key) or "")
        for key in ("in_reply_to", "references", "body", "dsn_original_message_ids")
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
                   q.provider_message_id,
                   COALESCE(contact.normalized_value, q.recipient_value) AS recipient_value,
                   q.sent_at,
                   touch.contact_point_id, touch.sequence_index,
                   touch.campaign_id, campaign.status AS campaign_status
            FROM outreachsendqueue q
            JOIN outreach_campaign_touches touch ON touch.id = q.campaign_touch_id
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id = q.workstream_id
            JOIN prospectingleads lead ON lead.id = q.lead_id
            JOIN creator_profiles creator
              ON lead.source_external_id = 'creator:' || creator.id::text
            LEFT JOIN lead_contact_points contact ON contact.id = touch.contact_point_id
            WHERE q.sender_account_id = %s
              AND q.channel = 'email'
              AND q.provider_name = 'native_email'
              AND q.delivery_status IN ('sent', 'delivered')
              AND q.sent_at >= NOW() - INTERVAL '45 days'
              AND workstream.workstream_type = 'creator_collaboration'
              AND campaign.sender_mode = 'localos_for_partner'
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


def _load_email_reply_scope_candidates(
    sender_account_id: str,
    campaign_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load only approved/claimed author targets and recent author conversations."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT q.id, q.delivery_status, q.sent_at, touch.campaign_id,
                   COALESCE(contact.normalized_value, q.recipient_value) AS recipient_value
            FROM outreachsendqueue q
            JOIN outreachsendbatches batch ON batch.id = q.batch_id
            JOIN outreach_campaign_touches touch ON touch.id = q.campaign_touch_id
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id = q.workstream_id
            JOIN prospectingleads lead ON lead.id = q.lead_id
            JOIN creator_profiles creator
              ON lead.source_external_id = 'creator:' || creator.id::text
            LEFT JOIN lead_contact_points contact ON contact.id = touch.contact_point_id
            WHERE q.sender_account_id = %s
              AND q.channel = 'email'
              AND workstream.workstream_type = 'creator_collaboration'
              AND campaign.sender_mode = 'localos_for_partner'
              AND contact.contact_type = 'email'
              AND COALESCE(contact.normalized_value, q.recipient_value) IS NOT NULL
              AND (
                    (
                        q.delivery_status IN ('queued', 'retry', 'sending')
                        AND batch.status = 'approved'
                        AND campaign.status IN ('approved', 'active')
                        AND campaign.approved_at IS NOT NULL
                        AND campaign.approved_snapshot_hash IS NOT NULL
                        AND touch.status IN ('approved', 'scheduled', 'queued')
                    )
                    OR (
                        q.delivery_status IN ('sent', 'delivered')
                        AND q.sent_at >= NOW() - INTERVAL '45 days'
                    )
              )
        """
        params: list[Any] = [sender_account_id]
        if campaign_id:
            query += " AND touch.campaign_id = %s"
            params.append(campaign_id)
        query += " ORDER BY COALESCE(q.sent_at, q.created_at) ASC LIMIT 1000"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _load_non_author_queue_candidates(
    sender_account_id: str,
    campaign_id: str | None = None,
) -> list[dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT q.id, q.lead_id, q.workstream_id, q.campaign_touch_id,
                   q.provider_message_id,
                   COALESCE(contact.normalized_value, q.recipient_value) AS recipient_value,
                   q.sent_at, touch.contact_point_id, touch.sequence_index,
                   touch.campaign_id, campaign.status AS campaign_status
            FROM outreachsendqueue q
            JOIN outreach_campaign_touches touch ON touch.id = q.campaign_touch_id
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id = q.workstream_id
            LEFT JOIN prospectingleads lead ON lead.id = q.lead_id
            LEFT JOIN creator_profiles creator
              ON lead.source_external_id = 'creator:' || creator.id::text
            LEFT JOIN lead_contact_points contact ON contact.id = touch.contact_point_id
            WHERE q.sender_account_id = %s
              AND q.channel = 'email'
              AND q.provider_name = 'native_email'
              AND q.delivery_status IN ('sent', 'delivered')
              AND NOT (
                  workstream.workstream_type = 'creator_collaboration'
                  AND campaign.sender_mode = 'localos_for_partner'
                  AND creator.id IS NOT NULL
              )
        """
        params: list[Any] = [sender_account_id]
        if campaign_id:
            query += " AND touch.campaign_id = %s"
            params.append(campaign_id)
        query += " ORDER BY q.sent_at DESC LIMIT 1001"
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        if len(rows) > 1000:
            raise EmailAdapterError(
                "email_reply_sync_non_author_scope_limit_exceeded",
                "Non-author reply scope exceeds the bounded synchronization limit",
            )
        return rows
    finally:
        conn.close()


def _match_queue_item(reply: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    references = _reference_tokens(reply)
    for candidate in candidates:
        message_id = str(candidate.get("provider_message_id") or "").strip().lower()
        if message_id and message_id in references:
            return candidate
    from_email = normalize_email(reply.get("from_email"))
    dsn_recipients = {
        normalize_email(value)
        for value in (reply.get("dsn_recipient_emails") or [])
        if normalize_email(value)
    }
    occurred_at = reply.get("occurred_at")
    body_lower = str(reply.get("body") or "").lower()
    for candidate in candidates:
        recipient = normalize_email(candidate.get("recipient_value"))
        sent_at = candidate.get("sent_at")
        if occurred_at and sent_at and occurred_at < sent_at - timedelta(minutes=5):
            continue
        if recipient and (
            recipient == from_email
            or recipient in dsn_recipients
            or recipient in body_lower
        ):
            return candidate
    return None


def _sync_known_email_threads(
    sender: dict[str, Any],
    *,
    sent_messages: list[dict[str, Any]],
    inbox_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Discover manual Sent threads and import Inbox replies for known leads only."""
    platform_enabled = (
        str(sender.get("scope_type") or "") == "platform"
        and str(os.getenv("OUTREACH_EMAIL_THREAD_SYNC_ENABLED") or "false").strip().lower()
        in {"1", "true", "yes", "on"}
        and any(value.strip() for value in os.getenv("OUTREACH_THREAD_SYNC_BUSINESS_IDS", "").split(","))
    )
    if not platform_enabled and not business_tracking_enabled(str(sender.get("business_id") or ""), "email"):
        return {"bound": 0, "imported": 0, "duplicates": 0, "processed_event_ids": set()}
    sender_id = str(sender.get("id") or "")
    summary = {"bound": 0, "imported": 0, "duplicates": 0, "processed_event_ids": set()}
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for message in sent_messages:
            for recipient in message.get("to_emails") or []:
                binding = resolve_known_contact_binding(
                    cursor,
                    sender_account_id=sender_id,
                    channel="email",
                    external_peer_id=recipient,
                    binding_source="sent_message",
                )
                if not binding:
                    continue
                update_binding_cursor(
                    cursor,
                    binding_id=str(binding.get("id") or ""),
                    provider_event_id=str(message.get("provider_event_id") or ""),
                    external_thread_id=str(message.get("message_id") or "") or None,
                )
                summary["bound"] += 1
        for message in inbox_messages:
            provider_event_id = str(message.get("provider_event_id") or "")
            binding = resolve_known_contact_binding(
                cursor,
                sender_account_id=sender_id,
                channel="email",
                external_peer_id=str(message.get("from_email") or ""),
            )
            if not binding:
                continue
            classification = classify_inbound_event({
                "classification": message.get("dsn_classification"),
                "subject": message.get("subject"),
                "body": message.get("body"),
                "raw_reply": message.get("body"),
                "auto_submitted": message.get("auto_submitted"),
                "precedence": message.get("precedence"),
            })
            status = record_bound_inbound_event(
                cursor,
                binding=binding,
                sender_account_id=sender_id,
                channel="email",
                provider_event_id=provider_event_id,
                raw_reply=str(message.get("body") or message.get("subject") or ""),
                classification=classification,
                occurred_at=message.get("occurred_at"),
                raw_payload={
                    "subject": message.get("subject"),
                    "message_id": message.get("message_id"),
                    "in_reply_to": message.get("in_reply_to"),
                    "references": message.get("references"),
                    "mailbox_uid": message.get("mailbox_uid"),
                    "thread_id": message.get("in_reply_to") or message.get("message_id"),
                    "auto_submitted": message.get("auto_submitted"),
                    "precedence": message.get("precedence"),
                    "dsn_recipient_emails": message.get("dsn_recipient_emails") or [],
                    "dsn_original_message_ids": message.get("dsn_original_message_ids") or [],
                    "dsn_classification": message.get("dsn_classification"),
                },
            )
            summary["processed_event_ids"].add(provider_event_id)
            if status == "recorded":
                summary["imported"] += 1
            elif status == "duplicate":
                summary["duplicates"] += 1
        conn.commit()
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
                    "message_id": reply.get("message_id"),
                    "dsn_recipient_emails": reply.get("dsn_recipient_emails") or [],
                    "dsn_original_message_ids": reply.get("dsn_original_message_ids") or [],
                    "dsn_classification": reply.get("dsn_classification"),
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


def _sync_legacy_non_author_sender(
    sender: dict[str, Any],
    *,
    campaign_id: str | None,
    limit: int,
) -> dict[str, int]:
    """Preserve the pre-existing limited Inbox/Sent importer outside the author lane."""
    sender_id = str(sender.get("id") or "")
    sync_started_at = datetime.now(timezone.utc)
    since_at = sender.get("last_reply_sync_at")
    if not isinstance(since_at, datetime):
        since_at = datetime.now(timezone.utc) - timedelta(days=30)
    sent_messages = fetch_mailbox_messages(
        sender,
        mailbox="sent",
        since_at=since_at - timedelta(minutes=10),
        limit=limit,
    )
    replies = fetch_replies(
        sender,
        since_at=since_at - timedelta(minutes=10),
        limit=limit,
    )
    known_threads = _sync_known_email_threads(
        sender,
        sent_messages=sent_messages,
        inbox_messages=replies,
    )
    candidates = _load_non_author_queue_candidates(sender_id, campaign_id=campaign_id)
    counts = {
        "fetched": len(replies),
        "matched": 0,
        "imported": int(known_threads["imported"]),
        "technical": 0,
        "duplicates": int(known_threads["duplicates"]),
        "unmatched": 0,
        "failed": 0,
        "bound": int(known_threads["bound"]),
    }
    for reply in replies:
        if reply.get("provider_event_id") in known_threads["processed_event_ids"]:
            continue
        queue_item = _match_queue_item(reply, candidates)
        if not queue_item:
            counts["unmatched"] += 1
            continue
        counts["matched"] += 1
        classification = classify_inbound_event({
            "classification": reply.get("dsn_classification"),
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
                counts["technical"] += 1
        if status == "recorded":
            counts["imported"] += 1
        elif status == "duplicate":
            counts["duplicates"] += 1
        elif status == "unmatched":
            counts["unmatched"] += 1
        else:
            counts["failed"] += 1
    if counts["failed"]:
        raise EmailAdapterError(
            "email_reply_import_failed",
            "One or more fetched non-author replies could not be durably imported",
        )
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE outreach_sender_accounts
            SET last_reply_sync_at = %s, reply_sync_error = NULL, updated_at = NOW()
            WHERE id = %s
            """,
            (sync_started_at, sender_id),
        )
        _record_sender_sync_event(
            cursor,
            sender_account_id=sender_id,
            event_type="reply_sync_succeeded",
            payload={
                "receipt_version": 1,
                "scope": "legacy_non_author_inbox_sent_limited",
                "complete": False,
                "fetched": counts["fetched"],
                "imported": counts["imported"],
                "unmatched": counts["unmatched"],
                "manual_threads_bound": counts["bound"],
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts


def sync_email_replies(
    *,
    sender_limit: int = 25,
    per_sender_limit: int = 100,
    sender_account_id: str | None = None,
    campaign_id: str | None = None,
    complete_window_limit: int | None = None,
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
    configured_complete_limit = max(
        1,
        min(
            int(
                complete_window_limit
                or os.getenv(
                    "OUTREACH_EMAIL_COMPLETE_SYNC_MAX_MESSAGES",
                    str(DEFAULT_COMPLETE_SYNC_MESSAGE_LIMIT),
                )
            ),
            20000,
        ),
    )
    for sender in senders:
        sender_id = str(sender.get("id") or "")
        sync_started_at = datetime.now(timezone.utc)
        window_started_at = sync_started_at - timedelta(days=45, minutes=10)
        recipient_emails: list[str] = []
        folder_receipts: list[dict[str, Any]] = []
        try:
            scope_candidates = _load_email_reply_scope_candidates(
                sender_id,
                campaign_id=campaign_id,
            )
            if not scope_candidates:
                legacy = _sync_legacy_non_author_sender(
                    sender,
                    campaign_id=campaign_id,
                    limit=per_sender_limit,
                )
                for key in ("fetched", "matched", "imported", "technical", "duplicates", "unmatched", "failed"):
                    summary[key] += int(legacy[key])
                summary["sender_results"].append({
                    "sender_account_id": sender_id,
                    "status": "ok",
                    "scope": "legacy_non_author",
                    "fetched": legacy["fetched"],
                    "imported": legacy["imported"],
                })
                continue
            non_author_candidates = _load_non_author_queue_candidates(
                sender_id,
                campaign_id=None,
            )
            recipient_emails = normalize_recipient_scope([
                str(candidate.get("recipient_value") or "")
                for candidate in scope_candidates
            ])
            non_author_recipient_emails = (
                normalize_recipient_scope([
                    str(candidate.get("recipient_value") or "")
                    for candidate in non_author_candidates
                ])
                if non_author_candidates
                else []
            )
            if set(recipient_emails).intersection(non_author_recipient_emails):
                raise EmailAdapterError(
                    "email_reply_sync_recipient_scope_overlap",
                    "One recipient belongs to both author and non-author reply scopes",
                )
            remaining_message_limit = configured_complete_limit
            scoped_messages: list[dict[str, Any]] = []
            for mailbox_role in COMPLETE_REPLY_MAILBOX_ROLES:
                mailbox_window = fetch_complete_mailbox_window(
                    sender,
                    mailbox=mailbox_role,
                    since_at=window_started_at,
                    until_at=sync_started_at,
                    max_messages=remaining_message_limit,
                    recipient_emails=recipient_emails,
                )
                folder_receipt = mailbox_window["folder"]
                folder_receipts.append(folder_receipt)
                remaining_message_limit -= int(folder_receipt.get("candidate_uid_count") or 0)
                scoped_messages.extend(mailbox_window["messages"])
            replies: list[dict[str, Any]] = []
            seen_messages: set[str] = set()
            for message in scoped_messages:
                stable_key = str(message.get("message_id") or message.get("provider_event_id") or "")
                if stable_key and stable_key in seen_messages:
                    continue
                if stable_key:
                    seen_messages.add(stable_key)
                replies.append(message)
            known_threads = {
                "bound": 0,
                "imported": 0,
                "duplicates": 0,
                "processed_event_ids": set(),
            }
            candidates = _load_queue_candidates(sender_id, campaign_id=campaign_id)
            sender_imported = 0
            sender_unmatched = 0
            sender_processing_failures = 0
            for reply in replies:
                summary["fetched"] += 1
                if reply.get("provider_event_id") in known_threads["processed_event_ids"]:
                    continue
                queue_item = _match_queue_item(reply, candidates)
                if not queue_item:
                    summary["unmatched"] += 1
                    sender_unmatched += 1
                    continue
                summary["matched"] += 1
                classification = classify_inbound_event({
                    "classification": reply.get("dsn_classification"),
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
                    sender_processing_failures += 1
            if sender_processing_failures:
                raise EmailAdapterError(
                    "email_reply_import_failed",
                    "One or more fetched replies could not be durably imported",
                )
            if sender_unmatched:
                raise EmailAdapterError(
                    "email_reply_unmatched_scoped_message",
                    "A recipient-scoped inbound message could not be durably associated",
                )
            non_author_replies: list[dict[str, Any]] = []
            non_author_imported = 0
            non_author_duplicates = 0
            non_author_unmatched = 0
            non_author_bound = 0
            if non_author_recipient_emails:
                non_author_scoped_messages: list[dict[str, Any]] = []
                for mailbox_role in COMPLETE_REPLY_MAILBOX_ROLES:
                    mailbox_window = fetch_complete_mailbox_window(
                        sender,
                        mailbox=mailbox_role,
                        since_at=window_started_at,
                        until_at=sync_started_at,
                        max_messages=remaining_message_limit,
                        recipient_emails=non_author_recipient_emails,
                    )
                    remaining_message_limit -= int(
                        mailbox_window["folder"].get("candidate_uid_count") or 0
                    )
                    non_author_scoped_messages.extend(mailbox_window["messages"])
                seen_non_author_messages: set[str] = set()
                for message in non_author_scoped_messages:
                    stable_key = str(
                        message.get("message_id")
                        or message.get("provider_event_id")
                        or ""
                    )
                    if stable_key and stable_key in seen_non_author_messages:
                        continue
                    if stable_key:
                        seen_non_author_messages.add(stable_key)
                    non_author_replies.append(message)
                non_author_threads = _sync_known_email_threads(
                    sender,
                    sent_messages=[],
                    inbox_messages=non_author_replies,
                )
                non_author_imported += int(non_author_threads["imported"])
                non_author_duplicates += int(non_author_threads["duplicates"])
                non_author_bound = int(non_author_threads["bound"])
                non_author_processing_failures = 0
                for reply in non_author_replies:
                    summary["fetched"] += 1
                    if reply.get("provider_event_id") in non_author_threads["processed_event_ids"]:
                        continue
                    queue_item = _match_queue_item(reply, non_author_candidates)
                    if not queue_item:
                        summary["unmatched"] += 1
                        non_author_unmatched += 1
                        continue
                    summary["matched"] += 1
                    classification = classify_inbound_event({
                        "classification": reply.get("dsn_classification"),
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
                        non_author_imported += 1
                    elif status == "duplicate":
                        non_author_duplicates += 1
                    elif status == "unmatched":
                        summary["unmatched"] += 1
                        non_author_unmatched += 1
                    else:
                        non_author_processing_failures += 1
                if non_author_processing_failures:
                    raise EmailAdapterError(
                        "email_reply_import_failed",
                        "One or more fetched non-author replies could not be durably imported",
                    )
                if non_author_unmatched:
                    raise EmailAdapterError(
                        "email_reply_unmatched_scoped_message",
                        "A recipient-scoped non-author message could not be durably associated",
                    )
                summary["imported"] += non_author_imported
                summary["duplicates"] += non_author_duplicates
            completed_at = datetime.now(timezone.utc)
            receipt = build_email_reply_sync_receipt(
                sender,
                recipient_emails=recipient_emails,
                sync_started_at=sync_started_at,
                window_started_at=window_started_at,
                covered_through=sync_started_at,
                completed_at=completed_at,
                folders=folder_receipts,
                message_limit=configured_complete_limit,
                counters={
                    "scoped_messages": len(scoped_messages),
                    "unique_messages": len(replies),
                    "imported": sender_imported + int(known_threads["imported"]),
                    "duplicates": int(known_threads["duplicates"]),
                    "unmatched": sender_unmatched,
                    "manual_threads_bound": int(known_threads["bound"]),
                },
            )
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE outreach_sender_accounts
                    SET last_reply_sync_at = %s, reply_sync_error = NULL, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (sync_started_at, sender_id),
                )
                _record_sender_sync_event(
                    cursor,
                    sender_account_id=sender_id,
                    event_type="reply_sync_succeeded",
                    payload=receipt,
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
                "scope": (
                    "author_and_non_author_scoped"
                    if non_author_recipient_emails
                    else "author_scoped"
                ),
                "fetched": len(replies) + len(non_author_replies),
                "recipient_count": len(recipient_emails),
                "author_recipient_count": len(recipient_emails),
                "non_author_recipient_count": len(non_author_recipient_emails),
                "imported": (
                    sender_imported
                    + int(known_threads["imported"])
                    + non_author_imported
                ),
                "manual_threads_bound": int(known_threads["bound"]) + non_author_bound,
            })
            summary["imported"] += int(known_threads["imported"])
            summary["duplicates"] += int(known_threads["duplicates"])
        except Exception as exc:
            summary["failed"] += 1
            error_code = getattr(exc, "code", "email_reply_sync_failed")
            failure_identity_fingerprint = None
            failure_recipient_hashes: list[str] = []
            failure_recipient_scope_hash = None
            if recipient_emails:
                try:
                    failure_identity_fingerprint = mailbox_identity_fingerprint(sender)
                    failure_recipient_hashes = email_recipient_hashes(recipient_emails)
                    failure_recipient_scope_hash = email_recipient_scope_fingerprint(
                        sender,
                        recipient_emails,
                    )
                except (EmailAdapterError, ValueError, TypeError):
                    pass
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
                    payload={
                        "receipt_version": EMAIL_REPLY_SYNC_RECEIPT_VERSION,
                        "sender_account_id": sender_id,
                        "sender_scope_type": str(sender.get("scope_type") or ""),
                        "sender_business_id": str(sender.get("business_id") or "") or None,
                        "channel": "email",
                        "provider": EMAIL_REPLY_SYNC_PROVIDER,
                        "provider_identity_fingerprint": failure_identity_fingerprint,
                        "scope": EMAIL_REPLY_SYNC_SCOPE,
                        "recipient_hashes": failure_recipient_hashes,
                        "recipient_count": len(failure_recipient_hashes),
                        "recipient_scope_hash": failure_recipient_scope_hash,
                        "message_limit": configured_complete_limit,
                        "window_started_at": window_started_at.isoformat(),
                        "covered_through": None,
                        "sync_started_at": sync_started_at.isoformat(),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "complete": False,
                        "truncated": error_code == "email_imap_window_limit_exceeded",
                        "failure_count": 1,
                        "folders": folder_receipts,
                        "error_code": error_code,
                    },
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
