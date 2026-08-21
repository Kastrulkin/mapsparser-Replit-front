#!/usr/bin/env python3
"""Build a read-only current-rule review for LocalOS Party 10."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from services.outreach_campaign_service import DEFAULT_SEQUENCE, build_preview
from services.outreach_template_service import TEMPLATE_LIBRARY_VERSION, select_outreach_template


SOURCE = Path("/app/debug_data/localos-party10-selection-20260813.json")
OUTPUT = Path("/app/debug_data/localos-party10-review-v1-20260813.json")


def canonical_sha(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def template_sequence(preview: dict[str, Any]) -> list[dict[str, Any]]:
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
            "signal",
            "crm_content",
            "average_ticket",
            "content_operations",
            "reviews_service",
            "integrated_system",
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


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    targets = list(source.get("selected") or [])
    connection = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    connection.set_session(readonly=True, autocommit=False)
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION READ ONLY")
    results: list[dict[str, Any]] = []
    revise: list[dict[str, Any]] = []
    try:
        for target in targets:
            workstream_id = str(target["workstream_id"])
            try:
                availability = build_preview(
                    cursor,
                    workstream_id,
                    sender_mode="localos",
                    generate_ai=False,
                    manual_reviewer_role="superadmin",
                )
                sequence = template_sequence(availability)
                if not sequence:
                    revise.append({
                        "name": target["name"],
                        "lead_id": target["lead_id"],
                        "workstream_id": workstream_id,
                        "reason": "NO_EVIDENCE_BOUND_TEMPLATE_SEQUENCE",
                    })
                    continue
                preview = build_preview(
                    cursor,
                    workstream_id,
                    sequence=sequence,
                    sender_mode="localos",
                    generate_ai=False,
                    manual_reviewer_role="superadmin",
                )
                touches = list(preview.get("touches") or [])
                failed = [
                    {
                        "sequence_index": touch.get("sequence_index"),
                        "channel": touch.get("channel"),
                        "reason_codes": (touch.get("quality_gate") or {}).get("reason_codes") or [],
                        "blocking_reasons": (touch.get("quality_gate") or {}).get("blocking_reasons") or [],
                    }
                    for touch in touches
                    if not bool((touch.get("quality_gate") or {}).get("passed"))
                ]
                if not touches or failed:
                    revise.append({
                        "name": target["name"],
                        "lead_id": target["lead_id"],
                        "workstream_id": workstream_id,
                        "reason": "QUALITY_GATE_FAILED" if failed else "NO_TOUCHES",
                        "failed_touches": failed,
                    })
                    continue
                results.append({
                    "party": "Партия 10",
                    "name": target["name"],
                    "segment": target.get("segment"),
                    "lead_id": target["lead_id"],
                    "workstream_id": workstream_id,
                    "source_url": target.get("source_url"),
                    "audit_slug": target.get("audit_slug") if target.get("audit_active") else None,
                    "classification": "content_ready",
                    "touch_count": len(touches),
                    "channels": [touch.get("channel") for touch in touches],
                    "touches": touches,
                })
            except Exception as error:
                revise.append({
                    "name": target["name"],
                    "lead_id": target["lead_id"],
                    "workstream_id": workstream_id,
                    "reason": "BUILD_PREVIEW_ERROR",
                    "error": f"{type(error).__name__}: {error}",
                })
    finally:
        connection.rollback()
        connection.close()

    payload = {
        "schema_version": "localos_party10_review_v1",
        "party": "Партия 10",
        "template_library_version": TEMPLATE_LIBRARY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection_sha256": source.get("canonical_sha256"),
        "selected_count": len(targets),
        "content_ready_count": len(results),
        "touch_count": sum(item["touch_count"] for item in results),
        "quality_passed_count": sum(
            bool((touch.get("quality_gate") or {}).get("passed"))
            for item in results for touch in item["touches"]
        ),
        "approved": 0,
        "queued": 0,
        "sent": 0,
        "database_mutations": 0,
        "results": results,
        "revise": revise,
    }
    payload["canonical_sha256"] = canonical_sha(results)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "selected": len(targets),
        "content_ready": len(results),
        "touches": payload["touch_count"],
        "quality_passed": payload["quality_passed_count"],
        "revise": len(revise),
        "canonical_sha256": payload["canonical_sha256"],
        "database_mutations": 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
