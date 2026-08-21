#!/usr/bin/env python3
"""Replace proposed IDs in the frozen artifact with canonical PostgreSQL touch IDs."""

import hashlib
import json
from pathlib import Path

from psycopg2.extras import RealDictCursor

from database_manager import get_db_connection


PATH = Path("/app/debug_data/localos-followup-batch-02-final-20260820.json")


def main():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    changes = []
    try:
        for item in payload.get("items") or []:
            cursor.execute(
                """
                SELECT id,status,approved_text FROM outreach_campaign_touches
                WHERE campaign_id=%s AND sequence_index=1 AND channel='email'
                """,
                (item["campaign_id"],),
            )
            row = dict(cursor.fetchone() or {})
            if row.get("status") != "draft" or row.get("approved_text") is not None:
                raise RuntimeError(f"canonical_draft_missing:{item['name']}")
            actual = str(row["id"])
            old = str(item.get("proposed_touch_id") or "")
            if old != actual:
                changes.append({"name": item["name"], "old": old, "actual": actual})
            item["proposed_touch_id"] = actual
            item["actual_touch_id"] = actual
        payload.pop("review_sha256", None)
        payload["review_sha256"] = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"reconciled": len(payload.get('items') or []), "changed": changes, "review_sha256": payload["review_sha256"]}, ensure_ascii=False))
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
