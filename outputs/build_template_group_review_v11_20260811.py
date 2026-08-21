"""Rebuild the reviewed 50-chain cohort with the current template library.

This script is read-only. It creates a review artifact and never persists a
campaign, approval, queue item, or send.
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


SOURCE = Path("/app/debug_data/localos-template-review-v10-20260811.json")
OUTPUT = Path("/app/debug_data/localos-template-review-v12-20260811.json")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")


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


source = json.loads(SOURCE.read_text(encoding="utf-8"))
targets = [
    item for item in source["results"] if item.get("classification") == "content_ready"
]
if len(targets) != 50:
    raise RuntimeError(f"expected_50_ready_got_{len(targets)}")

connection = psycopg2.connect(
    os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
)
connection.set_session(readonly=True, autocommit=False)
cursor = connection.cursor()
cursor.execute("SET TRANSACTION READ ONLY")

results = []
try:
    for target in targets:
        workstream_id = str(target["workstream_id"])
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
        touches = list(preview.get("touches") or [])
        if not touches or not all(
            bool((touch.get("quality_gate") or {}).get("passed")) for touch in touches
        ):
            raise RuntimeError(f"quality_gate_failed:{target['name']}")
        results.append(
            {
                "name": target["name"],
                "lead_id": target["lead_id"],
                "workstream_id": workstream_id,
                "pipeline_status": target.get("pipeline_status"),
                "workstream_status": target.get("workstream_status"),
                "lifecycle_status": target.get("lifecycle_status"),
                "classification": "content_ready",
                "preview_status": preview.get("status"),
                "touch_count": len(touches),
                "channels": [touch.get("channel") for touch in touches],
                "touches": touches,
            }
        )
finally:
    connection.rollback()
    connection.close()

payload = {
    "schema_version": "localos_template_review_v12",
    "template_library_version": TEMPLATE_LIBRARY_VERSION,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "content_ready_count": len(results),
    "approved": 0,
    "queued": 0,
    "sent": 0,
    "database_mutations": 0,
    "results": results,
}
payload["canonical_sha256"] = hashlib.sha256(_json_bytes(results)).hexdigest()
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            "status": "READ_ONLY_REVIEW_BUILT",
            "template_library_version": TEMPLATE_LIBRARY_VERSION,
            "chains": len(results),
            "touches": sum(item["touch_count"] for item in results),
            "quality_passed": sum(
                bool((touch.get("quality_gate") or {}).get("passed"))
                for item in results for touch in item["touches"]
            ),
            "canonical_sha256": payload["canonical_sha256"],
        },
        ensure_ascii=False,
        indent=2,
    )
)
