#!/usr/bin/env python3
"""Audit actual Gmail intervals for the 40 already prepared follow-up drafts."""

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from psycopg2.extras import RealDictCursor

from database_manager import get_db_connection
from dispatch_v4_email_queue_20260820 import gmail_mailboxes, imap_search, read_message, sender_account
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config


MANIFEST = Path("/app/debug_data/localos-1000-safe-final-manifest-v4-20260814.json")
FINALS = (
    Path("/app/debug_data/localos-followup-batch-01-final-20260820.json"),
    Path("/app/debug_data/localos-followup-batch-02-final-20260820.json"),
)
PLANNED = datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc)


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = {x["touch_id"]: x for x in manifest.get("touches") or []}
    items = []
    for path in FINALS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("items") or []:
            items.append((payload["batch_id"], item, rows[item["first_touch_id"]]))
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    sender = sender_account(cursor)
    connection.rollback()
    client = _imap_connection(load_mailbox_config(sender), timeout=25)
    _, sent_name = gmail_mailboxes(client)
    results = []
    try:
        for batch_id, item, first in items:
            messages = [read_message(client, sent_name, uid) for uid in imap_search(client, sent_name, f"to:{item['recipient']}")[-20:]]
            exact = [m for m in messages if m.get("subject") == first.get("subject", "").strip() and m.get("body") == first.get("text", "").strip()]
            sent_at = None
            if len(exact) == 1 and exact[0].get("date"):
                sent_at = parsedate_to_datetime(exact[0]["date"])
                if sent_at.tzinfo is None:
                    sent_at = sent_at.replace(tzinfo=timezone.utc)
                sent_at = sent_at.astimezone(timezone.utc)
            interval = (PLANNED - sent_at).total_seconds() / 3600 if sent_at else None
            results.append({
                "batch_id": batch_id, "name": item["name"], "recipient": item["recipient"],
                "first_touch_id": item["first_touch_id"], "first_sent_at": sent_at.isoformat() if sent_at else None,
                "interval_hours": round(interval, 2) if interval is not None else None,
                "eligible_72h": interval is not None and interval >= 72,
            })
    finally:
        _close_imap(client)
        connection.rollback()
        connection.close()
    blocked = [x for x in results if not x["eligible_72h"]]
    print(json.dumps({"total": len(results), "eligible_72h": len(results)-len(blocked), "blocked": len(blocked), "blocked_items": blocked, "items": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
