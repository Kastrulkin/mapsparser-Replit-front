#!/usr/bin/env python3

import json

from pg_db_utils import get_db_connection
from core.review_response_utils import extract_review_response_text


def main() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, raw_payload
        FROM externalbusinessreviews
        WHERE COALESCE(TRIM(response_text), '') = ''
          AND COALESCE(TRIM(raw_payload), '') <> ''
        """
    )
    rows = cur.fetchall() or []

    scanned = 0
    updated = 0
    for row in rows:
        scanned += 1
        review_id = row["id"] if hasattr(row, "keys") else row[0]
        raw_payload = row["raw_payload"] if hasattr(row, "keys") else row[1]
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        except Exception:
            continue
        response_text = extract_review_response_text(payload)
        if not response_text:
            continue
        cur.execute(
            """
            UPDATE externalbusinessreviews
            SET response_text = %s,
                updated_at = NOW()
            WHERE id = %s
              AND COALESCE(TRIM(response_text), '') = ''
            """,
            (response_text, review_id),
        )
        updated += int(cur.rowcount or 0)

    conn.commit()
    print({"scanned": scanned, "updated": updated})
    conn.close()


if __name__ == "__main__":
    main()
