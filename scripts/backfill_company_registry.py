#!/usr/bin/env python3
"""Preview or apply the first safe company-registry backfill.

Dry-run is the default. Use --apply only after a production backup.
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
from services.company_registry_service import ensure_company_for_business, ensure_company_for_lead


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()
    if args.apply and os.getenv("COMPANY_REGISTRY_BACKFILL_APPROVED") != "true":
        print(json.dumps({"status": "blocked", "reason": "set COMPANY_REGISTRY_BACKFILL_APPROVED=true after backup"}, ensure_ascii=False))
        return 2

    db = DatabaseManager()
    report = {
        "mode": "apply" if args.apply else "dry_run",
        "businesses": 0,
        "businesses_already_linked": 0,
        "businesses_would_create": 0,
        "businesses_created": 0,
        "leads": 0,
        "leads_already_linked": 0,
        "leads_would_resolve": 0,
        "leads_resolved": 0,
        "shadow_businesses": 0,
        "shadow_businesses_detection": "moderation_status",
        "leads_with_strong_identity": 0,
        "leads_without_strong_identity": 0,
        "public_rows_without_company_location": {},
        "tables_unavailable": [],
        "legacy_public_telegram_source_groups": 0,
        "errors": [],
    }
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'businesses'
                  AND column_name = 'moderation_status'
            ) AS exists
            """
        )
        moderation_column_row = cursor.fetchone()
        has_moderation_status = bool(
            moderation_column_row.get("exists")
            if hasattr(moderation_column_row, "get")
            else moderation_column_row[0]
        )
        if has_moderation_status:
            cursor.execute("SELECT COUNT(*) AS count FROM businesses WHERE COALESCE(moderation_status, '') = 'lead_outreach'")
            shadow_row = cursor.fetchone()
            report["shadow_businesses"] = int((shadow_row.get("count") if hasattr(shadow_row, "get") else shadow_row[0]) or 0)
            business_filter = "WHERE COALESCE(b.moderation_status, '') <> 'lead_outreach'"
        else:
            report["shadow_businesses_detection"] = "unavailable_on_legacy_schema"
            business_filter = ""
        cursor.execute(
            f"""
            SELECT b.*,
                   EXISTS (SELECT 1 FROM business_company_links link WHERE link.business_id = b.id) AS registry_linked
            FROM businesses b
            {business_filter}
            ORDER BY b.created_at ASC
            LIMIT %s
            """,
            (max(1, min(args.limit, 100000)),),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        report["businesses"] = len(rows)
        for business in rows:
            if business.get("registry_linked"):
                report["businesses_already_linked"] += 1
                continue
            report["businesses_would_create"] += 1
            if not args.apply:
                continue
            try:
                cursor.execute("SAVEPOINT company_registry_business")
                ensure_company_for_business(db.conn, business)
                cursor.execute("RELEASE SAVEPOINT company_registry_business")
                report["businesses_created"] += 1
            except Exception as exc:
                cursor.execute("ROLLBACK TO SAVEPOINT company_registry_business")
                cursor.execute("RELEASE SAVEPOINT company_registry_business")
                report["errors"].append({"business_id": business.get("id"), "error": str(exc)})
        cursor.execute(
            """
            SELECT * FROM prospectingleads
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (max(1, min(args.limit, 100000)),),
        )
        leads = [dict(row) for row in cursor.fetchall()]
        report["leads"] = len(leads)
        for lead in leads:
            has_strong_identity = bool(
                str(lead.get("source_external_id") or lead.get("google_id") or "").strip()
                or str(lead.get("source_url") or "").strip()
                or (str(lead.get("phone") or "").strip() and str(lead.get("address") or "").strip())
                or (str(lead.get("website") or "").strip() and str(lead.get("city") or "").strip())
            )
            if has_strong_identity:
                report["leads_with_strong_identity"] += 1
            else:
                report["leads_without_strong_identity"] += 1
            if lead.get("company_id"):
                report["leads_already_linked"] += 1
                continue
            report["leads_would_resolve"] += 1
            if not args.apply:
                continue
            try:
                cursor.execute("SAVEPOINT company_registry_lead")
                ensure_company_for_lead(db.conn, str(lead["id"]), lead, source="lead_backfill")
                cursor.execute("RELEASE SAVEPOINT company_registry_lead")
                report["leads_resolved"] += 1
            except Exception as exc:
                cursor.execute("ROLLBACK TO SAVEPOINT company_registry_lead")
                cursor.execute("RELEASE SAVEPOINT company_registry_lead")
                report["errors"].append({"lead_id": lead.get("id"), "error": str(exc)})
        public_tables = (
            "parsequeue",
            "cards",
            "externalbusinessreviews",
            "externalbusinessposts",
            "externalbusinessphotos",
            "externalbusinessstats",
            "businessmetricshistory",
        )
        available_public_tables = []
        for public_table in public_tables:
            cursor.execute("SELECT to_regclass(%s) AS table_name", (f"public.{public_table}",))
            table_row = cursor.fetchone()
            table_name = table_row.get("table_name") if hasattr(table_row, "get") else table_row[0]
            if not table_name:
                report["tables_unavailable"].append(public_table)
                continue
            available_public_tables.append(public_table)
        if args.apply:
            for public_table in available_public_tables:
                cursor.execute(
                    f"""
                    UPDATE {public_table} public_row
                    SET company_location_id = link.company_location_id
                    FROM business_company_links link
                    WHERE public_row.business_id = link.business_id
                      AND public_row.company_location_id IS NULL
                      AND link.is_primary = TRUE
                    """
                )
            for audit_table in ("adminprospectingleadpublicoffers", "sales_room_audit_offers"):
                cursor.execute("SELECT to_regclass(%s) AS table_name", (f"public.{audit_table}",))
                table_row = cursor.fetchone()
                table_name = table_row.get("table_name") if hasattr(table_row, "get") else table_row[0]
                if not table_name:
                    report["tables_unavailable"].append(audit_table)
                    continue
                cursor.execute(
                    f"""
                    UPDATE {audit_table} audit
                    SET company_id = lead.company_id,
                        company_location_id = lead.company_location_id
                    FROM prospectingleads lead
                    WHERE audit.lead_id = lead.id
                      AND audit.company_id IS NULL
                      AND lead.company_id IS NOT NULL
                    """
                )
            cursor.execute("SELECT to_regclass('public.partnership_partner_cards') AS table_name")
            partnership_table_row = cursor.fetchone()
            partnership_table_name = (
                partnership_table_row.get("table_name")
                if hasattr(partnership_table_row, "get")
                else partnership_table_row[0]
            )
            if partnership_table_name:
                cursor.execute(
                    """
                    UPDATE partnership_partner_cards card
                    SET company_id = lead.company_id,
                        company_location_id = lead.company_location_id,
                        updated_at = NOW()
                    FROM prospectingleads lead
                    WHERE card.lead_id = lead.id
                      AND card.company_id IS NULL
                      AND lead.company_id IS NOT NULL
                    """
                )
            else:
                report["tables_unavailable"].append("partnership_partner_cards")
        for public_table in available_public_tables:
            cursor.execute(f"SELECT COUNT(*) AS count FROM {public_table} WHERE company_location_id IS NULL")
            missing_row = cursor.fetchone()
            report["public_rows_without_company_location"][public_table] = int((missing_row.get("count") if hasattr(missing_row, "get") else missing_row[0]) or 0)
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM (
                SELECT LOWER(REGEXP_REPLACE(canonical_url, '/+$', '')) AS canonical_source
                FROM knowledge_sources
                WHERE source_type = 'telegram' AND visibility = 'public'
                  AND canonical_url ~* '^https?://(www\\.)?t\\.me/[A-Za-z0-9_]+'
                GROUP BY LOWER(REGEXP_REPLACE(canonical_url, '/+$', ''))
                HAVING COUNT(*) > 1
            ) duplicate_sources
            """
        )
        duplicate_row = cursor.fetchone()
        report["legacy_public_telegram_source_groups"] = int((duplicate_row.get("count") if hasattr(duplicate_row, "get") else duplicate_row[0]) or 0)
        if args.apply:
            db.conn.commit()
        else:
            db.conn.rollback()
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
        return 0 if not report["errors"] else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
