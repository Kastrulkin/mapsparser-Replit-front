#!/usr/bin/env python3
"""Create reviewed draft outreach versions for approved signal cohorts.

Dry-run is the default. ``--apply`` persists draft campaigns only. It never
approves, queues or sends touches. Existing drafts are superseded only after a
replacement version has been saved successfully.
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


RULES_VERSION = "localos_signal_cohorts_v1"
COHORTS = {
    "price_gap": {
        "signal_combo": "active_social_with_service_price_gap",
        "canary": ("35a54e63-7652-41ae-a9e0-f6d1bed1ec08",),
        "expansion": (
            "c9fe2f36-dab0-4008-92b7-225ebe29aae3",
            "71f07c10-d6c9-435a-a633-7838dcc1349f",
            "801a632f-0ce1-4f5b-9b9c-fa970f590c53",
            "2dc27fbb-2799-4e21-9857-3378a3a400a0",
            "5df12b1b-36d1-4f0e-823d-f47e687a1a42",
            "ccdccd57-3f5f-4e0a-baa3-6052934f50d8",
            "71c9dc31-2fa8-4b1f-9a82-c654e219e9f4",
            "b1fee804-a1fd-4d5d-a3e5-4d13586bce66",
            "3719ada0-0851-4da3-9cbc-5f54f4e591ed",
            "03768025-0ea4-4679-b4f4-fbf693a1ffc9",
        ),
        "angles": (
            "signal", "founder_origin", "average_ticket",
            "content_operations", "reviews_service", "integrated_system",
        ),
    },
    "negative_review": {
        "signal_combo": "active_social_with_unanswered_negative_review",
        "canary": ("60cd55a5-e097-4e02-bd7e-e2a979044043",),
        "expansion": (
            "15184232-e977-4859-8c51-e840ac25584c",
            "dfa16bde-b632-49f1-9e41-7e23c9ded4ef",
            "20bb72bf-394a-4e67-a0eb-8b45c2fa3417",
            "bab95257-4a1a-4ec4-af3a-184979696fe5",
            "13347e2b-d215-4e14-9aea-a39f7172b1b5",
            "ec628f7f-e6f9-4b19-b211-a173323d6815",
            "4caf5e90-a672-45f5-b013-d66bc09a07a1",
            "46e6296a-2cf2-45ab-8fcc-e5921bdcb4ee",
            "213e943c-b7c5-4987-ba28-5d57524302f6",
        ),
        "angles": (
            "signal", "founder_origin", "content_operations",
            "average_ticket", "integrated_system", "audit_step",
        ),
    },
    "new_service": {
        "signal_combo": "recent_new_service_announcement",
        "canary": ("f967c54a-54c0-4ae2-b922-2aa766b777f8",),
        "expansion": (),
        "angles": (
            "signal", "founder_origin", "proof",
            "content_operations", "integrated_system", "audit_step",
        ),
    },
    "event": {
        "signal_combo": "recent_event_announcement",
        "canary": ("647fbfe4-62b2-4ab6-b692-43b0d3a68052",),
        "expansion": (),
        "angles": (
            "signal", "founder_origin", "proof",
            "content_operations", "integrated_system", "audit_step",
        ),
    },
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


def _lead(cursor: Any, workstream_id: str) -> dict[str, str]:
    cursor.execute(
        """
        SELECT l.id, l.name
        FROM lead_workstreams ws
        JOIN prospectingleads l ON l.id=ws.lead_id
        WHERE ws.id=%s AND ws.workstream_type='localos_sales'
        """,
        (workstream_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise LookupError("localos_sales_workstream_not_found")
    return {"id": str(row["id"]), "name": str(row["name"] or "")}


def _start_at() -> datetime:
    now = datetime.now(timezone.utc)
    return (now + timedelta(days=2)).replace(hour=7, minute=0, second=0, microsecond=0)


def _sequence(availability: dict[str, Any], angles: tuple[str, ...]) -> list[dict[str, Any]]:
    available_steps = [
        (channel, day)
        for channel, day, _angle in DEFAULT_SEQUENCE
        if (availability.get(channel) or {}).get("status") in {"ready", "manual"}
    ]
    return [
        {
            "channel": channel,
            "day_offset": day,
            "angle": angles[index],
            "skip_if_unavailable": True,
        }
        for index, (channel, day) in enumerate(available_steps[:len(angles)])
    ]


def _summary(preview: dict[str, Any]) -> dict[str, Any]:
    candidates = preview.get("personalization_candidates") or []
    touches = preview.get("touches") or []
    return {
        "status": preview.get("status"),
        "decision": (preview.get("decision") or {}).get("action"),
        "signal_combo": candidates[0].get("signal_combo") if candidates else None,
        "touch_count": len(touches),
        "channels": [touch.get("channel") for touch in touches],
        "angles": [touch.get("angle") for touch in touches],
        "scores": [(touch.get("quality_gate") or {}).get("score") for touch in touches],
        "passed": bool(touches) and all(
            (touch.get("quality_gate") or {}).get("passed") is True
            for touch in touches
        ),
        "messages": [
            {
                "channel": touch.get("channel"),
                "subject": touch.get("subject"),
                "text": touch.get("text"),
            }
            for touch in touches
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=tuple(COHORTS), required=True)
    parser.add_argument("--stage", choices=("canary", "expansion"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    definition = COHORTS[args.cohort]
    workstreams = definition[args.stage]
    conn = _connect()
    results: list[dict[str, Any]] = []
    try:
        cursor = conn.cursor()
        user_id = _superadmin_id(cursor)
        for index, workstream_id in enumerate(workstreams):
            savepoint = f"signal_cohort_{index}"
            cursor.execute(f"SAVEPOINT {savepoint}")
            result: dict[str, Any] = {"workstream_id": workstream_id}
            try:
                lead = _lead(cursor, workstream_id)
                result.update({"lead_id": lead["id"], "lead": lead["name"]})
                first_preview = build_preview(
                    cursor,
                    workstream_id,
                    start_at=_start_at(),
                    sender_mode="localos",
                    generate_ai=False,
                    manual_reviewer_role="superadmin",
                )
                sequence = _sequence(
                    first_preview.get("channel_availability") or {},
                    definition["angles"],
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
                result["preview"] = _summary(preview)
                if result["preview"]["signal_combo"] != definition["signal_combo"]:
                    raise ValueError(
                        "unexpected_primary_signal:"
                        f"{result['preview']['signal_combo']}"
                    )
                if not result["preview"]["passed"]:
                    raise ValueError("quality_gate_failed")
                if args.apply:
                    saved = persist_preview(cursor, preview, user_id=user_id)
                    cursor.execute(
                        """
                        UPDATE outreach_campaigns
                        SET status='cancelled', stop_reason=%s, updated_at=NOW()
                        WHERE workstream_id=%s AND status='draft' AND id<>%s
                        """,
                        (f"superseded_by_{RULES_VERSION}", workstream_id, saved["id"]),
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
        "cohort": args.cohort,
        "stage": args.stage,
        "rules_version": RULES_VERSION,
        "requested": len(workstreams),
        "ready": sum(bool(item.get("preview")) and not item.get("error") for item in results),
        "errors": sum(bool(item.get("error")) for item in results),
        "approved": 0,
        "queued": 0,
        "sent": 0,
        "results": results,
    }, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
