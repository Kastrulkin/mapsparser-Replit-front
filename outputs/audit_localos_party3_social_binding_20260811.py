#!/usr/bin/env python3
"""Read-only Party 3 social-source binding audit."""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor


REVIEW = Path("/app/debug_data/localos-party3-review-v1-20260811.json")
OUTPUT = Path("/app/debug_data/localos-party3-social-binding-20260811.json")


def main() -> None:
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    workstream_ids = [item["workstream_id"] for item in review["results"]]
    connection = psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
    )
    connection.set_session(readonly=True, autocommit=False)
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION READ ONLY")
    try:
        cursor.execute(
            """
            SELECT ws.id AS workstream_id, l.id AS lead_id, l.name,
                   link.id AS link_id, link.status AS link_status,
                   link.source_type AS link_source_type,
                   link.source_id,
                   to_jsonb(link) AS link_json,
                   source.canonical_url, source.status AS source_status,
                   source.visibility,
                   to_jsonb(source) AS source_json,
                   cp.id AS contact_point_id, cp.contact_type,
                   cp.value AS contact_value, cp.normalized_value,
                   cp.verification_status, cp.source_url AS contact_source_url
            FROM lead_workstreams ws
            JOIN prospectingleads l ON l.id=ws.lead_id
            LEFT JOIN lead_signal_links link
              ON link.workstream_id=ws.id
             AND link.source_type='telegram_knowledge_source'
             AND link.status='selected'
            LEFT JOIN knowledge_sources source ON source.id::text=link.source_id
            LEFT JOIN lead_contact_points cp
              ON cp.lead_id=l.id AND cp.contact_type='telegram'
            WHERE ws.id=ANY(%s::uuid[])
            ORDER BY l.name,source.canonical_url,cp.id
            """,
            (workstream_ids,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        connection.rollback()
        connection.close()
    OUTPUT.write_text(
        json.dumps({"rows": rows, "database_mutations": 0}, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "database_mutations": 0}))


if __name__ == "__main__":
    main()
