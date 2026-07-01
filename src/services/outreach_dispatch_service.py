"""Outreach send-queue dispatch runtime.

The public compatibility entrypoint still lives in ``api.admin_prospecting``.
This module owns the dispatcher body so worker/runtime code can move away from
the large admin route module without changing behavior.
"""
from __future__ import annotations

from typing import Any


def dispatch_due_outreach_queue(batch_size: int = 20, batch_id: str | None = None, force_ready: bool = False) -> dict[str, Any]:
    """Dispatch queued/retry outreach items to the configured outbound provider."""
    from api import admin_prospecting as p

    safe_batch_size = max(1, min(int(batch_size or 20), 200))
    conn = p.get_db_connection()
    try:
        cur = conn.cursor()
        query = """
            WITH due AS (
                SELECT
                    q.id
                FROM outreachsendqueue q
                JOIN outreachsendbatches b ON b.id = q.batch_id
                WHERE b.status = %s
        """
        params: list[Any] = [p.BATCH_APPROVED]
        if batch_id:
            query += " AND q.batch_id = %s"
            params.append(batch_id)
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
                        l.name AS lead_name,
                        l.phone,
                        l.email,
                        l.telegram_url,
                        l.whatsapp_url,
                        l.selected_channel,
                        d.approved_text,
                        d.generated_text
                    FROM outreachsendqueue q
                    LEFT JOIN outreachmessagedrafts d ON d.id = q.draft_id
                    LEFT JOIN prospectingleads l ON l.id = q.lead_id
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
            "picked": len(claimed),
            "sent": 0,
            "delivered": 0,
            "retry": 0,
            "dlq": 0,
            "failed": 0,
            "results": [],
        }
        if not claimed:
            return summary

        for item in claimed:
            queue_id = str(item.get("id") or "")
            lead_id = str(item.get("lead_id") or "")
            attempt_no = int(item.get("attempts") or 1)
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
                if delay_seconds > 0:
                    p.time.sleep(delay_seconds)
        return summary
    finally:
        conn.close()
