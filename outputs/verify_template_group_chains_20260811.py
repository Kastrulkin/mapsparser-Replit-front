"""Read-only verification for the 50 persisted template chains."""

import hashlib
import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor


SOURCE = Path("/app/debug_data/localos-template-review-v12-20260811.json")
OUTPUT = Path("/app/debug_data/template-group-final-chain-check-v12-20260811.json")


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    expected = {
        str(item["workstream_id"]): item
        for item in source["results"]
        if item["classification"] == "content_ready"
    }
    connection = psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
    )
    connection.set_session(readonly=True, autocommit=False)
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION READ ONLY")
    cursor.execute(
        """
        SELECT DISTINCT ON (c.workstream_id)
            c.id,c.workstream_id,c.lead_id,c.version,c.status,
            w.status workstream_status,w.lifecycle_status,
            l.pipeline_status
        FROM outreach_campaigns c
        JOIN lead_workstreams w ON w.id=c.workstream_id
        JOIN prospectingleads l ON l.id=c.lead_id
        WHERE c.workstream_id=ANY(%s::uuid[])
        ORDER BY c.workstream_id,c.version DESC,c.created_at DESC
        """,
        (list(expected),),
    )
    latest = [dict(row) for row in cursor.fetchall()]
    campaign_ids = [str(row["id"]) for row in latest]
    cursor.execute(
        """SELECT * FROM outreach_campaign_touches
           WHERE campaign_id=ANY(%s::uuid[])
           ORDER BY campaign_id,sequence_index""",
        (campaign_ids,),
    )
    touches = [dict(row) for row in cursor.fetchall()]
    touches_by_campaign = {}
    for touch in touches:
        touches_by_campaign.setdefault(str(touch["campaign_id"]), []).append(touch)
    cursor.execute(
        """SELECT workstream_id,COUNT(*) FILTER (WHERE status='draft') draft_count
           FROM outreach_campaigns WHERE workstream_id=ANY(%s::uuid[])
           GROUP BY workstream_id""",
        (list(expected),),
    )
    draft_counts = {str(row["workstream_id"]): int(row["draft_count"]) for row in cursor.fetchall()}
    cursor.execute(
        """SELECT COUNT(*) count FROM outreachsendqueue q
           JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
           WHERE t.campaign_id=ANY(%s::uuid[])""",
        (campaign_ids,),
    )
    queue_count = int(cursor.fetchone()["count"])
    connection.rollback()
    connection.close()

    failures = []
    total_touches = 0
    for campaign in latest:
        workstream_id = str(campaign["workstream_id"])
        item = expected.get(workstream_id)
        if not item:
            failures.append({"workstream_id": workstream_id, "problem": "unexpected_campaign"})
            continue
        actual = touches_by_campaign.get(str(campaign["id"]), [])
        total_touches += len(actual)
        actual_bytes = [
            (row.get("channel"), row.get("subject"), row.get("generated_text"))
            for row in actual
        ]
        expected_bytes = [
            (row.get("channel"), row.get("subject"), row.get("text"))
            for row in item.get("touches") or []
        ]
        problems = []
        if campaign.get("status") != "draft":
            problems.append("latest_not_draft")
        if draft_counts.get(workstream_id) != 1:
            problems.append("draft_count_not_one")
        if actual_bytes != expected_bytes:
            problems.append("touch_bytes_mismatch")
        if not all(bool((row.get("quality_gate_json") or {}).get("passed")) for row in actual):
            problems.append("quality_gate_failed")
        if campaign.get("workstream_status") != item.get("workstream_status"):
            problems.append("workstream_status_changed")
        if campaign.get("lifecycle_status") != item.get("lifecycle_status"):
            problems.append("lifecycle_status_changed")
        if campaign.get("pipeline_status") != item.get("pipeline_status"):
            problems.append("pipeline_status_changed")
        if problems:
            failures.append({"name": item.get("name"), "problems": problems})
    if len(latest) != 50:
        failures.append({"problem": f"latest_campaign_count_{len(latest)}"})
    if total_touches != 85:
        failures.append({"problem": f"touch_count_{total_touches}"})
    if queue_count != 0:
        failures.append({"problem": f"queue_count_{queue_count}"})

    result = {
        "status": "PASS" if not failures else "FAIL",
        "chains": len(latest),
        "touches": total_touches,
        "draft_campaigns": sum(row.get("status") == "draft" for row in latest),
        "quality_passed": sum(
            bool((touch.get("quality_gate_json") or {}).get("passed")) for touch in touches
        ),
        "queue_count": queue_count,
        "approved": 0,
        "sent": 0,
        "failures": failures,
    }
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
    result["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
