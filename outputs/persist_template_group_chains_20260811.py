"""Persist the reviewed 50-chain pack as draft-only campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from services.outreach_campaign_service import DEFAULT_SEQUENCE, build_preview, persist_preview
from services.outreach_template_service import select_outreach_template


SOURCE = Path("/app/debug_data/localos-template-review-v12-20260811.json")
BACKUP_DIR = Path("/app/debug_data/template-group-chain-backup-v12-20260811")
RULES_VERSION = "template_owner_pain_v12_20260811"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _actor_id(cursor: Any) -> str:
    cursor.execute(
        """SELECT id FROM users
           WHERE COALESCE(is_superadmin,FALSE)=TRUE AND is_active=TRUE
           ORDER BY updated_at DESC NULLS LAST LIMIT 1"""
    )
    row = cursor.fetchone()
    if not row:
        raise RuntimeError("active_superadmin_not_found")
    return str(row["id"])


def _template_sequence(preview: dict[str, Any]) -> list[dict[str, Any]]:
    availability = preview.get("channel_availability") or {}
    route_slots = [
        (channel, day_offset)
        for channel, day_offset, _default_angle in DEFAULT_SEQUENCE
        if (availability.get(channel) or {}).get("status") in {"ready", "manual"}
    ]
    supported: list[dict[str, Any]] = []
    used_template_keys: list[str] = []
    used_pain_keys: list[str] = []
    for candidate in preview.get("personalization_candidates") or []:
        for angle in (
            "signal", "crm_content", "average_ticket", "content_operations",
            "reviews_service", "integrated_system",
        ):
            selection = select_outreach_template(
                angle,
                candidate,
                used_template_keys=used_template_keys,
                used_pain_keys=used_pain_keys,
            )
            if selection.get("status") != "selected":
                continue
            supported.append(
                {
                    "angle": angle,
                    "personalization_candidate_id": candidate.get("id"),
                    "template_key": selection.get("key"),
                }
            )
            used_template_keys.append(str(selection.get("key")))
            used_pain_keys.append(str(selection.get("pain_key")))
    return [
        {
            "channel": channel,
            "day_offset": day_offset,
            "angle": supported[index]["angle"],
            "personalization_candidate_id": supported[index]["personalization_candidate_id"],
            "skip_if_unavailable": True,
        }
        for index, (channel, day_offset) in enumerate(route_slots[: len(supported)])
    ]


def _rows(cursor: Any, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    os.environ["OUTREACH_ROOM_SYNC_ENABLED"] = "false"

    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    target_items = [
        item for item in source["results"] if item["classification"] == "content_ready"
    ]
    if len(target_items) != 50:
        raise RuntimeError(f"expected_50_ready_got_{len(target_items)}")
    target_by_workstream = {str(item["workstream_id"]): item for item in target_items}
    if len(target_by_workstream) != 50:
        raise RuntimeError("duplicate_workstreams")
    workstream_ids = list(target_by_workstream)
    lead_ids = [str(item["lead_id"]) for item in target_items]

    connection = psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
    )
    connection.autocommit = False
    cursor = connection.cursor()
    try:
        workstreams = _rows(
            cursor,
            "SELECT * FROM lead_workstreams WHERE id=ANY(%s::uuid[]) ORDER BY id FOR UPDATE",
            (workstream_ids,),
        )
        campaigns = _rows(
            cursor,
            "SELECT * FROM outreach_campaigns WHERE workstream_id=ANY(%s::uuid[]) ORDER BY workstream_id,version FOR UPDATE",
            (workstream_ids,),
        )
        campaign_ids = [str(row["id"]) for row in campaigns]
        touches = _rows(
            cursor,
            "SELECT * FROM outreach_campaign_touches WHERE campaign_id=ANY(%s::uuid[]) ORDER BY campaign_id,sequence_index FOR UPDATE",
            (campaign_ids,),
        ) if campaign_ids else []
        research = _rows(
            cursor,
            "SELECT * FROM lead_workstream_research WHERE workstream_id=ANY(%s::uuid[]) ORDER BY workstream_id,created_at",
            (workstream_ids,),
        )
        queue = _rows(
            cursor,
            "SELECT * FROM outreachsendqueue WHERE lead_id=ANY(%s) ORDER BY lead_id,created_at FOR UPDATE",
            (lead_ids,),
        )
        inbound = _rows(
            cursor,
            "SELECT id,lead_id,is_human,created_at FROM outreach_inbound_events WHERE lead_id=ANY(%s) AND COALESCE(is_human,FALSE)=TRUE",
            (lead_ids,),
        )
        suppressions = _rows(
            cursor,
            "SELECT id,lead_id,expires_at FROM outreach_suppressions WHERE lead_id=ANY(%s) AND (expires_at IS NULL OR expires_at>NOW())",
            (lead_ids,),
        )
        non_draft = [row for row in campaigns if row.get("status") not in {"draft", "cancelled"}]
        unsafe_queue = [
            row for row in queue
            if row.get("sent_at") is not None
            or row.get("delivery_status") in {"sent", "delivered", "sending", "queued", "retry"}
        ]
        if len(workstreams) != 50:
            raise RuntimeError(f"workstream_count_{len(workstreams)}")
        if inbound or suppressions or non_draft or unsafe_queue:
            raise RuntimeError(
                "safety_blocker:"
                + json.dumps(
                    {
                        "inbound": len(inbound),
                        "suppressions": len(suppressions),
                        "non_draft": len(non_draft),
                        "unsafe_queue": len(unsafe_queue),
                    },
                    ensure_ascii=False,
                )
            )

        backup = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "apply" if args.apply else "dry_run",
            "rules_version": RULES_VERSION,
            "source_sha256": source.get("canonical_sha256"),
            "workstreams": workstreams,
            "campaigns": campaigns,
            "touches": touches,
            "research": research,
            "queue": queue,
        }
        backup_bytes = _json_bytes(backup)
        backup_sha = hashlib.sha256(backup_bytes).hexdigest()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / (
            "prewrite.json" if args.apply else "dry-run-prewrite.json"
        )
        backup_path.write_bytes(backup_bytes)
        backup_path.with_suffix(".sha256").write_text(
            f"{backup_sha}  {backup_path.name}\n", encoding="utf-8"
        )

        actor = _actor_id(cursor)
        saved_items = []
        for workstream_id, expected in target_by_workstream.items():
            availability = build_preview(
                cursor,
                workstream_id,
                sender_mode="localos",
                generate_ai=False,
                manual_reviewer_role="superadmin",
            )
            sequence = _template_sequence(availability)
            preview = build_preview(
                cursor,
                workstream_id,
                sequence=sequence,
                sender_mode="localos",
                generate_ai=False,
                manual_reviewer_role="superadmin",
            )
            actual_touches = [
                (touch.get("channel"), touch.get("subject"), touch.get("text"))
                for touch in preview.get("touches") or []
            ]
            expected_touches = [
                (touch.get("channel"), touch.get("subject"), touch.get("text"))
                for touch in expected.get("touches") or []
            ]
            if actual_touches != expected_touches:
                raise RuntimeError(f"review_bytes_changed:{expected['name']}")
            if not actual_touches or not all(
                bool((touch.get("quality_gate") or {}).get("passed"))
                for touch in preview.get("touches") or []
            ):
                raise RuntimeError(f"quality_gate_failed:{expected['name']}")
            saved = persist_preview(cursor, preview, user_id=actor)
            cursor.execute(
                """UPDATE outreach_campaigns
                   SET status='cancelled', stop_reason=%s, updated_at=NOW()
                   WHERE workstream_id=%s AND status='draft' AND id<>%s""",
                (f"superseded_by_{RULES_VERSION}", workstream_id, saved["id"]),
            )
            saved_items.append(
                {
                    "name": expected["name"],
                    "lead_id": expected["lead_id"],
                    "workstream_id": workstream_id,
                    "campaign_id": saved["id"],
                    "version": saved["version"],
                    "touch_count": len(actual_touches),
                    "channels": [touch[0] for touch in actual_touches],
                }
            )

        if args.apply:
            connection.commit()
            status = "APPLIED"
        else:
            connection.rollback()
            status = "DRY_RUN_ROLLED_BACK"
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    result = {
        "status": status,
        "rules_version": RULES_VERSION,
        "chains": len(saved_items),
        "touches": sum(item["touch_count"] for item in saved_items),
        "approved": 0,
        "queued": 0,
        "sent": 0,
        "backup_path": str(backup_path),
        "backup_sha256": backup_sha,
        "items": saved_items,
    }
    result["canonical_sha256"] = hashlib.sha256(_json_bytes(saved_items)).hexdigest()
    result_path = BACKUP_DIR / (
        "apply-result.json" if args.apply else "dry-run-result.json"
    )
    result_path.write_bytes(_json_bytes(result))
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "items"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
