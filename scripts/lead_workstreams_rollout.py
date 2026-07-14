#!/usr/bin/env python3
"""Audit and idempotently backfill lead workstreams after the Alembic migration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pg_db_utils import get_db_connection


def collect_report(cur) -> dict:
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE COALESCE(intent, 'client_outreach') NOT IN ('partnership', 'partnership_outreach')
            ) AS localos_candidates,
            COUNT(*) FILTER (
                WHERE COALESCE(intent, 'client_outreach') IN ('partnership', 'partnership_outreach')
                  AND business_id IS NOT NULL
            ) AS partnership_candidates,
            COUNT(*) FILTER (
                WHERE COALESCE(intent, 'client_outreach') IN ('partnership', 'partnership_outreach')
                  AND business_id IS NULL
            ) AS ambiguous_missing_client,
            COUNT(*) FILTER (WHERE parse_business_id IS NOT NULL) AS parser_linked_leads
        FROM prospectingleads
        """
    )
    totals = dict(cur.fetchone())
    cur.execute(
        """
        SELECT l.id, l.name, l.source, l.intent, l.business_id, l.parse_business_id
        FROM prospectingleads l
        WHERE COALESCE(l.intent, 'client_outreach') IN ('partnership', 'partnership_outreach')
          AND (
              l.business_id IS NULL
              OR NOT EXISTS (SELECT 1 FROM businesses b WHERE b.id = l.business_id)
          )
        ORDER BY l.created_at ASC
        LIMIT 500
        """
    )
    ambiguous = [dict(row) for row in cur.fetchall() or []]
    cur.execute("SELECT to_regclass('public.lead_workstreams') AS table_name")
    table_exists = bool(dict(cur.fetchone()).get("table_name"))
    workstreams = {}
    if table_exists:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE workstream_type = 'localos_sales') AS localos_sales,
                COUNT(*) FILTER (WHERE workstream_type = 'client_partnership') AS client_partnership,
                COUNT(DISTINCT lead_id) FILTER (
                    WHERE lead_id IN (
                        SELECT lead_id
                        FROM lead_workstreams
                        GROUP BY lead_id
                        HAVING COUNT(DISTINCT workstream_type) > 1
                    )
                ) AS dual_context_companies
            FROM lead_workstreams
            """
        )
        workstreams = dict(cur.fetchone())
    return {
        "legacy": totals,
        "workstream_table_exists": table_exists,
        "workstreams": workstreams,
        "ambiguous": ambiguous,
    }


def backfill(cur) -> dict:
    cur.execute(
        """
        INSERT INTO lead_workstreams (
            id, lead_id, workstream_type, client_business_id, status,
            selected_channel, next_action_at, last_contact_at,
            last_contact_channel, last_contact_comment, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), l.id, 'localos_sales', NULL,
            COALESCE(NULLIF(l.pipeline_status, ''), 'unprocessed'),
            l.selected_channel, l.next_action_at, l.last_contact_at,
            l.last_contact_channel, l.last_contact_comment,
            COALESCE(l.created_at, NOW()), COALESCE(l.updated_at, l.created_at, NOW())
        FROM prospectingleads l
        WHERE COALESCE(l.intent, 'client_outreach') NOT IN ('partnership', 'partnership_outreach')
        ON CONFLICT DO NOTHING
        """
    )
    localos_inserted = cur.rowcount
    cur.execute(
        """
        INSERT INTO lead_workstreams (
            id, lead_id, workstream_type, client_business_id, status,
            selected_channel, next_action_at, last_contact_at,
            last_contact_channel, last_contact_comment, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), l.id, 'client_partnership', l.business_id,
            COALESCE(NULLIF(l.pipeline_status, ''), 'unprocessed'),
            l.selected_channel, l.next_action_at, l.last_contact_at,
            l.last_contact_channel, l.last_contact_comment,
            COALESCE(l.created_at, NOW()), COALESCE(l.updated_at, l.created_at, NOW())
        FROM prospectingleads l
        JOIN businesses b ON b.id = l.business_id
        WHERE COALESCE(l.intent, 'client_outreach') IN ('partnership', 'partnership_outreach')
        ON CONFLICT DO NOTHING
        """
    )
    partner_inserted = cur.rowcount
    return {"localos_inserted": localos_inserted, "partner_inserted": partner_inserted}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        before = collect_report(cur)
        result = {"mode": "dry-run", "before": before}
        if args.execute:
            if not before["workstream_table_exists"]:
                raise RuntimeError("lead_workstreams is missing; run Alembic migration first")
            result["mode"] = "execute"
            result["changes"] = backfill(cur)
            conn.commit()
            result["after"] = collect_report(cur)
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    rendered = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
