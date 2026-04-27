#!/usr/bin/env python3
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pg_db_utils import get_db_connection
from parsing_failure_taxonomy import classify_failure_reason, REASON_CLOSED_BUSINESS, REASON_TASK_TTL_EXCEEDED


def _row_dict(row: Any) -> Dict[str, Any]:
    if hasattr(row, "keys"):
        return dict(row)
    return {
        "id": row[0],
        "url": row[1],
        "business_id": row[2],
        "status": row[3],
        "error_message": row[4],
        "retry_after": row[5],
        "updated_at": row[6],
    }


def _load_rows(cur, since_ts: str) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT id, url, business_id, status, error_message, retry_after, updated_at
        FROM parsequeue
        WHERE updated_at >= %s
        ORDER BY updated_at DESC
        """,
        (since_ts,),
    )
    return [_row_dict(row) for row in (cur.fetchall() or [])]


def _dedupe_latest_by_key(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("url") or row.get("business_id") or row.get("id") or "").strip()
        if not key:
            continue
        latest.setdefault(key, row)
    return list(latest.values())


def _is_superseded_ttl(row: Dict[str, Any], latest_by_key: Dict[str, Dict[str, Any]]) -> bool:
    text = str(row.get("error_message") or "")
    if classify_failure_reason(row.get("status"), text) != REASON_TASK_TTL_EXCEEDED:
        return False
    key = str(row.get("url") or row.get("business_id") or row.get("id") or "").strip()
    if not key:
        return False
    latest = latest_by_key.get(key)
    if not latest:
        return False
    return str(latest.get("id") or "") != str(row.get("id") or "")


def _build_snapshot(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest_rows = _dedupe_latest_by_key(rows)
    latest_by_key = {
        str(row.get("url") or row.get("business_id") or row.get("id") or "").strip(): row
        for row in latest_rows
        if str(row.get("url") or row.get("business_id") or row.get("id") or "").strip()
    }

    raw_errors = [row for row in rows if str(row.get("status") or "").lower() == "error"]
    latest_errors = [row for row in latest_rows if str(row.get("status") or "").lower() == "error"]

    raw_counter = Counter()
    operational_counter = Counter()
    superseded_ttl_rows: List[Dict[str, Any]] = []

    for row in raw_errors:
        reason = classify_failure_reason(row.get("status"), row.get("error_message"))
        raw_counter[reason] += 1
        if _is_superseded_ttl(row, latest_by_key):
            superseded_ttl_rows.append(row)

    for row in latest_errors:
        reason = classify_failure_reason(row.get("status"), row.get("error_message"))
        if reason == REASON_CLOSED_BUSINESS:
            continue
        if _is_superseded_ttl(row, latest_by_key):
            continue
        operational_counter[reason] += 1

    return {
        "generated_at": datetime.now().isoformat(),
        "window_rows_total": len(rows),
        "latest_rows_total": len(latest_rows),
        "raw_error_count": len(raw_errors),
        "latest_error_count": len(latest_errors),
        "raw_error_buckets": dict(raw_counter.most_common()),
        "operational_error_buckets": dict(operational_counter.most_common()),
        "superseded_ttl_count": len(superseded_ttl_rows),
        "superseded_ttl_examples": [
            {
                "id": row.get("id"),
                "url": row.get("url"),
                "updated_at": str(row.get("updated_at") or ""),
                "error_message": str(row.get("error_message") or "")[:220],
            }
            for row in superseded_ttl_rows[:10]
        ],
        "latest_actionable_errors": [
            {
                "id": row.get("id"),
                "url": row.get("url"),
                "updated_at": str(row.get("updated_at") or ""),
                "reason": classify_failure_reason(row.get("status"), row.get("error_message")),
                "error_message": str(row.get("error_message") or "")[:220],
            }
            for row in latest_errors
            if classify_failure_reason(row.get("status"), row.get("error_message")) != REASON_CLOSED_BUSINESS
            and not _is_superseded_ttl(row, latest_by_key)
        ][:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-ts", required=True, help="Lower bound for parsequeue.updated_at, e.g. 2026-04-06 00:00:00+00")
    parser.add_argument("--json-out", default="", help="Optional JSON output file")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        rows = _load_rows(cur, args.since_ts)
        snapshot = _build_snapshot(rows)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
