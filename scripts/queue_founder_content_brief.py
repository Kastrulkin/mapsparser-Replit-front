#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

from database_manager import DatabaseManager
from services.founder_content_editorial import queue_founder_content_brief, stable_brief_key


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue a truthful LocalOS product update for founder content")
    parser.add_argument("--title", required=True)
    parser.add_argument("--change", required=True)
    parser.add_argument("--rationale", default="")
    parser.add_argument("--source-ref", action="append", default=[])
    parser.add_argument("--proof", action="append", default=[])
    parser.add_argument("--priority", type=int, default=50)
    parser.add_argument("--created-by", default="")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    preview = {
        "content_key": stable_brief_key(arguments.title, arguments.change),
        "title": arguments.title,
        "change_summary": arguments.change,
        "rationale": arguments.rationale,
        "source_refs": list(arguments.source_ref or []),
        "proof": [{"text": item} for item in arguments.proof or []],
        "priority": max(0, min(int(arguments.priority), 100)),
        "mode": "apply" if arguments.apply else "dry_run",
    }
    if not arguments.apply:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return

    database = DatabaseManager()
    cursor = database.conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM founder_content_briefs WHERE content_key = %s LIMIT 1",
            (preview["content_key"],),
        )
        existing = cursor.fetchone()
        if existing:
            database.conn.rollback()
            print(json.dumps({**preview, "created": False, "reason_code": "duplicate"}, ensure_ascii=False, indent=2))
            return
        brief = queue_founder_content_brief(
            cursor,
            title=arguments.title,
            change_summary=arguments.change,
            rationale=arguments.rationale,
            created_by=arguments.created_by,
            proof=preview["proof"],
            source_refs=preview["source_refs"],
            priority=preview["priority"],
        )
        database.conn.commit()
        print(
            json.dumps(
                {
                    **preview,
                    "created": True,
                    "brief_id": str(brief.get("id") if isinstance(brief, dict) else ""),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception:
        database.conn.rollback()
        raise
    finally:
        cursor.close()
        database.close()


if __name__ == "__main__":
    main()
