#!/usr/bin/env python3
"""Import frozen batch 01 as unapproved PostgreSQL drafts without queueing or sending."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from psycopg2.extras import Json, RealDictCursor

from database_manager import get_db_connection


FINAL_PATH = Path("/app/debug_data/localos-followup-batch-01-final-20260820.json")
EXPECTED_SHA = "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386"
SCHEDULED_AT = datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc)


def main():
    payload = json.loads(FINAL_PATH.read_text(encoding="utf-8"))
    if payload.get("base_manifest_canonical_sha256") != EXPECTED_SHA:
        raise RuntimeError("manifest_sha_mismatch")
    if payload.get("state") != "draft_for_user_approval" or payload.get("delivery_authorized"):
        raise RuntimeError("final_batch_state_invalid")
    items = payload.get("items") or []
    if len(items) != 20:
        raise RuntimeError("final_batch_size_invalid")

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    imported = []
    try:
        for item in items:
            cursor.execute(
                """
                SELECT t.*, c.lead_id, c.workstream_id
                FROM outreach_campaign_touches t
                JOIN outreach_campaigns c ON c.id=t.campaign_id
                WHERE t.id=%s AND t.campaign_id=%s AND c.lead_id=%s
                FOR UPDATE
                """,
                (item.get("first_touch_id"), item.get("campaign_id"), item.get("lead_id")),
            )
            first = dict(cursor.fetchone() or {})
            if not first or first.get("status") not in {"sent", "manual_sent", "delivered"}:
                raise RuntimeError(f"first_touch_not_sent:{item.get('name')}")
            cursor.execute(
                "SELECT id,status FROM outreach_campaign_touches WHERE campaign_id=%s AND sequence_index=1",
                (item.get("campaign_id"),),
            )
            existing = cursor.fetchone()
            if existing and existing["status"] != "cancelled":
                raise RuntimeError(f"second_touch_already_exists:{item.get('name')}:{existing['id']}:{existing['status']}")
            draft = item.get("draft") or {}
            touch_id = str(existing["id"]) if existing else item.get("proposed_touch_id")
            quality = {
                **(item.get("quality") or {}),
                "approval_status": "pending_user_approval",
                "delivery_authorized": False,
                "batch_id": payload.get("batch_id"),
            }
            brief = {
                "observation": draft.get("observation"),
                "problem_hypothesis": draft.get("problem_hypothesis"),
                "solution": draft.get("offer_bridge"),
                "cta": draft.get("cta"),
                "source_url": (item.get("evidence", {}).get("research") or {}).get("price_source_url")
                or (item.get("evidence", {}).get("research") or {}).get("source_url"),
                "contact_source_url": item.get("contact_source_url"),
                "researched_at": (item.get("evidence", {}).get("research") or {}).get("researched_at"),
                "generation_source": "supervised_v4_followup_batch",
                "first_touch_id": item.get("first_touch_id"),
            }
            strategy = {
                "source": "current_public_fact",
                "batch_id": payload.get("batch_id"),
                "base_manifest_sha256": EXPECTED_SHA,
                "first_touch_id": item.get("first_touch_id"),
                "angle": draft.get("angle"),
                "planned_send_date": payload.get("planned_send_date"),
                "approval_status": "pending_user_approval",
            }
            fingerprint = hashlib.sha256(json.dumps(strategy, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            if existing:
                cursor.execute(
                    """
                    UPDATE outreach_campaign_touches
                    SET channel='email',contact_point_id=%s,sender_account_id=%s,angle_type=%s,
                        scheduled_at=%s,status='draft',subject=%s,generated_text=%s,approved_text=NULL,
                        message_brief_json=%s,quality_gate_json=%s,delivery_json=%s,updated_at=NOW(),
                        strategy_fingerprint=%s,strategy_json=%s,manual_due_at=%s,
                        preflight_at=NULL,preflight_reason=NULL
                    WHERE id=%s AND status='cancelled'
                    """,
                    (
                        first.get("contact_point_id"), first.get("sender_account_id"), draft.get("angle"),
                        SCHEDULED_AT, draft.get("subject"), draft.get("text"), Json(brief), Json(quality),
                        Json({"queued": False, "sent": False, "delivery_authorized": False}),
                        fingerprint, Json(strategy), SCHEDULED_AT, touch_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"cancelled_touch_reuse_failed:{item.get('name')}")
            else:
                cursor.execute(
                    """
                    INSERT INTO outreach_campaign_touches(
                        id,campaign_id,draft_id,sequence_index,channel,contact_point_id,sender_account_id,
                        angle_type,scheduled_at,status,subject,generated_text,approved_text,
                        message_brief_json,quality_gate_json,delivery_json,created_at,updated_at,
                        strategy_fingerprint,strategy_json,manual_due_at,preflight_at,preflight_reason
                    ) VALUES(
                        %s,%s,%s,1,'email',%s,%s,%s,%s,'draft',%s,%s,NULL,
                        %s,%s,%s,NOW(),NOW(),%s,%s,%s,NULL,NULL
                    )
                    """,
                    (
                        touch_id, item.get("campaign_id"), None, first.get("contact_point_id"),
                        first.get("sender_account_id"), draft.get("angle"), SCHEDULED_AT,
                        draft.get("subject"), draft.get("text"), Json(brief), Json(quality),
                        Json({"queued": False, "sent": False, "delivery_authorized": False}),
                        fingerprint, Json(strategy), SCHEDULED_AT,
                    ),
                )
            cursor.execute(
                "UPDATE outreach_campaigns SET status='draft',updated_at=NOW() WHERE id=%s",
                (item.get("campaign_id"),),
            )
            cursor.execute(
                """
                INSERT INTO outreach_campaign_events(id,campaign_id,touch_id,event_type,payload_json,created_at)
                VALUES(%s,%s,%s,'draft_generated',%s,NOW())
                """,
                (
                    str(uuid.uuid4()),
                    item.get("campaign_id"),
                    touch_id,
                    Json(
                        {
                            "source": "supervised_v4_followup_batch",
                            "batch_id": payload.get("batch_id"),
                            "approval_status": "pending_user_approval",
                            "delivery_authorized": False,
                        }
                    ),
                ),
            )
            imported.append({"name": item.get("name"), "touch_id": touch_id})
        cursor.execute(
            "SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id IN %s",
            (tuple(item["touch_id"] for item in imported),),
        )
        if int((cursor.fetchone() or {}).get("count") or 0) != 0:
            raise RuntimeError("queue_record_created_unexpectedly")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    print(json.dumps({"imported_drafts": len(imported), "queued": 0, "sent": 0, "scheduled_at": SCHEDULED_AT.isoformat(), "items": imported}, ensure_ascii=False))


if __name__ == "__main__":
    main()
