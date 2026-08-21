#!/usr/bin/env python3
"""Prove both prepared batches remain unapproved, unqueued, and unsent."""

import json

from psycopg2.extras import RealDictCursor

from database_manager import get_db_connection


BATCHES = ("followup-batch-01-20260820", "followup-batch-02-20260820")


def main():
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT quality_gate_json->>'batch_id' batch_id,
                   COUNT(*) total,
                   COUNT(*) FILTER (WHERE status='draft') drafts,
                   COUNT(*) FILTER (WHERE approved_text IS NOT NULL) approved,
                   COUNT(*) FILTER (WHERE status IN ('approved','queued','sending','sent','delivered','manual_sent')) unsafe_status,
                   COUNT(*) FILTER (WHERE COALESCE((delivery_json->>'queued')::boolean,FALSE)) delivery_queued,
                   COUNT(*) FILTER (WHERE COALESCE((delivery_json->>'sent')::boolean,FALSE)) delivery_sent,
                   MIN(scheduled_at) min_scheduled_at,
                   MAX(scheduled_at) max_scheduled_at
            FROM outreach_campaign_touches
            WHERE quality_gate_json->>'batch_id' IN %s
            GROUP BY quality_gate_json->>'batch_id'
            ORDER BY batch_id
            """,
            (BATCHES,),
        )
        batches = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT COUNT(*) count
            FROM outreachsendqueue q
            JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
            WHERE t.quality_gate_json->>'batch_id' IN %s
            """,
            (BATCHES,),
        )
        queue_rows = int((cursor.fetchone() or {}).get("count") or 0)
        cursor.execute(
            """
            SELECT COUNT(*) count
            FROM outreach_campaign_events e
            JOIN outreach_campaign_touches t ON t.id=e.touch_id
            WHERE t.quality_gate_json->>'batch_id' IN %s
              AND e.event_type IN ('queued','send_started','sent','delivered','manual_sent')
            """,
            (BATCHES,),
        )
        send_events = int((cursor.fetchone() or {}).get("count") or 0)
        if len(batches) != 2 or any(int(row["total"]) != 20 or int(row["drafts"]) != 20 for row in batches):
            raise RuntimeError("batch_draft_count_failed")
        if queue_rows or send_events or any(
            int(row[key]) for row in batches for key in ("approved", "unsafe_status", "delivery_queued", "delivery_sent")
        ):
            raise RuntimeError("batch_safety_invariant_failed")
        print(json.dumps({"batches": batches, "total_drafts": 40, "queue_rows": queue_rows, "send_events": send_events}, ensure_ascii=False, default=str))
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
