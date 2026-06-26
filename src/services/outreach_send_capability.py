import uuid
from typing import Any

from database_manager import get_db_connection


OUTREACH_SEND_BATCH_CAPABILITY = "outreach.send_batch"
MAX_DAILY_OUTREACH_BATCH = 10
DRAFT_APPROVED = "approved"
BATCH_APPROVED = "approved"
QUEUE_STATUS_QUEUED = "queued"
QUEUED_FOR_SEND = "queued_for_send"
PIPELINE_IN_PROGRESS = "in_progress"


def _normalize_draft_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        candidate = str(item or "").strip()
        if candidate:
            normalized.append(candidate)
    return normalized


def _normalize_daily_limit(value: Any) -> int:
    try:
        limit = int(value or MAX_DAILY_OUTREACH_BATCH)
    except Exception:
        limit = MAX_DAILY_OUTREACH_BATCH
    return max(1, min(limit, MAX_DAILY_OUTREACH_BATCH))


def _normalize_outreach_intent(value: Any) -> str:
    intent = str(value or "client_outreach").strip().lower()
    return intent if intent in {"client_outreach", "partnership_outreach"} else "client_outreach"


def _has_channel_contact(row: dict[str, Any]) -> bool:
    channel = str(row.get("channel") or "").strip().lower()
    if channel == "manual":
        return True
    if channel == "telegram":
        return bool(str(row.get("telegram_url") or "").strip())
    if channel == "whatsapp":
        return bool(str(row.get("whatsapp_url") or "").strip())
    if channel == "email":
        return bool(str(row.get("email") or "").strip())
    return False


def _remaining_daily_slots(cur) -> int:
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM outreachsendqueue q
        JOIN outreachsendbatches b ON b.id = q.batch_id
        WHERE b.batch_date = CURRENT_DATE
        """
    )
    row = cur.fetchone() or {}
    return max(0, MAX_DAILY_OUTREACH_BATCH - int(row.get("cnt") or 0))


def handle_outreach_send_batch(envelope: dict[str, Any], user_data: dict[str, Any]) -> dict[str, Any]:
    """Queue an approved outreach batch; external dispatch stays outside blueprint runtime."""
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    business_id = str(envelope.get("tenant_id") or payload.get("business_id") or "").strip()
    if not business_id:
        return {
            "result": {
                "status": "blocked",
                "reason_code": "BUSINESS_REQUIRED",
                "external_dispatch_performed": False,
            }
        }

    draft_ids = _normalize_draft_ids(payload.get("draft_ids"))
    requested_limit = _normalize_daily_limit(payload.get("daily_limit"))
    intent = _normalize_outreach_intent(payload.get("intent"))
    actor_user_id = str(user_data.get("user_id") or user_data.get("id") or envelope.get("actor", {}).get("user_id") or "")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        remaining_slots = min(_remaining_daily_slots(cur), requested_limit)
        if remaining_slots <= 0:
            return {
                "result": {
                    "status": "blocked",
                    "reason_code": "DAILY_CAP_REACHED",
                    "daily_limit": MAX_DAILY_OUTREACH_BATCH,
                    "external_dispatch_performed": False,
                }
            }

        query = """
            SELECT
                d.id,
                d.lead_id,
                d.channel,
                l.telegram_url,
                l.whatsapp_url,
                l.email
            FROM outreachmessagedrafts d
            JOIN prospectingleads l ON l.id = d.lead_id
            WHERE d.status = %s
              AND l.business_id = %s
              AND COALESCE(l.intent, 'client_outreach') = %s
              AND NOT EXISTS (
                    SELECT 1
                    FROM outreachsendqueue q
                    WHERE q.draft_id = d.id
              )
        """
        params: list[Any] = [DRAFT_APPROVED, business_id, intent]
        if draft_ids:
            query += " AND d.id = ANY(%s)"
            params.append(draft_ids)
        query += " ORDER BY d.updated_at DESC, d.created_at DESC LIMIT %s"
        params.append(remaining_slots)
        cur.execute(query, tuple(params))
        selected_rows = [dict(row) for row in cur.fetchall()]
        valid_rows = [row for row in selected_rows if _has_channel_contact(row)]

        if not valid_rows:
            return {
                "result": {
                    "status": "blocked",
                    "reason_code": "NO_APPROVED_DRAFTS",
                    "requested_draft_ids": draft_ids,
                    "intent": intent,
                    "external_dispatch_performed": False,
                }
            }

        batch_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO outreachsendbatches (
                id, batch_date, daily_limit, status, created_by, approved_by
            ) VALUES (
                %s, CURRENT_DATE, %s, %s, %s, %s
            )
            """,
            (batch_id, MAX_DAILY_OUTREACH_BATCH, BATCH_APPROVED, actor_user_id, actor_user_id),
        )
        queued_draft_ids = []
        for row in valid_rows:
            queued_draft_ids.append(str(row.get("id") or ""))
            cur.execute(
                """
                INSERT INTO outreachsendqueue (
                    id, batch_id, lead_id, draft_id, channel, delivery_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    str(uuid.uuid4()),
                    batch_id,
                    row.get("lead_id"),
                    row.get("id"),
                    row.get("channel"),
                    QUEUE_STATUS_QUEUED,
                ),
            )
            cur.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    pipeline_status = %s,
                    partnership_stage = CASE
                        WHEN COALESCE(intent, 'client_outreach') = 'partnership_outreach' THEN %s
                        ELSE partnership_stage
                    END,
                    updated_at = NOW()
                WHERE id = %s
                  AND business_id = %s
                """,
                (QUEUED_FOR_SEND, PIPELINE_IN_PROGRESS, QUEUED_FOR_SEND, row.get("lead_id"), business_id),
            )

        conn.commit()
        return {
            "result": {
                "status": "queued_for_dispatch",
                "dispatch_state": "queued_not_dispatched",
                "batch_id": batch_id,
                "queue_count": len(valid_rows),
                "draft_ids": queued_draft_ids,
                "intent": intent,
                "daily_limit": MAX_DAILY_OUTREACH_BATCH,
                "requested_limit": requested_limit,
                "external_dispatch_performed": False,
                "dispatcher_required": True,
                "operator_note": "Queued in LocalOS only. External dispatcher did not run inside Agent Blueprint runtime.",
                "next_step": "dispatch_due_outreach_queue",
            }
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
