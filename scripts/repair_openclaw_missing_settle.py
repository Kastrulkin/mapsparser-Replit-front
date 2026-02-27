#!/usr/bin/env python3
"""
Repair helper for OpenClaw billing reconciliation issues (missing_settle).

Default mode is dry-run (no DB writes).
Use --apply to insert missing settle ledger entries.
"""

import argparse
import json
from datetime import datetime, timezone

from database_manager import DatabaseManager
from core.action_ledger import ensure_ledger_tables, write_ledger_entry


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair missing settle entries for completed actions")
    parser.add_argument("--tenant-id", required=True, help="Business/tenant id")
    parser.add_argument("--window-minutes", type=int, default=30 * 24 * 60, help="Lookback window")
    parser.add_argument("--limit", type=int, default=500, help="Max actions to inspect")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (otherwise dry-run)")
    args = parser.parse_args()

    tenant_id = str(args.tenant_id).strip()
    window_minutes = max(1, min(int(args.window_minutes or 30 * 24 * 60), 180 * 24 * 60))
    limit = max(1, min(int(args.limit or 500), 5000))

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_ledger_tables(cursor)
        cursor.execute(
            """
            SELECT
                ar.action_id,
                ar.billing_json,
                ar.created_at,
                COALESCE(SUM(CASE WHEN bl.entry_type='reserve' THEN bl.tokens_out ELSE 0 END), 0) AS reserve_total,
                COALESCE(SUM(CASE WHEN bl.entry_type='settle' THEN bl.tokens_out ELSE 0 END), 0) AS settle_total,
                COALESCE(SUM(CASE WHEN bl.entry_type='release' THEN bl.tokens_out ELSE 0 END), 0) AS release_total
            FROM action_requests ar
            LEFT JOIN billing_ledger bl ON bl.action_id = ar.action_id
            WHERE ar.tenant_id = %s
              AND ar.status = 'completed'
              AND ar.created_at >= (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
            GROUP BY ar.action_id, ar.billing_json, ar.created_at
            ORDER BY ar.created_at DESC
            LIMIT %s
            """,
            (tenant_id, window_minutes, limit),
        )
        rows = cursor.fetchall() or []

        candidates = []
        for row in rows:
            action_id = str(row[0] or "")
            billing_json = row[1] if isinstance(row[1], dict) else {}
            reserve_total = int(row[3] or 0)
            settle_total = int(row[4] or 0)
            release_total = int(row[5] or 0)
            if reserve_total <= 0 or settle_total > 0:
                continue
            expected_settle = max(0, reserve_total - release_total)
            if expected_settle <= 0:
                continue
            candidates.append(
                {
                    "action_id": action_id,
                    "reserve_total": reserve_total,
                    "settle_total": settle_total,
                    "release_total": release_total,
                    "expected_settle": expected_settle,
                    "tariff_id": str((billing_json or {}).get("tariff_id") or ""),
                }
            )

        inserted = []
        if args.apply:
            for item in candidates:
                entry_id = write_ledger_entry(
                    cursor,
                    action_id=item["action_id"],
                    tenant_id=tenant_id,
                    entry_type="settle",
                    tokens_out=item["expected_settle"],
                    cost=0.0,
                    tariff_id=item["tariff_id"] or None,
                    meta={
                        "repair": "missing_settle",
                        "repaired_at": _utc_iso(),
                        "reserve_total": item["reserve_total"],
                        "release_total": item["release_total"],
                        "previous_settle_total": item["settle_total"],
                    },
                )
                inserted.append({"action_id": item["action_id"], "entry_id": entry_id, "tokens_out": item["expected_settle"]})
            db.conn.commit()
        else:
            db.conn.rollback()

        print(
            json.dumps(
                {
                    "success": True,
                    "tenant_id": tenant_id,
                    "dry_run": not args.apply,
                    "window_minutes": window_minutes,
                    "inspected": len(rows),
                    "candidates": len(candidates),
                    "inserted": len(inserted),
                    "items": inserted if args.apply else candidates,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        db.conn.rollback()
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
