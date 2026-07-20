#!/usr/bin/env python3
"""Register Telegram references already stored on leads as scoped radar candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pg_db_utils import get_db_connection
from services.discovered_telegram_source_service import sync_discovered_telegram_sources


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--commit-every", type=int, default=50)
    args = parser.parse_args()

    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT *
        FROM prospectingleads
        WHERE COALESCE(telegram_url, '') ILIKE '%%t.me/%%'
           OR COALESCE(messenger_links_json::text, '') ILIKE '%%t.me/%%'
        ORDER BY updated_at DESC, id
    """
    params: tuple[Any, ...] = ()
    if args.limit > 0:
        query += " LIMIT %s"
        params = (args.limit,)
    cursor.execute(query, params)
    leads = [_row_dict(row) for row in cursor.fetchall() or []]
    cursor.close()

    summary = {
        "mode": "execute" if args.execute else "dry_run",
        "leads_seen": len(leads),
        "leads_processed": 0,
        "references": 0,
        "source_links": 0,
        "queued": 0,
        "errors": [],
    }
    if not args.execute:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        conn.close()
        return 0

    commit_every = max(1, int(args.commit_every or 50))
    for index, lead in enumerate(leads, start=1):
        transaction_cursor = conn.cursor()
        transaction_cursor.execute("SAVEPOINT telegram_source_backfill")
        transaction_cursor.close()
        try:
            result = sync_discovered_telegram_sources(conn, lead)
            transaction_cursor = conn.cursor()
            transaction_cursor.execute("RELEASE SAVEPOINT telegram_source_backfill")
            transaction_cursor.close()
            summary["leads_processed"] += 1
            summary["references"] += int(result.get("references") or 0)
            summary["source_links"] += int(result.get("sources") or 0)
            summary["queued"] += int(result.get("queued") or 0)
            if index % commit_every == 0:
                conn.commit()
        except Exception as error:
            transaction_cursor = conn.cursor()
            transaction_cursor.execute("ROLLBACK TO SAVEPOINT telegram_source_backfill")
            transaction_cursor.execute("RELEASE SAVEPOINT telegram_source_backfill")
            transaction_cursor.close()
            summary["errors"].append({
                "lead_id": str(lead.get("id") or ""),
                "message": f"{type(error).__name__}: {error}"[:500],
            })
    conn.commit()
    conn.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
