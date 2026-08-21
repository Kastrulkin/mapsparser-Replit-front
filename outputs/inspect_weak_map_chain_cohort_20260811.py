#!/usr/bin/env python3
"""Read-only production inventory for the weak-map outreach cohort."""

from __future__ import annotations

import json
import os

import psycopg2
from psycopg2.extras import RealDictCursor


LEAD_IDS = [
    "9aa271b1-ca9b-4f41-a13f-c11bf6c14d9e",
    "cd8592be-ceb5-4830-a105-80b894d54273",
    "492caf0b-f633-4fbb-ab05-f1943c61d0f7",
    "1658f6ce-c613-46e6-8384-bbe444261f10",
    "5095efec-bcf9-4e82-a821-4f2d843d1b85",
    "cfb84d6c-bfd4-49dc-8521-0183cb471575",
    "26bc3e2d-9c66-4d66-a690-6ff1afe0a1ba",
    "1e8aea4f-b94e-4307-9895-14df8719f7c2",
    "e21da65b-6553-4646-add4-00d28c3dd7c5",
    "510f8e0c-8f2f-485b-ba9a-4924918d2b36",
    "359271c0-b6ea-4f8a-9b87-95cab5486a05",
    "ac14050a-6072-4426-ab66-afaf8bc97081",
    "7999e5da-11e7-4d8d-8f51-050508e924b9",
]


def rows(cursor, sql: str, params=()):
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def main() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    conn.set_session(readonly=True, autocommit=False)
    try:
        cur = conn.cursor()
        leads = rows(cur, "SELECT * FROM prospectingleads WHERE id=ANY(%s) ORDER BY name", (LEAD_IDS,))
        workstreams = rows(cur, "SELECT * FROM lead_workstreams WHERE lead_id=ANY(%s) AND workstream_type='localos_sales' ORDER BY lead_id, updated_at", (LEAD_IDS,))
        workstream_ids = [str(row["id"]) for row in workstreams]
        contacts = rows(cur, "SELECT * FROM lead_contact_points WHERE lead_id=ANY(%s) ORDER BY lead_id, contact_type, verification_status, confidence DESC", (LEAD_IDS,))
        campaigns = rows(cur, "SELECT * FROM outreach_campaigns WHERE workstream_id=ANY(%s::uuid[]) ORDER BY workstream_id, version", (workstream_ids,))
        campaign_ids = [str(row["id"]) for row in campaigns]
        touches = rows(cur, "SELECT * FROM outreach_campaign_touches WHERE campaign_id=ANY(%s::uuid[]) ORDER BY campaign_id, sequence_index", (campaign_ids,)) if campaign_ids else []
        touch_ids = [str(row["id"]) for row in touches]
        queue = rows(cur, "SELECT * FROM outreachsendqueue WHERE campaign_touch_id=ANY(%s::uuid[]) ORDER BY id", (touch_ids,)) if touch_ids else []
        research = rows(cur, "SELECT DISTINCT ON (workstream_id) * FROM lead_workstream_research WHERE workstream_id=ANY(%s::uuid[]) ORDER BY workstream_id, researched_at DESC NULLS LAST", (workstream_ids,))
        safety = rows(cur, """
            SELECT l.id AS lead_id,
              (SELECT count(*) FROM outreach_suppressions s WHERE s.lead_id=l.id AND (s.expires_at IS NULL OR s.expires_at>NOW())) AS suppressions,
              (SELECT count(*) FROM outreach_inbound_events i WHERE i.lead_id=l.id AND i.is_human=TRUE) AS human_inbound,
              (SELECT count(*) FROM outreachsendqueue q JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id JOIN outreach_campaigns c ON c.id=t.campaign_id WHERE c.lead_id=l.id) AS queue_count,
              (SELECT count(*) FROM outreachsendqueue q JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id JOIN outreach_campaigns c ON c.id=t.campaign_id WHERE c.lead_id=l.id AND q.sent_at IS NOT NULL) AS sent_count
            FROM prospectingleads l WHERE l.id=ANY(%s)
        """, (LEAD_IDS,))
        print(json.dumps({
            "leads": leads,
            "workstreams": workstreams,
            "research": research,
            "contacts": contacts,
            "campaigns": campaigns,
            "touches": touches,
            "queue": queue,
            "safety": safety,
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
