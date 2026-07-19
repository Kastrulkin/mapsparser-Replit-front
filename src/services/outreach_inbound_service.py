from __future__ import annotations

import uuid
from typing import Any

from psycopg2.extras import Json

from services.outreach_safety_service import recipient_key, record_learning_event


def record_campaign_inbound_reaction(
    cursor: Any,
    *,
    queue_payload: dict[str, Any],
    reaction_id: str,
    user_id: str,
    raw_reply: str,
    final_outcome: str | None,
    provider_message_id: str | None,
    classifier_source: str,
    reply_created_at: Any,
    inbound_classification: dict[str, Any],
    classification_payload: dict[str, Any],
) -> None:
    """Persist an inbound campaign event and apply stop-on-reply atomically."""
    touch_id = queue_payload.get("campaign_touch_id")
    if not touch_id or not raw_reply.strip():
        return
    actor_id = None if str(user_id or "").startswith("system:") else user_id
    cursor.execute(
        """
        SELECT t.*, c.scope_type, c.business_id, c.workstream_id,
               ws.workstream_type
        FROM outreach_campaign_touches t
        JOIN outreach_campaigns c ON c.id = t.campaign_id
        JOIN lead_workstreams ws ON ws.id = c.workstream_id
        WHERE t.id = %s
        """,
        (touch_id,),
    )
    touch_row = cursor.fetchone()
    if not touch_row:
        return
    touch = dict(touch_row)
    campaign_id = str(touch["campaign_id"])
    classification = str(inbound_classification["classification"])
    cursor.execute(
        """
        INSERT INTO outreach_inbound_events (
            id, campaign_id, touch_id, lead_id, workstream_id,
            sender_account_id, channel, provider_event_id, event_type,
            classification, is_human, stops_campaign, confidence,
            raw_payload_json, classified_by, occurred_at, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, ''), 'reply',
            %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), NOW()
        )
        ON CONFLICT DO NOTHING
        """,
        (
            str(uuid.uuid4()), campaign_id, touch_id, queue_payload["lead_id"],
            queue_payload.get("workstream_id"), touch.get("sender_account_id"),
            touch.get("channel"), provider_message_id or "", classification,
            inbound_classification["is_human"], inbound_classification["stops_campaign"],
            inbound_classification["confidence"],
            Json({
                "raw_reply": raw_reply.strip(),
                "outcome": final_outcome,
                "subject": classification_payload.get("subject"),
                "auto_submitted": classification_payload.get("auto_submitted"),
                "precedence": classification_payload.get("precedence"),
            }),
            classifier_source, reply_created_at,
        ),
    )
    if inbound_classification["creates_suppression"]:
        cursor.execute(
            """
            INSERT INTO outreach_suppressions (
                id, lead_id, workstream_id, scope_type, business_id,
                recipient_key, reason_code, source, created_by,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'reply_sync', %s, NOW(), NOW())
            """,
            (
                str(uuid.uuid4()), queue_payload["lead_id"],
                queue_payload.get("workstream_id"), touch.get("scope_type"),
                touch.get("business_id"), recipient_key(str(queue_payload["lead_id"])),
                classification, actor_id,
            ),
        )
    if inbound_classification["stops_campaign"]:
        _stop_campaign_after_reply(
            cursor,
            campaign_id=campaign_id,
            touch=touch,
            queue_payload=queue_payload,
            classification=classification,
            reply_created_at=reply_created_at,
            actor_id=actor_id,
        )
    elif classification in {
        "out_of_office", "bounce", "temporary_delivery_failure",
        "permanent_delivery_failure", "system_acknowledgement",
    }:
        cursor.execute(
            """
            UPDATE outreach_campaigns
            SET status = 'paused', needs_attention_reason = %s, updated_at = NOW()
            WHERE id = %s AND status IN ('approved', 'active')
            """,
            (classification, campaign_id),
        )
        cursor.execute(
            """
            UPDATE lead_workstreams
            SET lifecycle_status = 'needs_attention', status_reason = %s,
                next_step = 'Проверить технический ответ', state_changed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (classification, queue_payload.get("workstream_id")),
        )
    _record_learning(
        cursor,
        campaign_id=campaign_id,
        touch=touch,
        reaction_id=reaction_id,
        classification=classification,
        reply_created_at=reply_created_at,
    )
    cursor.execute(
        """
        INSERT INTO outreach_campaign_events (
            id, campaign_id, touch_id, event_type, reason_code,
            payload_json, actor_id, created_at
        ) VALUES (%s, %s, %s, 'reply_received', %s, %s, %s, NOW())
        """,
        (
            str(uuid.uuid4()), campaign_id, touch_id, classification,
            Json({
                "queue_id": queue_payload.get("id"),
                "outcome": final_outcome,
                "is_human": inbound_classification["is_human"],
                "stops_campaign": inbound_classification["stops_campaign"],
            }),
            actor_id,
        ),
    )


def _stop_campaign_after_reply(
    cursor: Any,
    *,
    campaign_id: str,
    touch: dict[str, Any],
    queue_payload: dict[str, Any],
    classification: str,
    reply_created_at: Any,
    actor_id: str | None,
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_campaign_events (
            id, campaign_id, touch_id, event_type, reason_code,
            payload_json, actor_id, created_at
        )
        SELECT %s, %s, queue.campaign_touch_id, 'dispatch_reply_race',
               'reply_arrived_during_provider_call',
               jsonb_build_object(
                   'queue_id', queue.id,
                   'dispatch_started_at', queue.dispatch_started_at,
                   'reply_created_at', COALESCE(%s, NOW()),
                   'channel', queue.channel
               ), %s, NOW()
        FROM outreachsendqueue queue
        WHERE queue.campaign_touch_id IN (
            SELECT id FROM outreach_campaign_touches WHERE campaign_id = %s
        )
          AND queue.delivery_status = 'sending'
        LIMIT 1
        """,
        (str(uuid.uuid4()), campaign_id, reply_created_at, actor_id, campaign_id),
    )
    cursor.execute(
        """
        UPDATE outreach_campaigns
        SET status = 'stopped', stop_reason = 'recipient_replied',
            last_reply_at = COALESCE(%s, NOW()), updated_at = NOW()
        WHERE id = %s
        """,
        (reply_created_at, campaign_id),
    )
    cursor.execute(
        """
        UPDATE outreach_campaign_touches
        SET status = 'reply_cancelled',
            delivery_json = delivery_json || %s,
            updated_at = NOW()
        WHERE campaign_id = %s
          AND sequence_index > %s
          AND status IN (
              'approved', 'scheduled', 'queued', 'manual',
              'awaiting_manual_send', 'needs_attention', 'paused'
          )
        """,
        (
            Json({"stop_reason": "recipient_replied", "classification": classification}),
            campaign_id, touch["sequence_index"],
        ),
    )
    cursor.execute(
        """
        UPDATE outreachsendqueue
        SET delivery_status = 'failed', error_text = 'recipient_replied',
            preflight_reason = 'recipient_replied', updated_at = NOW()
        WHERE campaign_touch_id IN (
            SELECT id FROM outreach_campaign_touches
            WHERE campaign_id = %s AND status = 'reply_cancelled'
        )
          AND delivery_status IN ('queued', 'retry', 'paused')
        """,
        (campaign_id,),
    )
    cursor.execute(
        """
        UPDATE lead_workstreams
        SET lifecycle_status = 'replied', status_reason = %s,
            next_step = 'Ответить получателю вручную', state_changed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (classification, queue_payload.get("workstream_id")),
    )


def _record_learning(
    cursor: Any,
    *,
    campaign_id: str,
    touch: dict[str, Any],
    reaction_id: str,
    classification: str,
    reply_created_at: Any,
) -> None:
    learning_outcome = {
        "interested": "positive_reply",
        "question": "question",
        "not_interested": "hard_no",
        "unsubscribe": "unsubscribe",
        "complaint": "complaint",
        "human_unknown": "replied",
    }.get(classification)
    if not learning_outcome or not touch.get("strategy_fingerprint"):
        return
    record_learning_event(
        cursor,
        campaign={
            "id": campaign_id,
            "scope_type": touch.get("scope_type"),
            "business_id": touch.get("business_id"),
            "workstream_type": touch.get("workstream_type"),
        },
        touch=touch,
        outcome_type=learning_outcome,
        payload={"reaction_id": reaction_id, "classification": classification},
        occurred_at=reply_created_at,
    )
