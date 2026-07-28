#!/usr/bin/env python3
"""Restore canonical company coordinates from already collected public data.

Dry-run is the default. Apply requires an explicit environment gate and must
only be run after a production backup.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from database_manager import DatabaseManager
from services.company_registry_service import (
    ensure_company_for_business,
    ensure_company_for_lead,
    resolve_company_coordinates,
)


def _has_coordinates(payload: dict) -> bool:
    latitude, longitude = resolve_company_coordinates(payload)
    return latitude is not None and longitude is not None


def _mapped_company_ids(cursor) -> set[str]:
    cursor.execute(
        """
        SELECT DISTINCT c.id
        FROM companies c
        JOIN company_locations location ON location.company_id = c.id
        WHERE c.status IN ('observed', 'active')
          AND location.status = 'active'
          AND location.latitude IS NOT NULL
          AND location.longitude IS NOT NULL
        """
    )
    return {
        str(row.get("id") if hasattr(row, "get") else row[0])
        for row in cursor.fetchall()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100000)
    args = parser.parse_args()
    if args.apply and os.getenv("COMPANY_REGISTRY_COORDINATES_BACKFILL_APPROVED") != "true":
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "set COMPANY_REGISTRY_COORDINATES_BACKFILL_APPROVED=true after backup",
                },
                ensure_ascii=False,
            )
        )
        return 2

    db = DatabaseManager()
    cursor = db.conn.cursor()
    report = {
        "mode": "apply" if args.apply else "dry_run",
        "mapped_before": 0,
        "business_rows_checked": 0,
        "business_coordinate_candidates": 0,
        "lead_rows_checked": 0,
        "lead_coordinate_candidates": 0,
        "candidate_locations": 0,
        "candidate_companies": 0,
        "estimated_mapped_after": 0,
        "mapped_after": 0,
        "updated_locations": 0,
        "errors": [],
    }
    safe_limit = max(1, min(args.limit, 200000))
    candidate_locations: set[str] = set()
    candidate_companies: set[str] = set()
    try:
        mapped_before_ids = _mapped_company_ids(cursor)
        report["mapped_before"] = len(mapped_before_ids)
        cursor.execute(
            """
            SELECT business.*, link.company_id AS registry_company_id,
                   link.company_location_id AS registry_location_id
            FROM business_company_links link
            JOIN businesses business ON business.id = link.business_id
            JOIN company_locations location ON location.id = link.company_location_id
            WHERE location.status = 'active'
              AND (location.latitude IS NULL OR location.longitude IS NULL)
            ORDER BY business.created_at, business.id
            LIMIT %s
            """,
            (safe_limit,),
        )
        business_rows = [dict(row) for row in cursor.fetchall()]
        report["business_rows_checked"] = len(business_rows)
        for business in business_rows:
            if not _has_coordinates(business):
                continue
            report["business_coordinate_candidates"] += 1
            candidate_locations.add(str(business.get("registry_location_id") or ""))
            candidate_companies.add(str(business.get("registry_company_id") or ""))
            if not args.apply:
                continue
            try:
                cursor.execute("SAVEPOINT company_coordinate_business")
                ensure_company_for_business(db.conn, business, source="business_coordinate_backfill")
                cursor.execute("RELEASE SAVEPOINT company_coordinate_business")
            except Exception as exc:
                cursor.execute("ROLLBACK TO SAVEPOINT company_coordinate_business")
                cursor.execute("RELEASE SAVEPOINT company_coordinate_business")
                report["errors"].append({"business_id": business.get("id"), "error": str(exc)})

        cursor.execute(
            """
            SELECT lead.*
            FROM prospectingleads lead
            JOIN company_locations location ON location.id = lead.company_location_id
            WHERE lead.company_id IS NOT NULL
              AND lead.company_location_id IS NOT NULL
              AND location.status = 'active'
              AND (location.latitude IS NULL OR location.longitude IS NULL)
            ORDER BY lead.created_at, lead.id
            LIMIT %s
            """,
            (safe_limit,),
        )
        lead_rows = [dict(row) for row in cursor.fetchall()]
        report["lead_rows_checked"] = len(lead_rows)
        for lead in lead_rows:
            if not _has_coordinates(lead):
                continue
            report["lead_coordinate_candidates"] += 1
            candidate_locations.add(str(lead.get("company_location_id") or ""))
            candidate_companies.add(str(lead.get("company_id") or ""))
            if not args.apply:
                continue
            try:
                cursor.execute("SAVEPOINT company_coordinate_lead")
                ensure_company_for_lead(
                    db.conn,
                    str(lead["id"]),
                    lead,
                    source="lead_coordinate_backfill",
                )
                cursor.execute("RELEASE SAVEPOINT company_coordinate_lead")
            except Exception as exc:
                cursor.execute("ROLLBACK TO SAVEPOINT company_coordinate_lead")
                cursor.execute("RELEASE SAVEPOINT company_coordinate_lead")
                report["errors"].append({"lead_id": lead.get("id"), "error": str(exc)})

        candidate_locations.discard("")
        candidate_companies.discard("")
        report["candidate_locations"] = len(candidate_locations)
        report["candidate_companies"] = len(candidate_companies)
        report["estimated_mapped_after"] = len(mapped_before_ids | candidate_companies)
        if args.apply:
            db.conn.commit()
        else:
            db.conn.rollback()
        report["mapped_after"] = len(_mapped_company_ids(cursor))
        report["updated_locations"] = max(0, report["mapped_after"] - report["mapped_before"])
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
        return 0 if not report["errors"] else 1
    finally:
        cursor.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
