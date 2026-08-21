#!/usr/bin/env python3
import json
import os

import psycopg2
from psycopg2.extras import RealDictCursor


LEADS = (
    "4eaa0e32-ef50-4dc8-888f-febf561ab17e",
    "d14a0e2b-cc99-41b1-9d89-fee61160b46f",
)


def main() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    conn.set_session(readonly=True, autocommit=False)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT l.id AS lead_id, l.name, l.status, l.pipeline_status,
                   l.rating, l.reviews_count, l.last_contact_at,
                   ws.id AS workstream_id, ws.status AS workstream_status,
                   ws.lifecycle_status,
                   cp.id AS contact_id, cp.contact_type, cp.value AS contact_value,
                   cp.verification_status, cp.source_url, cp.source_type,
                   cp.observed_at, cp.verified_at, cp.stale_after
            FROM prospectingleads l
            JOIN lead_workstreams ws ON ws.lead_id=l.id AND ws.workstream_type='localos_sales'
            LEFT JOIN lead_contact_points cp ON cp.lead_id=l.id
            WHERE l.id = ANY(%s)
            ORDER BY l.name, cp.contact_type, cp.confidence DESC NULLS LAST
            """,
            (list(LEADS),),
        )
        rows = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT c.lead_id, c.id AS campaign_id, c.version, c.status,
                   c.stop_reason, c.updated_at,
                   COUNT(DISTINCT t.id) AS touch_count,
                   COUNT(DISTINCT q.id) AS queue_count
            FROM outreach_campaigns c
            LEFT JOIN outreach_campaign_touches t ON t.campaign_id=c.id
            LEFT JOIN outreachsendqueue q ON q.campaign_touch_id=t.id
            WHERE c.lead_id = ANY(%s)
            GROUP BY c.lead_id, c.id
            ORDER BY c.lead_id, c.version DESC
            """,
            (list(LEADS),),
        )
        campaigns = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT l.id AS lead_id,
                   (SELECT COUNT(*) FROM outreach_suppressions s
                    WHERE s.lead_id=l.id AND (s.expires_at IS NULL OR s.expires_at > NOW())) AS suppressions,
                   (SELECT COUNT(*) FROM outreach_inbound_events i
                    WHERE i.lead_id=l.id AND i.is_human=TRUE) AS inbound
            FROM prospectingleads l
            WHERE l.id = ANY(%s)
            """,
            (list(LEADS),),
        )
        safety = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM prospectingleads WHERE id=ANY(%s) ORDER BY id", (list(LEADS),))
        lead_rows = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM lead_workstreams WHERE lead_id=ANY(%s) ORDER BY id", (list(LEADS),))
        workstream_rows = [dict(row) for row in cur.fetchall()]
        workstream_ids = [row["id"] for row in workstream_rows]
        cur.execute("SELECT * FROM lead_workstream_research WHERE workstream_id=ANY(%s::uuid[]) ORDER BY workstream_id, researched_at", (workstream_ids,))
        research_rows = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM lead_contact_points WHERE lead_id=ANY(%s) ORDER BY lead_id, id", (list(LEADS),))
        contact_rows = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT * FROM outreach_campaigns WHERE lead_id=ANY(%s) ORDER BY lead_id, version", (list(LEADS),))
        campaign_rows = [dict(row) for row in cur.fetchall()]
        campaign_ids = [row["id"] for row in campaign_rows]
        cur.execute("SELECT * FROM outreach_campaign_touches WHERE campaign_id=ANY(%s::uuid[]) ORDER BY campaign_id, sequence_index", (campaign_ids,))
        touch_rows = [dict(row) for row in cur.fetchall()]
        touch_ids = [row["id"] for row in touch_rows]
        cur.execute("SELECT * FROM outreachsendqueue WHERE campaign_touch_id=ANY(%s::uuid[]) ORDER BY id", (touch_ids,))
        queue_rows = [dict(row) for row in cur.fetchall()]
        print(json.dumps({
            "summary_rows": rows, "campaign_summary": campaigns, "safety": safety,
            "prospectingleads": lead_rows, "lead_workstreams": workstream_rows,
            "lead_workstream_research": research_rows, "lead_contact_points": contact_rows,
            "outreach_campaigns": campaign_rows, "outreach_campaign_touches": touch_rows,
            "outreachsendqueue": queue_rows,
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
