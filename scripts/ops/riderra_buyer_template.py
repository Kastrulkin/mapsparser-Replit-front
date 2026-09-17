"""Prepare native campaigns from an authenticated Riderra template grant.

Default mode rolls the transaction back. ``--commit`` persists native campaign
queue rows; this script never creates authority and never dispatches mail.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from psycopg2.extras import RealDictCursor


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from pg_db_utils import get_db_connection  # noqa: E402
from services.outreach_campaign_service import (  # noqa: E402
    approve_campaign_by_riderra_template,
    build_riderra_template_preview,
    persist_preview,
)
from services.riderra_template_authorization_service import load_authorization  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records-sha256", required=True, help="Exact records hash returned by authenticated grant API")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--not-before", help="Optional timezone-aware ISO schedule; defaults to now")
    return parser.parse_args()


def scheduled_at(value: str | None) -> datetime:
    now = datetime.now(timezone.utc)
    if not value:
        return now
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed < now - timedelta(minutes=1):
        raise ValueError("not_before_must_be_timezone_aware_and_not_in_past")
    return parsed


def main() -> int:
    args = parse_args()
    when = scheduled_at(args.not_before)
    os.environ["OUTREACH_ROOM_SYNC_ENABLED"] = "false"
    conn = get_db_connection()
    results: list[dict[str, str]] = []
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        grant = load_authorization(cursor)
        manifest = grant.get("manifest") if grant else {}
        if not grant or manifest.get("records_sha256") != args.records_sha256:
            raise ValueError("exact_live_riderra_grant_required")
        for record in manifest["records"]:
            preview = build_riderra_template_preview(cursor, record, start_at=when)
            saved = persist_preview(cursor, preview, user_id=grant["approved_by"])
            approved = approve_campaign_by_riderra_template(cursor, str(saved["id"]))
            results.append({"workstream_id": record["workstream_id"], "campaign_id": str(saved["id"]),
                            "batch_id": str(approved["batch_id"]), "approval_mode": str(approved["approval_mode"])})
        if args.commit:
            conn.commit()
        else:
            conn.rollback()
        print(json.dumps({
            "mode": "commit" if args.commit else "rolled_back_dry_run",
            "authorization_id": grant["id"], "records_sha256": manifest["records_sha256"],
            "prepared": len(results), "campaigns": results, "external_dispatch_performed": False,
        }, ensure_ascii=False))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
