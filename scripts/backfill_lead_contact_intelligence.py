#!/usr/bin/env python3
"""Dry-run or enqueue free contact intelligence for existing lead workstreams."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from database_manager import DatabaseManager
from services.contact_intelligence_service import enqueue_enrichment_job, legacy_contact_candidates, upsert_contact_points


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show scope without writing")
    mode.add_argument("--execute", action="store_true", help="Save legacy contacts and enqueue free jobs")
    parser.add_argument("--limit", type=int, default=0, help="Maximum workstreams; 0 means all")
    parser.add_argument(
        "--workstream-type",
        choices=("localos_sales", "client_partnership"),
        help="Optional workstream filter",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = DatabaseManager()
    cursor = database.conn.cursor()
    where = []
    params = []
    if args.workstream_type:
        where.append("ws.workstream_type = %s")
        params.append(args.workstream_type)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    limit_sql = "LIMIT %s" if args.limit > 0 else ""
    if args.limit > 0:
        params.append(args.limit)
    cursor.execute(
        f"""
        SELECT ws.id AS workstream_id, ws.workstream_type, ws.status,
               lead.id, lead.name, lead.phone, lead.email, lead.telegram_url,
               lead.whatsapp_url, lead.website, lead.source_url, lead.messenger_links_json
        FROM lead_workstreams ws
        JOIN prospectingleads lead ON lead.id = ws.lead_id
        {where_sql}
        ORDER BY ws.created_at ASC
        {limit_sql}
        """,
        tuple(params),
    )
    rows = [dict(row) for row in cursor.fetchall() or []]
    report = {
        "mode": "execute" if args.execute else "dry-run",
        "workstreams": len(rows),
        "legacy_contact_candidates": sum(len(legacy_contact_candidates(row)) for row in rows),
        "jobs_enqueued": 0,
        "jobs_reused": 0,
        "contacts_saved": 0,
        "paid_enrichment": False,
    }
    if args.dry_run:
        database.close()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    try:
        for index, row in enumerate(rows, start=1):
            report["contacts_saved"] += upsert_contact_points(cursor, str(row["id"]), legacy_contact_candidates(row))
            job = enqueue_enrichment_job(
                cursor,
                str(row["workstream_id"]),
                allow_paid_enrichment=False,
            )
            if job.get("reused"):
                report["jobs_reused"] += 1
            else:
                report["jobs_enqueued"] += 1
            if index % 100 == 0:
                database.conn.commit()
        database.conn.commit()
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
