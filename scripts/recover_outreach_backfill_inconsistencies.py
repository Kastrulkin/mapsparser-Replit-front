#!/usr/bin/env python3
"""Audit or requeue only inconsistent LocalOS sales enrichment results.

The default safe mode is ``--dry-run``. Execution never sends messages and
never enables paid enrichment; it only creates fresh enrichment jobs for the
explicitly selected inconsistent workstreams.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from database_manager import DatabaseManager
from services.contact_intelligence_service import enqueue_enrichment_job


INCONSISTENT_WORKSTREAMS_SQL = """
WITH latest_research AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           COALESCE(NULLIF(message_readiness_json ->> 'code', ''), 'missing_code') AS readiness_code,
           researched_at
    FROM lead_workstream_research
    ORDER BY workstream_id, researched_at DESC, created_at DESC
),
latest_job AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           id AS job_id,
           status AS job_status,
           NULLIF(result_json ->> 'draft_id', '') AS result_draft_id,
           updated_at AS job_updated_at
    FROM lead_enrichment_jobs
    ORDER BY workstream_id, created_at DESC
),
draft_rollup AS (
    SELECT workstream_id,
           COUNT(*) FILTER (
               WHERE research_id IS NOT NULL
                 AND quality_gate_json ->> 'passed' = 'true'
           ) AS sourced_passed_draft_count
    FROM outreachmessagedrafts
    GROUP BY workstream_id
)
SELECT ws.id AS workstream_id,
       lead.id AS lead_id,
       lead.name AS lead_name,
       latest_research.readiness_code,
       latest_research.researched_at,
       latest_job.job_id,
       latest_job.job_status,
       latest_job.result_draft_id,
       latest_job.job_updated_at,
       COALESCE(draft_rollup.sourced_passed_draft_count, 0) AS sourced_passed_draft_count
FROM lead_workstreams ws
JOIN prospectingleads lead ON lead.id = ws.lead_id
JOIN latest_research ON latest_research.workstream_id = ws.id
JOIN latest_job ON latest_job.workstream_id = ws.id
LEFT JOIN draft_rollup ON draft_rollup.workstream_id = ws.id
WHERE ws.workstream_type = 'localos_sales'
  AND latest_job.job_status = 'ready'
  AND (
      latest_research.readiness_code <> 'ready'
      OR latest_job.result_draft_id IS NULL
      OR COALESCE(draft_rollup.sourced_passed_draft_count, 0) = 0
  )
ORDER BY latest_job.job_updated_at, ws.id
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Report inconsistencies without writing")
    mode.add_argument("--execute", action="store_true", help="Queue fresh free enrichment jobs")
    parser.add_argument(
        "--workstream-id",
        action="append",
        default=[],
        help="Explicit inconsistent workstream to requeue; repeat for several",
    )
    parser.add_argument(
        "--all-flagged",
        action="store_true",
        help="With --execute, requeue every currently flagged workstream",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum flagged rows; 0 means all")
    return parser.parse_args()


def inconsistency_action(row: dict[str, Any]) -> str:
    if str(row.get("readiness_code") or "") != "ready":
        return "reconcile_terminal_status"
    if not str(row.get("result_draft_id") or "").strip():
        return "regenerate_missing_sourced_draft"
    if int(row.get("sourced_passed_draft_count") or 0) == 0:
        return "regenerate_failed_or_legacy_draft"
    return "none"


def select_flagged_rows(cursor, *, limit: int = 0) -> list[dict[str, Any]]:
    sql = INCONSISTENT_WORKSTREAMS_SQL
    params: tuple[Any, ...] = ()
    if limit > 0:
        sql += "\nLIMIT %s"
        params = (limit,)
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall() or []]


def build_report(rows: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    actions = Counter(inconsistency_action(row) for row in rows)
    actions.pop("none", None)
    return {
        "mode": mode,
        "workstream_type": "localos_sales",
        "flagged_workstreams": len(rows),
        "actions": dict(sorted(actions.items())),
        "workstream_ids": [str(row.get("workstream_id") or "") for row in rows],
        "external_send": False,
        "paid_enrichment": False,
    }


def main() -> int:
    args = parse_args()
    if args.execute and not args.all_flagged and not args.workstream_id:
        raise SystemExit("--execute requires --all-flagged or at least one --workstream-id")
    if args.all_flagged and not args.execute:
        raise SystemExit("--all-flagged is only valid with --execute")

    database = DatabaseManager()
    cursor = database.conn.cursor()
    rows = select_flagged_rows(cursor, limit=max(0, args.limit))
    report = build_report(rows, mode="execute" if args.execute else "dry-run")

    if args.dry_run:
        database.close()
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0

    requested_ids = {
        str(value or "").strip()
        for value in args.workstream_id
        if str(value or "").strip()
    }
    selected_rows = rows if args.all_flagged else [
        row for row in rows if str(row.get("workstream_id") or "") in requested_ids
    ]
    selected_ids = {str(row.get("workstream_id") or "") for row in selected_rows}
    missing_ids = sorted(requested_ids - selected_ids)
    if missing_ids:
        database.close()
        raise SystemExit(
            "Requested workstreams are not currently flagged: " + ", ".join(missing_ids)
        )

    queued_ids: list[str] = []
    try:
        for row in selected_rows:
            workstream_id = str(row.get("workstream_id") or "")
            job = enqueue_enrichment_job(
                cursor,
                workstream_id,
                force=True,
                allow_paid_enrichment=False,
            )
            if not job.get("reused"):
                queued_ids.append(workstream_id)
        database.conn.commit()
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()

    report.update({
        "selected_workstreams": len(selected_rows),
        "jobs_enqueued": len(queued_ids),
        "queued_workstream_ids": queued_ids,
    })
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
