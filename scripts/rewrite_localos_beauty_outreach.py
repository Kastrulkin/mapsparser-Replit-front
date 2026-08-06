#!/usr/bin/env python3
"""Preview or version the reviewed LocalOS beauty outreach cohort.

Dry-run is the default. ``--apply`` creates draft campaigns only, leaves every
touch in ``draft`` and supersedes the previous draft only after the replacement
has been saved successfully. It never approves, queues or dispatches messages.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (str(REPO_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.outreach_campaign_service import (  # noqa: E402
    DEFAULT_SEQUENCE,
    build_preview,
    persist_preview,
)


RULES_VERSION = "localos_beauty_outreach_v3"
TARGET_WORKSTREAMS = (
    "7e3e0f39-3e00-41c6-9343-b5ff054b3103",
    "2fc0e399-42c9-4cff-935e-1b31180116f1",
    "45691317-df58-4f29-a03d-8aa1baafafdf",
    "c9fe2f36-dab0-4008-92b7-225ebe29aae3",
    "28dc573a-7882-4d2e-8a03-58ccba1c2278",
    "890efa74-5725-4420-9c49-3dbfc93f8012",
    "056ad120-667f-4b62-b257-50f0005a9f60",
    "cbb4c048-7ece-43a3-a5bf-cc489c2e02f5",
    "5935fc3f-064f-46ed-bbdf-bcebade9ac84",
    "f4e9cb5e-e8da-4c0f-aac0-d58bc930cf45",
    "e4ef90f7-20a1-420e-ac4f-66640cc7c40c",
)
EXCLUDED_WORKSTREAMS = {
    "28dc573a-7882-4d2e-8a03-58ccba1c2278": "strong_sales_signal_offer_strategy_pending",
}


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _superadmin_id(cursor: Any) -> str:
    cursor.execute(
        """
        SELECT id FROM users
        WHERE COALESCE(is_superadmin,FALSE)=TRUE AND is_active=TRUE
        ORDER BY updated_at DESC NULLS LAST, created_at ASC LIMIT 1
        """
    )
    row = cursor.fetchone()
    if not row:
        raise RuntimeError("active_superadmin_not_found")
    return str(row["id"])


def _lead_name(cursor: Any, workstream_id: str) -> str:
    cursor.execute(
        """
        SELECT l.name
        FROM lead_workstreams ws
        JOIN prospectingleads l ON l.id=ws.lead_id
        WHERE ws.id=%s AND ws.workstream_type='localos_sales'
        """,
        (workstream_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise LookupError("localos_sales_workstream_not_found")
    return str(row["name"] or "")


def _latest_draft_id(cursor: Any, workstream_id: str) -> str | None:
    cursor.execute(
        """
        SELECT id FROM outreach_campaigns
        WHERE workstream_id=%s AND status='draft'
        ORDER BY version DESC, created_at DESC LIMIT 1
        """,
        (workstream_id,),
    )
    row = cursor.fetchone()
    return str(row["id"]) if row else None


def _start_at() -> datetime:
    now = datetime.now(timezone.utc)
    return (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)


def _preview_summary(preview: dict[str, Any]) -> dict[str, Any]:
    touches = preview.get("touches") or []
    return {
        "status": preview.get("status"),
        "decision": (preview.get("decision") or {}).get("action"),
        "touch_count": len(touches),
        "channels": [touch.get("channel") for touch in touches],
        "angles": [touch.get("angle") for touch in touches],
        "scores": [
            (touch.get("quality_gate") or {}).get("score")
            or (touch.get("quality_gate") or {}).get("total_score")
            for touch in touches
        ],
        "all_quality_passed": bool(touches) and all(
            bool((touch.get("quality_gate") or {}).get("passed")) for touch in touches
        ),
        "messages": [
            {
                "channel": touch.get("channel"),
                "subject": touch.get("subject"),
                "text": touch.get("text"),
                "case_key": (touch.get("strategy") or {}).get("case_key"),
            }
            for touch in touches
        ],
    }


def _available_sequence(channel_availability: dict[str, Any]) -> list[dict[str, Any]]:
    available_steps = [
        (channel, day)
        for channel, day, _angle in DEFAULT_SEQUENCE
        if (channel_availability.get(channel) or {}).get("status") in {"ready", "manual"}
    ]
    reviewed_angles = (
        "signal",
        "content_operations",
        "average_ticket",
        "reviews_service",
        "integrated_system",
        "founder_origin",
    )
    angles = reviewed_angles[:len(available_steps)]
    return [
        {
            "channel": channel,
            "day_offset": day,
            "angle": angles[index],
            "skip_if_unavailable": True,
        }
        for index, (channel, day) in enumerate(available_steps)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--workstream-id", action="append")
    args = parser.parse_args()
    workstreams = tuple(args.workstream_id or TARGET_WORKSTREAMS)

    conn = _connect()
    results: list[dict[str, Any]] = []
    try:
        cursor = conn.cursor()
        user_id = _superadmin_id(cursor)
        for index, workstream_id in enumerate(workstreams):
            if workstream_id in EXCLUDED_WORKSTREAMS:
                results.append({
                    "workstream_id": workstream_id,
                    "lead": _lead_name(cursor, workstream_id),
                    "skipped": True,
                    "reason": EXCLUDED_WORKSTREAMS[workstream_id],
                })
                continue
            savepoint = f"beauty_outreach_{index}"
            cursor.execute(f"SAVEPOINT {savepoint}")
            result: dict[str, Any] = {"workstream_id": workstream_id}
            try:
                result["lead"] = _lead_name(cursor, workstream_id)
                previous_draft_id = _latest_draft_id(cursor, workstream_id)
                availability_preview = build_preview(
                    cursor,
                    workstream_id,
                    start_at=_start_at(),
                    sender_mode="localos",
                    generate_ai=False,
                    manual_reviewer_role="superadmin",
                )
                sequence = _available_sequence(
                    availability_preview.get("channel_availability") or {}
                )
                preview = build_preview(
                    cursor,
                    workstream_id,
                    sequence=sequence,
                    start_at=_start_at(),
                    sender_mode="localos",
                    generate_ai=False,
                    manual_reviewer_role="superadmin",
                )
                result["preview"] = _preview_summary(preview)
                if not result["preview"]["all_quality_passed"]:
                    raise ValueError("quality_gate_failed")
                if args.apply:
                    saved = persist_preview(cursor, preview, user_id=user_id)
                    if previous_draft_id and previous_draft_id != saved["id"]:
                        cursor.execute(
                            """
                            UPDATE outreach_campaigns
                            SET status='cancelled', stop_reason=%s, updated_at=NOW()
                            WHERE id=%s AND status='draft'
                            """,
                            (f"superseded_by_{RULES_VERSION}", previous_draft_id),
                        )
                    result["saved"] = saved
                cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception as exc:
                cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                result["error"] = str(exc)
            results.append(result)
        if args.apply and not any(item.get("error") for item in results):
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    print(json.dumps({
        "dry_run": not args.apply,
        "rules_version": RULES_VERSION,
        "requested": len(workstreams),
        "ready": sum(bool(item.get("preview")) and not item.get("error") for item in results),
        "skipped": sum(bool(item.get("skipped")) for item in results),
        "errors": sum(bool(item.get("error")) for item in results),
        "results": results,
        "approved": 0,
        "queued": 0,
        "sent": 0,
    }, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
