#!/usr/bin/env python3
"""Read-only runtime reconciliation for the reviewed 50-lead template cohort."""

from __future__ import annotations

import json
from collections import Counter

from database_manager import get_db_connection


SOURCE = "/app/debug_data/localos-template-review-v12-20260811.json"


def main() -> None:
    source = json.load(open(SOURCE, encoding="utf-8"))
    workstream_ids = [str(item["workstream_id"]) for item in source["results"]]
    lead_ids = [str(item["lead_id"]) for item in source["results"]]
    expected_by_workstream = {
        str(item["workstream_id"]): {
            "name": item["name"],
            "first_channel": item["touches"][0]["channel"],
            "expected_touches": len(item["touches"]),
        }
        for item in source["results"]
    }
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(
            """
            SELECT DISTINCT ON (c.workstream_id)
                   c.id,c.workstream_id,c.lead_id,c.version,c.status,c.updated_at,
                   c.stop_reason,c.needs_attention_reason
            FROM outreach_campaigns c
            WHERE c.workstream_id=ANY(%s::uuid[])
            ORDER BY c.workstream_id,c.version DESC,c.created_at DESC
            """,
            (workstream_ids,),
        )
        latest = [dict(row) for row in cursor.fetchall()]
        latest_by_workstream = {str(row["workstream_id"]): row for row in latest}
        campaign_ids = [str(row["id"]) for row in latest]
        cursor.execute(
            """
            SELECT campaign_id,channel,status,COUNT(*) AS count
            FROM outreach_campaign_touches
            WHERE campaign_id=ANY(%s::uuid[])
            GROUP BY campaign_id,channel,status
            ORDER BY campaign_id,channel,status
            """,
            (campaign_ids,),
        )
        touch_rows = [dict(row) for row in cursor.fetchall()]
        touch_by_campaign: dict[str, list[dict]] = {}
        for row in touch_rows:
            touch_by_campaign.setdefault(str(row["campaign_id"]), []).append(row)
        cursor.execute(
            """
            SELECT t.campaign_id,q.delivery_status,COUNT(*) AS count,
                   COUNT(sent_at) AS sent,COUNT(provider_message_id) AS provider
            FROM outreachsendqueue q
            JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
            WHERE q.lead_id=ANY(%s)
            GROUP BY t.campaign_id,q.delivery_status
            """,
            (lead_ids,),
        )
        queue_rows = [dict(row) for row in cursor.fetchall()]
        queue_by_campaign: dict[str, list[dict]] = {}
        for row in queue_rows:
            queue_by_campaign.setdefault(str(row["campaign_id"]), []).append(row)
        cursor.execute(
            """
            SELECT l.id AS lead_id,
              (SELECT COUNT(*) FROM outreach_suppressions s
               WHERE s.lead_id=l.id AND (s.expires_at IS NULL OR s.expires_at>NOW())) AS suppressions,
              (SELECT COUNT(*) FROM outreach_inbound_events i
               WHERE i.lead_id=l.id AND COALESCE(i.is_human,FALSE)=TRUE) AS inbound,
              (SELECT COUNT(*) FROM outreachreactions r WHERE r.lead_id=l.id) AS reactions
            FROM prospectingleads l WHERE l.id=ANY(%s)
            """,
            (lead_ids,),
        )
        safety_by_lead = {str(row["lead_id"]): dict(row) for row in cursor.fetchall()}
        connection.rollback()
    finally:
        connection.close()

    records = []
    for workstream_id, expected in expected_by_workstream.items():
        campaign = latest_by_workstream.get(workstream_id)
        records.append(
            {
                **expected,
                "workstream_id": workstream_id,
                "campaign_id": str(campaign["id"]) if campaign else None,
                "campaign_version": campaign.get("version") if campaign else None,
                "campaign_status": campaign.get("status") if campaign else "missing",
                "stop_reason": campaign.get("stop_reason") if campaign else None,
                "needs_attention_reason": campaign.get("needs_attention_reason") if campaign else None,
                "touches": touch_by_campaign.get(str(campaign["id"]), []) if campaign else [],
                "queues": queue_by_campaign.get(str(campaign["id"]), []) if campaign else [],
                "safety": safety_by_lead.get(str(campaign["lead_id"]), {}) if campaign else {},
            }
        )
    print(
        json.dumps(
            {
                "reviewed": len(source["results"]),
                "reviewed_touches": sum(len(item["touches"]) for item in source["results"]),
                "first_channels": Counter(item["first_channel"] for item in records),
                "latest_campaign_statuses": Counter(item["campaign_status"] for item in records),
                "campaigns_present": sum(bool(item["campaign_id"]) for item in records),
                "safety_blocked": [
                    item["name"]
                    for item in records
                    if any(int(item["safety"].get(key) or 0) for key in ("suppressions", "inbound", "reactions"))
                ],
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
