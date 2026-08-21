#!/usr/bin/env python3
"""Move three too-fresh batch-two drafts out of the August 21 cohort."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from psycopg2.extras import Json, RealDictCursor

from database_manager import get_db_connection


PATH = Path("/app/debug_data/localos-followup-batch-02-final-20260820.json")
BLOCKED = {
    "Ли́ца": ("2026-08-20T12:05:51+00:00", "c8fd8dbc-8193-4920-b83f-1ff725a51ab4"),
    "Милано": ("2026-08-20T12:09:02+00:00", "b9bfea0f-fd4f-4b82-b63d-5f5a85a1d611"),
    "Петергоф-Мед": ("2026-08-20T12:12:19+00:00", "c6c00dfc-f38b-4f68-8b79-bdef26fe855a"),
}
DEFERRED = datetime(2026, 8, 24, 7, 0, tzinfo=timezone.utc)


def main():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        by_name = {item["name"]: item for item in payload.get("items") or []}
        for name, (sent_at, touch_id) in BLOCKED.items():
            item = by_name[name]
            if item.get("actual_touch_id") != touch_id:
                raise RuntimeError(f"touch_id_mismatch:{name}")
            cursor.execute("SELECT quality_gate_json,strategy_json FROM outreach_campaign_touches WHERE id=%s AND status='draft' FOR UPDATE", (touch_id,))
            row = dict(cursor.fetchone() or {})
            if not row:
                raise RuntimeError(f"draft_missing:{name}")
            quality = dict(row.get("quality_gate_json") or {})
            quality.update({
                "approval_status": "blocked_cooldown", "verdict": "reject",
                "reason_codes": ["gmail_followup_interval_under_72h"],
                "first_sent_at": sent_at, "earliest_business_send_at": DEFERRED.isoformat(),
                "delivery_authorized": False,
            })
            strategy = dict(row.get("strategy_json") or {})
            strategy.update({"planned_send_date": "2026-08-24", "approval_status": "blocked_cooldown"})
            cursor.execute(
                """
                UPDATE outreach_campaign_touches
                SET scheduled_at=%s,manual_due_at=%s,quality_gate_json=%s,strategy_json=%s,
                    delivery_json=%s,updated_at=NOW()
                WHERE id=%s AND status='draft'
                """,
                (DEFERRED, DEFERRED, Json(quality), Json(strategy), Json({"queued": False, "sent": False, "delivery_authorized": False}), touch_id),
            )
            item["planned_send_date"] = "2026-08-24"
            item["status"] = "blocked_cooldown"
            item["reasons"] = ["gmail_followup_interval_under_72h"]
            item["approval"] = {"content_status": "blocked_cooldown", "delivery_authorized": False}
            item["quality"].update({"verdict": "reject", "reason_codes": item["reasons"], "first_sent_at": sent_at})
        payload["ready_count"] = 17
        payload["blocked_count"] = 3
        payload["planned_send_date"] = "mixed: 17 on 2026-08-21; 3 deferred to 2026-08-24"
        payload.pop("review_sha256", None)
        payload["review_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        cursor.execute("SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id IN %s", (tuple(x[1] for x in BLOCKED.values()),))
        if int((cursor.fetchone() or {}).get("count") or 0):
            raise RuntimeError("blocked_touch_in_queue")
        connection.commit()
        PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"deferred": list(BLOCKED), "deferred_to": DEFERRED.isoformat(), "ready_aug21": 17, "queued": 0}, ensure_ascii=False))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
