#!/usr/bin/env python3
"""Build the current-rule review artifact for LocalOS Party 2.

Read-only production access. No campaign persistence, approval, queue, or send.
"""

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
from services.outreach_template_service import (
    TEMPLATE_LIBRARY_VERSION,
    select_outreach_template,
)


SOURCE = Path("/app/debug_data/localos-party2-selection-20260811.json")
OUTPUT = Path("/app/debug_data/localos-party2-review-v1-20260811.json")


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


def review_candidate(cursor: Any, target: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
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
            return None, {"name": target["name"], "workstream_id": workstream_id, "reason": "NO_SUPPORTED_SEQUENCE"}
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
            return None, {
                "name": target["name"],
                "address": (target.get("current") or {}).get("address"),
                "workstream_id": workstream_id,
                "reason": "QUALITY_GATE_FAILED" if failed else "NO_TOUCHES",
                "failed_touches": failed,
            }
        return (
            {
                "party": "Партия 2",
                "name": target["name"],
                "lead_id": target["lead_id"],
                "workstream_id": workstream_id,
                "prior_rank": target.get("rank"),
                "pipeline_status": (target.get("current") or {}).get("pipeline_status"),
                "workstream_status": (target.get("current") or {}).get("workstream_status"),
                "lifecycle_status": (target.get("current") or {}).get("lifecycle_status"),
                "research_score": (target.get("current") or {}).get("score"),
                "researched_at": (target.get("current") or {}).get("researched_at"),
                "classification": "content_ready",
                "preview_status": preview.get("status"),
                "touch_count": len(touches),
                "channels": [touch.get("channel") for touch in touches],
                "touches": touches,
            },
            None,
        )
    except Exception as error:
        return None, {
            "name": target["name"],
            "workstream_id": workstream_id,
            "reason": "BUILD_PREVIEW_ERROR",
            "error": f"{type(error).__name__}: {error}",
        }


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    # Replacement candidates must satisfy the same recipient-deduplication
    # contract as the initial 50. Rows skipped by selection for an overlapping
    # verified route are not safe fallbacks.
    candidates = list(source["selected"]) + [
        item
        for item in (source.get("eligible_not_selected") or [])
        if not item.get("selection_skip_reason")
    ]
    connection = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    connection.set_session(readonly=True, autocommit=False)
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION READ ONLY")
    results: list[dict[str, Any]] = []
    revise: list[dict[str, Any]] = []
    used_route_keys: set[str] = set()
    try:
        for target in candidates:
            route_keys = set(target.get("verified_route_keys") or [])
            if route_keys.intersection(used_route_keys):
                revise.append(
                    {
                        "name": target["name"],
                        "lead_id": target["lead_id"],
                        "prior_rank": target.get("rank"),
                        "reason": "PARTY2_RECIPIENT_ROUTE_OVERLAP",
                    }
                )
                continue
            result, failure = review_candidate(cursor, target)
            if result is not None and len(results) < 50:
                results.append(result)
                used_route_keys.update(route_keys)
            elif failure is not None:
                revise.append({**failure, "lead_id": target["lead_id"], "prior_rank": target.get("rank")})
            if len(results) == 50:
                break
    finally:
        connection.rollback()
        connection.close()
    if len(results) != 50:
        raise RuntimeError(f"expected_50_content_ready_got_{len(results)}")
    payload = {
        "schema_version": "localos_party2_review_v1",
        "party": "Партия 2",
        "template_library_version": TEMPLATE_LIBRARY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection_sha256": source.get("canonical_sha256"),
        "content_ready_count": len(results),
        "touch_count": sum(item["touch_count"] for item in results),
        "quality_passed_count": sum(
            bool((touch.get("quality_gate") or {}).get("passed"))
            for item in results
            for touch in item["touches"]
        ),
        "approved": 0,
        "queued": 0,
        "sent": 0,
        "database_mutations": 0,
        "results": results,
        "revised_or_skipped_before_filling_50": revise,
    }
    payload["canonical_sha256"] = canonical_sha(results)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "party": payload["party"],
                "chains": payload["content_ready_count"],
                "touches": payload["touch_count"],
                "quality_passed": payload["quality_passed_count"],
                "revised_or_skipped": len(revise),
                "canonical_sha256": payload["canonical_sha256"],
                "database_mutations": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
