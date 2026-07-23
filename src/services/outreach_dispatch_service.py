"""Outreach send-queue dispatch runtime.

The public compatibility entrypoint still lives in ``api.admin_prospecting``.
This module owns the dispatcher body so worker/runtime code can move away from
the large admin route module without changing behavior.
"""
from __future__ import annotations

from typing import Any

from services.outreach_safety_service import (
    block_queue_item_after_preflight,
    persist_preflight_result,
    record_sender_health_event,
    record_touch_learning_event,
    run_dispatch_preflight,
)


def dispatch_due_outreach_queue(
    batch_size: int = 20,
    batch_id: str | None = None,
    force_ready: bool = False,
    queue_id: str | None = None,
    campaign_only: bool = False,
    allowed_business_ids: list[str] | None = None,
    allow_platform: bool = False,
) -> dict[str, Any]:
    """Dispatch queued/retry outreach items to the configured outbound provider."""
    from api import admin_prospecting as p

    safe_batch_size = max(1, min(int(batch_size or 20), 200))
    cohort_business_ids = sorted({
        str(item or "").strip()
        for item in (allowed_business_ids or [])
        if str(item or "").strip()
    })
    if campaign_only and not allow_platform and not cohort_business_ids:
        return {
            "success": True,
            "batch_id": batch_id,
            "queue_id": queue_id,
            "picked": 0,
            "sent": 0,
            "delivered": 0,
            "retry": 0,
            "dlq": 0,
            "failed": 0,
            "blocked": 0,
            "results": [],
            "reason_code": "dispatch_cohort_not_configured",
        }
    conn = p.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM outreachsendqueue
            WHERE sent_at >= CURRENT_DATE
              AND delivery_status IN (%s, %s)
            """,
            (p.QUEUE_STATUS_SENT, p.QUEUE_STATUS_DELIVERED),
        )
        sent_row = cur.fetchone()
        sent_today = int(
            (sent_row.get("count") if hasattr(sent_row, "get") else sent_row[0] if sent_row else 0)
            or 0
        )
        safe_batch_size = min(safe_batch_size, max(0, int(p.MAX_DAILY_OUTREACH_BATCH) - sent_today))
        if safe_batch_size <= 0:
            return {
                "success": True,
                "batch_id": batch_id,
                "queue_id": queue_id,
                "picked": 0,
                "sent": 0,
                "delivered": 0,
                "retry": 0,
                "dlq": 0,
                "failed": 0,
                "blocked": 0,
                "results": [],
                "reason_code": "daily_limit_reached",
            }
        query = """
            WITH due AS (
                SELECT
                    q.id
                FROM outreachsendqueue q
                JOIN outreachsendbatches b ON b.id = q.batch_id
                WHERE b.status = %s
                  AND (q.scheduled_at IS NULL OR q.scheduled_at <= NOW())
                  AND NOT EXISTS (
                      SELECT 1 FROM outreach_suppressions s
                      WHERE s.lead_id = q.lead_id
                        AND (s.workstream_id IS NULL OR s.workstream_id = q.workstream_id)
                        AND (s.expires_at IS NULL OR s.expires_at > NOW())
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM outreachsendqueue previous
                      WHERE previous.lead_id = q.lead_id
                        AND previous.id <> q.id
                        AND previous.sent_at > NOW() - INTERVAL '12 hours'
                        AND previous.delivery_status IN ('sent', 'delivered')
                  )
                  AND (
                      q.campaign_touch_id IS NULL
                      OR EXISTS (
                          SELECT 1
                          FROM outreach_campaign_touches t
                          JOIN outreach_campaigns c ON c.id = t.campaign_id
                          WHERE t.id = q.campaign_touch_id
                            AND t.status IN ('approved', 'scheduled', 'queued')
                            AND c.status IN ('approved', 'active')
                      )
                  )
        """
        params: list[Any] = [p.BATCH_APPROVED]
        if batch_id:
            query += " AND q.batch_id = %s"
            params.append(batch_id)
        if queue_id:
            query += " AND q.id = %s"
            params.append(queue_id)
        if campaign_only:
            query += " AND q.campaign_touch_id IS NOT NULL"
            cohort_clauses: list[str] = []
            if allow_platform:
                cohort_clauses.append("campaign.scope_type = 'platform'")
            if cohort_business_ids:
                placeholders = ",".join(["%s"] * len(cohort_business_ids))
                cohort_clauses.append(
                    f"(campaign.scope_type = 'business' AND campaign.business_id IN ({placeholders}))"
                )
                params.extend(cohort_business_ids)
            query += f"""
                AND EXISTS (
                    SELECT 1
                    FROM outreach_campaign_touches cohort_touch
                    JOIN outreach_campaigns campaign ON campaign.id = cohort_touch.campaign_id
                    WHERE cohort_touch.id = q.campaign_touch_id
                      AND ({' OR '.join(cohort_clauses)})
                )
            """
        query += """
                  AND (
                    q.delivery_status = %s
        """
        params.append(p.QUEUE_STATUS_QUEUED)
        if force_ready:
            query += """
                    OR q.delivery_status = %s
            """
            params.append(p.QUEUE_STATUS_RETRY)
        else:
            query += """
                    OR (
                        q.delivery_status = %s
                        AND q.next_retry_at IS NOT NULL
                        AND q.next_retry_at <= NOW()
                    )
            """
            params.append(p.QUEUE_STATUS_RETRY)
        query += """
                  )
                ORDER BY COALESCE(q.next_retry_at, q.created_at) ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE outreachsendqueue q
            SET delivery_status = %s,
                attempts = COALESCE(q.attempts, 0) + 1,
                last_attempt_at = NOW(),
                dispatch_started_at = NOW(),
                idempotency_key = COALESCE(q.idempotency_key, 'outreach:' || q.id::text),
                updated_at = NOW()
            FROM due
            WHERE q.id = due.id
            RETURNING q.id, q.batch_id, q.lead_id, q.draft_id, q.channel, q.delivery_status,
                      q.attempts, q.provider_message_id, q.error_text
        """
        params.extend(
            [
                safe_batch_size,
                p.QUEUE_STATUS_SENDING,
            ]
        )
        cur.execute(
            query,
            params,
        )
        claimed = [dict(row) for row in cur.fetchall()]
        if claimed:
            queue_ids = [str(row.get("id") or "") for row in claimed if str(row.get("id") or "")]
            if queue_ids:
                placeholders = ",".join(["%s"] * len(queue_ids))
                cur.execute(
                    f"""
                    SELECT
                        q.id,
                        q.sender_account_id,
                        q.campaign_touch_id,
                        q.idempotency_key,
                        q.dispatch_started_at,
                        q.scheduled_at,
                        touch.subject,
                        contact.contact_type,
                        contact.normalized_value AS contact_value,
                        l.name AS lead_name,
                        l.phone,
                        COALESCE(contact.normalized_value, l.email) AS email,
                        l.telegram_url,
                        l.whatsapp_url,
                        l.selected_channel,
                        d.approved_text,
                        d.generated_text
                    FROM outreachsendqueue q
                    LEFT JOIN outreachmessagedrafts d ON d.id = q.draft_id
                    LEFT JOIN prospectingleads l ON l.id = q.lead_id
                    LEFT JOIN outreach_campaign_touches touch ON touch.id = q.campaign_touch_id
                    LEFT JOIN lead_contact_points contact ON contact.id = touch.contact_point_id
                    WHERE q.id IN ({placeholders})
                    """,
                    tuple(queue_ids),
                )
                detail_map = {str(row.get("id") or ""): dict(row) for row in cur.fetchall()}
                for row in claimed:
                    row_id = str(row.get("id") or "")
                    details = detail_map.get(row_id) or {}
                    row.update(
                        {
                            "lead_name": details.get("lead_name"),
                            "sender_account_id": details.get("sender_account_id"),
                            "campaign_touch_id": details.get("campaign_touch_id"),
                            "idempotency_key": details.get("idempotency_key"),
                            "dispatch_started_at": details.get("dispatch_started_at"),
                            "scheduled_at": details.get("scheduled_at"),
                            "subject": details.get("subject"),
                            "contact_type": details.get("contact_type"),
                            "contact_value": details.get("contact_value"),
                            "phone": details.get("phone"),
                            "email": details.get("email"),
                            "telegram_url": details.get("telegram_url"),
                            "whatsapp_url": details.get("whatsapp_url"),
                            "selected_channel": details.get("selected_channel"),
                            "approved_text": details.get("approved_text"),
                            "generated_text": details.get("generated_text"),
                        }
                    )
        conn.commit()

        summary = {
            "success": True,
            "batch_id": batch_id,
            "queue_id": queue_id,
            "picked": len(claimed),
            "sent": 0,
            "delivered": 0,
            "retry": 0,
            "dlq": 0,
            "failed": 0,
            "blocked": 0,
            "results": [],
        }
        if not claimed:
            return summary

        for item in claimed:
            queue_id = str(item.get("id") or "")
            lead_id = str(item.get("lead_id") or "")
            attempt_no = int(item.get("attempts") or 1)
            preflight_conn = p.get_db_connection()
            try:
                preflight_cur = preflight_conn.cursor()
                preflight = run_dispatch_preflight(preflight_cur, queue_id)
                persist_preflight_result(preflight_cur, queue_id, preflight)
                if not preflight.get("allowed"):
                    block_queue_item_after_preflight(preflight_cur, queue_id, preflight)
                preflight_conn.commit()
            except Exception:
                preflight_conn.rollback()
                raise
            finally:
                preflight_conn.close()
            if not preflight.get("allowed"):
                summary["blocked"] += 1
                summary["results"].append(
                    {
                        "queue_id": queue_id,
                        "lead_id": lead_id,
                        "channel": item.get("channel"),
                        "attempt_no": attempt_no,
                        "delivery_status": "blocked",
                        "reason_code": preflight.get("reason_code"),
                    }
                )
                continue
            dispatch_result = p._dispatch_outreach_queue_item(item)
            delivery_status = str(dispatch_result.get("delivery_status") or p.QUEUE_STATUS_FAILED).strip().lower()
            provider_message_id = dispatch_result.get("provider_message_id")
            provider_name = dispatch_result.get("provider_name")
            provider_account_id = dispatch_result.get("provider_account_id")
            recipient_kind = dispatch_result.get("recipient_kind")
            recipient_value = dispatch_result.get("recipient_value")
            error_text = str(dispatch_result.get("error_text") or "").strip()[:500] or None
            retryable = bool(dispatch_result.get("retryable", True))

            update_conn = p.get_db_connection()
            try:
                update_cur = update_conn.cursor()
                if delivery_status in {p.QUEUE_STATUS_SENT, p.QUEUE_STATUS_DELIVERED}:
                    update_cur.execute(
                        """
                        UPDATE outreachsendqueue
                        SET delivery_status = %s,
                            provider_message_id = %s,
                            provider_name = %s,
                            provider_account_id = %s,
                            recipient_kind = %s,
                            recipient_value = %s,
                            error_text = NULL,
                            sent_at = COALESCE(sent_at, NOW()),
                            next_retry_at = NULL,
                            dlq_at = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            delivery_status,
                            provider_message_id,
                            provider_name,
                            provider_account_id,
                            recipient_kind,
                            recipient_value,
                            queue_id,
                        ),
                    )
                    update_cur.execute(
                        """
                        UPDATE prospectingleads
                        SET status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        ("sent", lead_id),
                    )
                    if item.get("campaign_touch_id"):
                        update_cur.execute(
                            """
                            UPDATE outreach_campaign_touches
                            SET status = %s,
                                delivery_json = delivery_json || %s,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                "delivered" if delivery_status == p.QUEUE_STATUS_DELIVERED else "sent",
                                p.Json({"provider_name": provider_name, "provider_message_id": provider_message_id}),
                                item["campaign_touch_id"],
                            ),
                        )
                        record_touch_learning_event(
                            update_cur,
                            touch_id=str(item["campaign_touch_id"]),
                            outcome_type="delivered" if delivery_status == p.QUEUE_STATUS_DELIVERED else "sent",
                            payload={
                                "provider_name": provider_name,
                                "provider_message_id": provider_message_id,
                            },
                        )
                        update_cur.execute(
                            """
                            INSERT INTO outreach_campaign_events (
                                id, campaign_id, touch_id, event_type, reason_code,
                                payload_json, created_at
                            )
                            SELECT %s, touch.campaign_id, touch.id,
                                   'dispatch_reply_race', 'provider_returned_after_reply',
                                   jsonb_build_object(
                                       'queue_id', queue.id,
                                       'dispatch_started_at', queue.dispatch_started_at,
                                       'reply_at', campaign.last_reply_at,
                                       'provider_message_id', %s
                                   ), NOW()
                            FROM outreachsendqueue queue
                            JOIN outreach_campaign_touches touch ON touch.id = queue.campaign_touch_id
                            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
                            WHERE queue.id = %s
                              AND campaign.last_reply_at IS NOT NULL
                              AND queue.dispatch_started_at IS NOT NULL
                              AND campaign.last_reply_at >= queue.dispatch_started_at
                            """,
                            (str(p.uuid.uuid4()), provider_message_id, queue_id),
                        )
                        update_cur.execute(
                            """
                            UPDATE outreach_campaigns c
                            SET status = 'completed', updated_at = NOW()
                            WHERE c.id = (
                                SELECT campaign_id FROM outreach_campaign_touches WHERE id = %s
                            )
                              AND c.status IN ('approved', 'active')
                              AND NOT EXISTS (
                                  SELECT 1 FROM outreach_campaign_touches t
                                  WHERE t.campaign_id = c.id
                                    AND t.status IN ('draft', 'approved', 'scheduled', 'queued', 'manual', 'paused')
                              )
                            """,
                            (item["campaign_touch_id"],),
                        )
                        update_cur.execute(
                            """
                            INSERT INTO outreach_campaign_events (
                                id, campaign_id, touch_id, event_type, payload_json, created_at
                            )
                            SELECT %s, campaign_id, id, 'touch_sent', %s, NOW()
                            FROM outreach_campaign_touches WHERE id = %s
                            """,
                            (
                                str(p.uuid.uuid4()),
                                p.Json({"provider_name": provider_name, "provider_message_id": provider_message_id}),
                                item["campaign_touch_id"],
                            ),
                        )
                    if delivery_status == p.QUEUE_STATUS_DELIVERED:
                        summary["delivered"] += 1
                    else:
                        summary["sent"] += 1
                else:
                    retry_delay = p._outreach_retry_delay_for_attempt(attempt_no) if retryable else None
                    exhausted = (attempt_no >= p.OUTREACH_SEND_MAX_ATTEMPTS or retry_delay is None) and retryable
                    if not retryable:
                        next_status = p.QUEUE_STATUS_FAILED
                        next_retry_at = None
                        dlq_at_sql = "NULL"
                    elif exhausted:
                        next_status = p.QUEUE_STATUS_DLQ
                        next_retry_at = None
                        dlq_at_sql = "NOW()"
                        summary["dlq"] += 1
                    else:
                        next_status = p.QUEUE_STATUS_RETRY
                        next_retry_at = p.datetime.now(p.timezone.utc) + retry_delay
                        dlq_at_sql = "NULL"
                        summary["retry"] += 1
                    update_cur.execute(
                        f"""
                        UPDATE outreachsendqueue
                        SET delivery_status = %s,
                            provider_message_id = %s,
                            provider_name = %s,
                            provider_account_id = %s,
                            recipient_kind = %s,
                            recipient_value = %s,
                            error_text = %s,
                            next_retry_at = %s,
                            dlq_at = {dlq_at_sql},
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            next_status,
                            provider_message_id,
                            provider_name,
                            provider_account_id,
                            recipient_kind,
                            recipient_value,
                            error_text,
                            next_retry_at,
                            queue_id,
                        ),
                    )
                    update_cur.execute(
                        """
                        UPDATE prospectingleads
                        SET status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (p.CHANNEL_SELECTED, lead_id),
                    )
                    if item.get("campaign_touch_id"):
                        update_cur.execute(
                            """
                            INSERT INTO outreach_campaign_events (
                                id, campaign_id, touch_id, event_type, reason_code,
                                payload_json, created_at
                            )
                            SELECT %s, campaign_id, id, 'touch_delivery_failed', %s, %s, NOW()
                            FROM outreach_campaign_touches WHERE id = %s
                            """,
                            (
                                str(p.uuid.uuid4()), next_status,
                                p.Json({"error": error_text, "retryable": retryable, "attempt": attempt_no}),
                                item["campaign_touch_id"],
                            ),
                        )
                        if next_status in {p.QUEUE_STATUS_FAILED, p.QUEUE_STATUS_DLQ}:
                            update_cur.execute(
                                "UPDATE outreach_campaign_touches SET status = 'failed', delivery_json = delivery_json || %s, updated_at = NOW() WHERE id = %s",
                                (p.Json({"error": error_text, "queue_status": next_status}), item["campaign_touch_id"]),
                            )
                            record_touch_learning_event(
                                update_cur,
                                touch_id=str(item["campaign_touch_id"]),
                                outcome_type="delivery_failed",
                                payload={
                                    "error": error_text,
                                    "queue_status": next_status,
                                    "provider_name": provider_name,
                                },
                            )
                    if item.get("sender_account_id") and delivery_status not in {
                        p.QUEUE_STATUS_SENT,
                        p.QUEUE_STATUS_DELIVERED,
                    }:
                        error_lower = str(error_text or "").lower()
                        health_event_type = (
                            "auth_invalid" if any(token in error_lower for token in ("auth", "unauthorized", "session revoked"))
                            else "blocked" if any(token in error_lower for token in ("blocked", "banned"))
                            else "flood_wait" if "flood" in error_lower
                            else "rate_limit" if any(token in error_lower for token in ("rate limit", "too many requests", "429"))
                            else "bounce" if any(token in error_lower for token in ("bounce", "mailbox", "address rejected"))
                            else "delivery_failed"
                        )
                        flood_wait_seconds = 0
                        record_sender_health_event(
                            update_cur,
                            sender_account_id=str(item["sender_account_id"]),
                            event_type=health_event_type,
                            provider_code=str(provider_name or ""),
                            touch_id=str(item.get("campaign_touch_id") or "") or None,
                            metrics={"error": error_text, "flood_wait_seconds": flood_wait_seconds},
                        )
                    summary["failed"] += 1
                update_conn.commit()
            except Exception:
                update_conn.rollback()
                raise
            finally:
                update_conn.close()

            summary["results"].append(
                {
                    "queue_id": queue_id,
                    "lead_id": lead_id,
                    "channel": item.get("channel"),
                    "attempt_no": attempt_no,
                    "delivery_status": delivery_status,
                    "provider_message_id": provider_message_id,
                    "provider_name": provider_name,
                    "provider_account_id": provider_account_id,
                    "recipient_kind": recipient_kind,
                    "recipient_value": recipient_value,
                    "error_text": error_text,
                }
            )
            if len(claimed) > 1 and queue_id != str(claimed[-1].get("id") or ""):
                delay_seconds = p.random.uniform(p.OUTREACH_SEND_DELAY_MIN_SEC, p.OUTREACH_SEND_DELAY_MAX_SEC)
                health_status = str((preflight.get("item") or {}).get("health_status") or "healthy")
                if health_status == "degraded":
                    delay_seconds *= 2.0
                elif health_status == "warning":
                    delay_seconds *= 1.5
                if delay_seconds > 0:
                    p.time.sleep(delay_seconds)
        return summary
    finally:
        conn.close()
