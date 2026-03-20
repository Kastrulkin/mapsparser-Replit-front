#!/usr/bin/env python3
import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Any, Dict


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pg_db_utils import get_db_connection
from parsing_failure_taxonomy import classify_failure_reason


def _one_value(row: Any, key: str, idx: int = 0) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[idx]
    except Exception:
        return None


def _load_status_counts(cur, batch_id: str) -> Dict[str, int]:
    cur.execute(
        """
        SELECT status, COUNT(*) AS cnt
        FROM parsequeue
        WHERE batch_id = %s
        GROUP BY status
        ORDER BY status
        """,
        (batch_id,),
    )
    out: Dict[str, int] = {}
    for row in cur.fetchall() or []:
        status = str(_one_value(row, "status", 0) or "").strip().lower()
        cnt = int(_one_value(row, "cnt", 1) or 0)
        if status:
            out[status] = cnt
    return out


def _load_valid_strict(cur, batch_id: str) -> Dict[str, int]:
    cur.execute(
        """
        WITH done AS (
            SELECT business_id
            FROM parsequeue
            WHERE batch_id = %s
              AND status = 'completed'
        ),
        latest AS (
            SELECT
                d.business_id,
                c.title,
                c.address,
                c.rating,
                c.reviews_count,
                CASE
                    WHEN c.products IS NULL OR BTRIM(c.products) = '' THEN 0
                    ELSE jsonb_array_length(c.products::jsonb)
                END AS products_blocks,
                ROW_NUMBER() OVER (PARTITION BY d.business_id ORDER BY c.updated_at DESC NULLS LAST) AS rn
            FROM done d
            JOIN cards c ON c.business_id = d.business_id
        )
        SELECT
            COUNT(*) AS completed,
            COUNT(*) FILTER (
                WHERE NULLIF(TRIM(COALESCE(title, '')), '') IS NOT NULL
                  AND NULLIF(TRIM(COALESCE(address, '')), '') IS NOT NULL
            ) AS with_title_address,
            COUNT(*) FILTER (
                WHERE NULLIF(TRIM(COALESCE(rating::text, '')), '') IS NOT NULL
                   OR COALESCE(reviews_count, 0) > 0
            ) AS with_rating_or_reviews,
            COUNT(*) FILTER (WHERE products_blocks > 0) AS with_products,
            COUNT(*) FILTER (
                WHERE NULLIF(TRIM(COALESCE(title, '')), '') IS NOT NULL
                  AND NULLIF(TRIM(COALESCE(address, '')), '') IS NOT NULL
                  AND (
                        NULLIF(TRIM(COALESCE(rating::text, '')), '') IS NOT NULL
                     OR COALESCE(reviews_count, 0) > 0
                  )
                  AND products_blocks > 0
            ) AS valid_strict
        FROM latest
        WHERE rn = 1
        """,
        (batch_id,),
    )
    row = cur.fetchone() or {}
    return {
        "completed_cards": int(_one_value(row, "completed", 0) or 0),
        "with_title_address": int(_one_value(row, "with_title_address", 1) or 0),
        "with_rating_or_reviews": int(_one_value(row, "with_rating_or_reviews", 2) or 0),
        "with_products": int(_one_value(row, "with_products", 3) or 0),
        "valid_strict": int(_one_value(row, "valid_strict", 4) or 0),
    }


def _load_latency(cur, batch_id: str) -> Dict[str, Any]:
    cur.execute(
        """
        WITH done AS (
            SELECT created_at, updated_at
            FROM parsequeue
            WHERE batch_id = %s
              AND status = 'completed'
              AND created_at IS NOT NULL
              AND updated_at IS NOT NULL
        )
        SELECT
            COUNT(*) AS completed_with_timing,
            ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (updated_at - created_at))) / 60.0)::numeric, 2) AS p50_minutes,
            ROUND((percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (updated_at - created_at))) / 60.0)::numeric, 2) AS p95_minutes
        FROM done
        """,
        (batch_id,),
    )
    row = cur.fetchone() or {}
    return {
        "completed_with_timing": int(_one_value(row, "completed_with_timing", 0) or 0),
        "p50_minutes": float(_one_value(row, "p50_minutes", 1) or 0.0),
        "p95_minutes": float(_one_value(row, "p95_minutes", 2) or 0.0),
    }


def _load_failure_taxonomy(cur, batch_id: str) -> Dict[str, int]:
    cur.execute(
        """
        SELECT status, error_message
        FROM parsequeue
        WHERE batch_id = %s
          AND (
                error_message IS NOT NULL
             OR status IN ('captcha', 'error', 'paused')
          )
        """,
        (batch_id,),
    )
    counter: Counter[str] = Counter()
    for row in cur.fetchall() or []:
        status = _one_value(row, "status", 0)
        error_message = _one_value(row, "error_message", 1)
        reason = classify_failure_reason(status, error_message)
        counter[reason] += 1
    return dict(counter.most_common())


def _pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((float(num) / float(den)) * 100.0, 2)


def _build_markdown(snapshot: Dict[str, Any]) -> str:
    status_counts = snapshot["status_counts"]
    total = snapshot["batch_total"]
    valid = snapshot["valid"]
    target = snapshot["target"]
    latency = snapshot["latency"]
    taxonomy = snapshot["failure_taxonomy"]

    lines = []
    lines.append("# Parsing Baseline Snapshot")
    lines.append("")
    lines.append(f"- Generated at: `{snapshot['generated_at']}`")
    lines.append(f"- Batch ID: `{snapshot['batch_id']}`")
    lines.append("")
    lines.append("## Status Counts")
    lines.append("")
    lines.append("| Status | Count | Rate |")
    lines.append("|---|---:|---:|")
    for status in sorted(status_counts.keys()):
        count = int(status_counts.get(status, 0))
        lines.append(f"| {status} | {count} | {_pct(count, total)}% |")
    lines.append(f"| total | {total} | 100% |")
    lines.append("")
    lines.append("## Valid Strict")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| completed_cards | {valid['completed_cards']} |")
    lines.append(f"| with_title_address | {valid['with_title_address']} |")
    lines.append(f"| with_rating_or_reviews | {valid['with_rating_or_reviews']} |")
    lines.append(f"| with_products | {valid['with_products']} |")
    lines.append(f"| valid_strict | {valid['valid_strict']} |")
    lines.append(f"| valid_strict_rate_of_batch | {_pct(valid['valid_strict'], total)}% |")
    lines.append("")
    lines.append("## Target vs Actual")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| target_rate | {target['target_rate_pct']}% |")
    lines.append(f"| target_valid_count | {target['target_valid_count']} |")
    lines.append(f"| actual_valid_count | {target['actual_valid_count']} |")
    lines.append(f"| gap_to_target | {target['gap_to_target']} |")
    lines.append(f"| progress_to_target | {target['progress_to_target_pct']}% |")
    lines.append("")
    lines.append("## Latency")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| completed_with_timing | {latency['completed_with_timing']} |")
    lines.append(f"| p50_minutes | {latency['p50_minutes']} |")
    lines.append(f"| p95_minutes | {latency['p95_minutes']} |")
    lines.append("")
    lines.append("## Failure Taxonomy")
    lines.append("")
    lines.append("| Reason | Count |")
    lines.append("|---|---:|")
    if taxonomy:
        for reason, count in taxonomy.items():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| none | 0 |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True, help="parsequeue.batch_id")
    parser.add_argument("--target-rate", type=float, default=0.96, help="Target valid success rate")
    parser.add_argument("--out", default="", help="Optional output markdown file path")
    parser.add_argument("--json-out", default="", help="Optional output JSON file path")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        status_counts = _load_status_counts(cur, args.batch_id)
        total = int(sum(status_counts.values()))
        valid = _load_valid_strict(cur, args.batch_id)
        latency = _load_latency(cur, args.batch_id)
        taxonomy = _load_failure_taxonomy(cur, args.batch_id)

        target_valid_count = int(math.ceil(total * float(args.target_rate))) if total > 0 else 0
        actual_valid_count = int(valid.get("valid_strict", 0))
        gap_to_target = max(target_valid_count - actual_valid_count, 0)
        progress_to_target_pct = _pct(actual_valid_count, target_valid_count) if target_valid_count > 0 else 0.0

        snapshot: Dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "batch_id": args.batch_id,
            "batch_total": total,
            "status_counts": status_counts,
            "valid": valid,
            "target": {
                "target_rate_pct": round(float(args.target_rate) * 100.0, 2),
                "target_valid_count": target_valid_count,
                "actual_valid_count": actual_valid_count,
                "gap_to_target": gap_to_target,
                "progress_to_target_pct": progress_to_target_pct,
            },
            "latency": latency,
            "failure_taxonomy": taxonomy,
        }

        markdown = _build_markdown(snapshot)
        print(markdown)

        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(markdown)
                fh.write("\n")
            print(f"\n[ok] markdown saved: {args.out}")

        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            print(f"[ok] json saved: {args.json_out}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
