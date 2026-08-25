"""Known-lead conversation bindings and channel-neutral inbound processing."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from psycopg2.extras import Json

from services.outreach_relationship_service import upsert_relationship_from_reply
from services.outreach_safety_service import recipient_key
from services.sales_room_helpers import make_sales_room_url


HUMAN_NEGATIVE = {"not_interested", "unsubscribe", "complaint"}
TECHNICAL = {
    "out_of_office", "bounce", "temporary_delivery_failure",
    "permanent_delivery_failure", "system_acknowledgement",
}
CONFIRMED_CONTACT_STATUSES = {"confirmed_source", "verified"}


def normalize_external_peer(channel: str, value: Any) -> str:
    raw = str(value or "").strip()
    if channel == "email":
        return raw.lower()
    if channel == "telegram":
        if raw.startswith("https://t.me/"):
            raw = raw.split("https://t.me/", 1)[1]
        return raw.lstrip("@").lower()
    return raw


def business_tracking_enabled(business_id: str | None, channel: str) -> bool:
    flag = os.getenv(f"OUTREACH_{channel.upper()}_THREAD_SYNC_ENABLED", "false")
    if flag.strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    allowed = {
        item.strip() for item in os.getenv("OUTREACH_THREAD_SYNC_BUSINESS_IDS", "").split(",")
        if item.strip()
    }
    return bool(business_id and business_id in allowed)


def resolve_known_contact_binding(
    cursor: Any,
    *,
    sender_account_id: str,
    channel: str,
    external_peer_id: str,
    binding_source: str = "contact_match",
) -> dict[str, Any] | None:
    """Return/create a binding only when one confirmed contact maps to one workstream."""
    peer = normalize_external_peer(channel, external_peer_id)
    if not peer:
        return None
    peer_variants = [peer]
    if channel == "telegram":
        peer_variants.extend([f"@{peer}", f"https://t.me/{peer}", f"http://t.me/{peer}"])
    cursor.execute(
        """
        SELECT binding.*
        FROM outreach_thread_bindings binding
        WHERE binding.sender_account_id = %s
          AND binding.channel = %s
          AND binding.external_peer_id = %s
          AND binding.status = 'active'
        """,
        (sender_account_id, channel, peer),
    )
    existing = cursor.fetchone()
    if existing:
        return dict(existing)
    cursor.execute(
        """
        SELECT DISTINCT workstream.id AS workstream_id, workstream.lead_id,
               workstream.client_business_id AS business_id
        FROM lead_contact_points contact
        JOIN lead_workstreams workstream ON workstream.lead_id = contact.lead_id
        JOIN outreach_sender_accounts sender ON sender.id = %s
        WHERE contact.contact_type = %s
          AND LOWER(BTRIM(contact.normalized_value)) = ANY(%s)
          AND contact.verification_status = ANY(%s)
          AND workstream.workstream_type = 'client_partnership'
          AND (
              (sender.scope_type = 'business' AND workstream.client_business_id = sender.business_id)
              OR sender.scope_type = 'platform'
          )
          AND workstream.client_business_id = ANY(%s)
        """,
        (
            sender_account_id, channel, peer_variants, list(CONFIRMED_CONTACT_STATUSES),
            [item.strip() for item in os.getenv("OUTREACH_THREAD_SYNC_BUSINESS_IDS", "").split(",") if item.strip()],
        ),
    )
    candidates = [dict(row) for row in cursor.fetchall()]
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    if not business_tracking_enabled(str(candidate.get("business_id") or ""), channel):
        return None
    binding_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO outreach_thread_bindings (
            id, business_id, workstream_id, lead_id, sender_account_id,
            channel, external_peer_id, status, binding_source, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s, NOW(), NOW())
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        (
            binding_id, candidate.get("business_id"), candidate.get("workstream_id"),
            candidate.get("lead_id"), sender_account_id, channel, peer, binding_source,
        ),
    )
    row = cursor.fetchone()
    if row:
        return dict(row)
    cursor.execute(
        """
        SELECT * FROM outreach_thread_bindings
        WHERE sender_account_id = %s AND channel = %s
          AND external_peer_id = %s AND status = 'active'
        """,
        (sender_account_id, channel, peer),
    )
    recovered = cursor.fetchone()
    return dict(recovered) if recovered else None


def update_binding_cursor(
    cursor: Any,
    *,
    binding_id: str,
    provider_event_id: str,
    external_thread_id: str | None = None,
) -> None:
    cursor.execute(
        """
        UPDATE outreach_thread_bindings
        SET last_processed_event_id = %s,
            external_thread_id = COALESCE(NULLIF(%s, ''), external_thread_id),
            last_processed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (provider_event_id, external_thread_id or "", binding_id),
    )


def _next_action_at(raw_reply: str, occurred_at: datetime) -> datetime:
    lowered = raw_reply.lower()
    if "завтра" in lowered:
        target = occurred_at.date() + timedelta(days=1)
        return datetime.combine(target, time(hour=10), tzinfo=occurred_at.tzinfo or timezone.utc)
    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", raw_reply)
    if iso_match:
        try:
            target = date(*map(int, iso_match.groups()))
            return datetime.combine(target, time(hour=10), tzinfo=occurred_at.tzinfo or timezone.utc)
        except ValueError:
            pass
    dotted = re.search(r"\b([0-3]?\d)[./]([01]?\d)(?:[./](20\d{2}))?\b", raw_reply)
    if dotted:
        try:
            day, month = int(dotted.group(1)), int(dotted.group(2))
            year = int(dotted.group(3) or occurred_at.year)
            target = date(year, month, day)
            if target < occurred_at.date() and dotted.group(3) is None:
                target = date(year + 1, month, day)
            return datetime.combine(target, time(hour=10), tzinfo=occurred_at.tzinfo or timezone.utc)
        except ValueError:
            pass
    target = occurred_at.date() + timedelta(days=1)
    return datetime.combine(target, time(hour=10), tzinfo=occurred_at.tzinfo or timezone.utc)


def _room_for_workstream(cursor: Any, workstream_id: str) -> dict[str, Any] | None:
    cursor.execute(
        "SELECT id, slug FROM sales_rooms WHERE workstream_id = %s ORDER BY created_at LIMIT 1",
        (workstream_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _enqueue_yougile_sync(
    cursor: Any,
    *,
    inbound_event_id: str,
    message_id: str,
    binding: dict[str, Any],
    room: dict[str, Any],
    channel: str,
    classification: str,
    raw_reply: str,
    next_action_at: datetime | None,
    occurred_at: datetime,
) -> None:
    business_id = str(binding.get("business_id") or "")
    cursor.execute(
        """
        SELECT id FROM agent_integrations
        WHERE business_id = %s AND provider = 'yougile' AND status = 'active'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (business_id,),
    )
    if not cursor.fetchone():
        return
    event_id = str(uuid.uuid4())
    event_payload = {
        "inbound_event_id": inbound_event_id,
        "workstream_id": str(binding.get("workstream_id") or ""),
        "lead_id": str(binding.get("lead_id") or ""),
        "channel": channel,
        "classification": classification,
    }
    event_json = json.dumps(event_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event_hash = hashlib.sha256(event_json.encode("utf-8")).hexdigest()
    cursor.execute(
        """
        INSERT INTO communication_events (
            id, message_id, room_id, event_type, sender_ref, channel,
            provider_event_id, occurred_at, content_sha256, completeness_status,
            metadata_json, content_retention_until, metadata_retention_until,
            event_sha256, created_at
        ) VALUES (
            %s, %s, %s, 'processed', %s, %s, %s, %s, %s, 'complete',
            %s, NOW() + INTERVAL '1 year', NOW() + INTERVAL '2 years', %s, NOW()
        )
        """,
        (
            event_id, message_id, room.get("id"), binding.get("external_peer_id"), channel,
            inbound_event_id, occurred_at, hashlib.sha256(raw_reply.encode("utf-8")).hexdigest(),
            Json(event_payload), event_hash,
        ),
    )
    outbox_payload = {
        **event_payload,
        "business_id": business_id,
        "reply_excerpt": raw_reply[:1000],
        "next_action_at": next_action_at.isoformat() if next_action_at else None,
        "room_url": make_sales_room_url(str(room.get("slug") or "")),
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
        (str(uuid.uuid4()), event_id, Json(outbox_payload), hashlib.sha256(payload_json.encode("utf-8")).hexdigest()),
    )


def record_bound_inbound_event(
    cursor: Any,
    *,
    binding: dict[str, Any],
    sender_account_id: str,
    channel: str,
    provider_event_id: str,
    raw_reply: str,
    classification: dict[str, Any],
    occurred_at: datetime | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> str:
    """Atomically persist a known-lead inbound event and all LocalOS projections."""
    body = str(raw_reply or "").strip()
    if not body or not provider_event_id:
        return "unmatched"
    event_time = occurred_at or datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())
    classification_name = str(classification.get("classification") or "human_unknown")
    is_human = bool(classification.get("is_human"))
    stops_campaign = bool(classification.get("stops_campaign"))
    payload = {**(raw_payload or {}), "raw_reply": body}
    cursor.execute(
        """
        INSERT INTO outreach_inbound_events (
            id, campaign_id, touch_id, lead_id, workstream_id, sender_account_id,
            channel, provider_event_id, event_type, classification, is_human,
            stops_campaign, confidence, raw_payload_json, classified_by,
            occurred_at, created_at
        ) VALUES (
            %s, NULL, NULL, %s, %s, %s, %s, %s, 'reply', %s, %s, %s, %s,
            %s, 'reply_tracking_v1', %s, NOW()
        )
        ON CONFLICT DO NOTHING RETURNING id
        """,
        (
            event_id, binding.get("lead_id"), binding.get("workstream_id"), sender_account_id,
            channel, provider_event_id, classification_name, is_human, stops_campaign,
            float(classification.get("confidence") or 0), Json(payload), event_time,
        ),
    )
    if not cursor.fetchone():
        return "duplicate"
    update_binding_cursor(
        cursor,
        binding_id=str(binding.get("id") or ""),
        provider_event_id=provider_event_id,
        external_thread_id=str(payload.get("thread_id") or "") or None,
    )
    if not is_human:
        room = _room_for_workstream(cursor, str(binding.get("workstream_id") or ""))
        if room:
            cursor.execute(
                """
                INSERT INTO sales_room_messages (
                    id, room_id, author_type, body_text, direction, source_channel,
                    provider_event_id, delivery_status, occurred_at, idempotency_key,
                    accepted_at, processed_at, content_sha256, archive_status,
                    content_retention_until, metadata_retention_until, created_at
                ) VALUES (
                    %s, %s, 'provider', %s, 'inbound', %s, %s, 'received', %s, %s,
                    NOW(), NOW(), %s, 'pending', NOW() + INTERVAL '1 year',
                    NOW() + INTERVAL '2 years', NOW()
                ) ON CONFLICT DO NOTHING
                """,
                (
                    str(uuid.uuid4()), room.get("id"), body, channel, provider_event_id,
                    event_time, f"inbound:{channel}:{provider_event_id}",
                    hashlib.sha256(body.encode("utf-8")).hexdigest(),
                ),
            )
        return "recorded"
    workstream_id = str(binding.get("workstream_id") or "")
    business_id = str(binding.get("business_id") or "") or None
    next_action_at = _next_action_at(body, event_time)
    next_step = "Не продолжать аутрич" if classification_name in HUMAN_NEGATIVE else "Ответить и согласовать следующий шаг"
    lifecycle = "closed_lost" if classification_name in HUMAN_NEGATIVE else "replied"
    cursor.execute(
        """
        UPDATE lead_workstreams
        SET status = %s, lifecycle_status = %s, status_reason = %s,
            next_step = %s, next_action_at = %s, selected_channel = %s,
            last_contact_at = %s, last_contact_channel = %s,
            last_contact_comment = %s, state_changed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (
            lifecycle, lifecycle, classification_name, next_step,
            None if lifecycle == "closed_lost" else next_action_at,
            channel, event_time, channel, body[:1000], workstream_id,
        ),
    )
    upsert_relationship_from_reply(
        cursor,
        workstream_id=workstream_id,
        lead_id=str(binding.get("lead_id") or ""),
        scope_type="business",
        business_id=business_id,
        raw_reply=body,
        classification=classification_name,
        provider_event_id=provider_event_id,
    )
    cursor.execute(
        """
        UPDATE outreach_campaigns
        SET status = 'stopped', stop_reason = %s, updated_at = NOW()
        WHERE workstream_id = %s AND status IN ('approved', 'active', 'paused')
        """,
        (f"reply:{classification_name}", workstream_id),
    )
    cursor.execute(
        """
        UPDATE outreach_campaign_touches touch
        SET status = 'cancelled', preflight_reason = 'reply_received', updated_at = NOW()
        FROM outreach_campaigns campaign
        WHERE touch.campaign_id = campaign.id AND campaign.workstream_id = %s
          AND touch.status IN ('approved', 'scheduled', 'queued', 'awaiting_manual_send', 'paused')
        """,
        (workstream_id,),
    )
    cursor.execute(
        """
        UPDATE outreachsendqueue
        SET delivery_status = 'cancelled', preflight_reason = 'reply_received',
            error_text = NULL, updated_at = NOW()
        WHERE workstream_id = %s AND delivery_status IN ('queued', 'retry', 'paused')
        """,
        (workstream_id,),
    )
    if classification_name in HUMAN_NEGATIVE:
        cursor.execute(
            """
            INSERT INTO outreach_suppressions (
                id, lead_id, workstream_id, scope_type, business_id, recipient_key,
                reason_code, source, created_at, updated_at
            ) SELECT %s, %s, %s, 'business', %s, %s, %s, 'reply_tracking', NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM outreach_suppressions
                WHERE workstream_id = %s AND reason_code = %s
            )
            """,
            (
                str(uuid.uuid4()), binding.get("lead_id"), workstream_id, business_id,
                recipient_key(str(binding.get("lead_id") or "")), classification_name,
                workstream_id, classification_name,
            ),
        )
    room = _room_for_workstream(cursor, workstream_id)
    if room:
        message_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO sales_room_messages (
                id, room_id, author_type, body_text, direction, source_channel,
                provider_event_id, delivery_status, occurred_at, idempotency_key,
                accepted_at, processed_at, content_sha256, archive_status,
                content_retention_until, metadata_retention_until, created_at
            ) VALUES (
                %s, %s, 'recipient', %s, 'inbound', %s, %s, 'received', %s, %s,
                NOW(), NOW(), %s, 'pending', NOW() + INTERVAL '1 year',
                NOW() + INTERVAL '2 years', NOW()
            ) ON CONFLICT DO NOTHING
            """,
            (
                message_id, room.get("id"), body, channel, provider_event_id, event_time,
                f"inbound:{channel}:{provider_event_id}", hashlib.sha256(body.encode("utf-8")).hexdigest(),
            ),
        )
        if cursor.rowcount:
            _enqueue_yougile_sync(
                cursor,
                inbound_event_id=event_id,
                message_id=message_id,
                binding=binding,
                room=room,
                channel=channel,
                classification=classification_name,
                raw_reply=body,
                next_action_at=None if lifecycle == "closed_lost" else next_action_at,
                occurred_at=event_time,
            )
    return "recorded"
