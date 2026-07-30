from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json


def record_lead_preparation_step(
    cursor,
    *,
    workstream_id: str,
    step_code: str,
    label: str,
    status: str = "completed",
    completed_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    message_brief_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a user-visible preparation step in the latest research snapshot."""

    timestamp = completed_at or datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        SELECT id, message_brief_json
        FROM lead_workstream_research
        WHERE workstream_id = %s
        ORDER BY researched_at DESC, created_at DESC
        LIMIT 1
        FOR UPDATE
        """,
        (workstream_id,),
    )
    research = cursor.fetchone()
    stored_brief = research.get("message_brief_json") if research and hasattr(research, "get") else None
    message_brief = dict(stored_brief or {})
    message_brief.update(message_brief_updates or {})
    preparation_steps = dict(message_brief.get("preparation_steps") or {})
    step = {
        "status": status,
        "label": label,
        "completed_at": timestamp,
    }
    if metadata:
        step["metadata"] = metadata
    preparation_steps[step_code] = step
    message_brief["preparation_steps"] = preparation_steps

    if research:
        research_id = research.get("id") if hasattr(research, "get") else research[0]
        cursor.execute(
            """
            UPDATE lead_workstream_research
            SET message_brief_json = %s
            WHERE id = %s
            """,
            (Json(message_brief), research_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO lead_workstream_research (
                id, workstream_id, score, qualification_stage, signal_label,
                score_breakdown, why_now, signals_json, sources_json,
                contact_evidence_json, limitations_json, message_brief_json,
                message_readiness_json, report_hash, researched_at, created_at
            ) VALUES (
                %s, %s, 15, 'potential_fit', 'fit_only',
                '{}'::jsonb, NULL, '[]'::jsonb, '[]'::jsonb,
                '[]'::jsonb, '[]'::jsonb, %s,
                '{}'::jsonb, %s, NOW(), NOW()
            )
            """,
            (
                str(uuid.uuid4()),
                workstream_id,
                Json(message_brief),
                f"preparation-progress:{workstream_id}",
            ),
        )
    return step
