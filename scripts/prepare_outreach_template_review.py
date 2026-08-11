#!/usr/bin/env python3
"""Build a read-only review pack for safe LocalOS sales leads.

The command never persists campaigns, approves drafts, creates queue rows or
sends messages. It scans a larger deduplicated pool until it finds the requested
number of content-ready chains or exhausts the pool, then writes JSON and
Markdown review artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (str(REPO_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.outreach_campaign_service import DEFAULT_SEQUENCE, build_preview  # noqa: E402
from services.outreach_template_service import (  # noqa: E402
    TEMPLATE_LIBRARY_VERSION,
    select_outreach_template,
)


SCHEMA_VERSION = "localos_outreach_template_review_v1"
DEFAULT_POOL_LIMIT = 300


def _connect():
    connection = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=RealDictCursor,
    )
    connection.set_session(readonly=True, autocommit=False)
    return connection


def _select_candidates(cursor: Any, *, pool_limit: int) -> list[dict[str, Any]]:
    cursor.execute(
        """
        WITH latest_research AS (
            SELECT DISTINCT ON (workstream_id)
                workstream_id, id, score, signal_label, researched_at
            FROM lead_workstream_research
            ORDER BY workstream_id, researched_at DESC NULLS LAST, created_at DESC
        ), eligible AS (
            SELECT
                workstream.id AS workstream_id,
                lead.id AS lead_id,
                lead.name,
                lead.category,
                lead.rating,
                lead.reviews_count,
                lead.source_url,
                lead.pipeline_status,
                workstream.status AS workstream_status,
                workstream.lifecycle_status,
                research.score,
                research.signal_label,
                research.researched_at,
                COALESCE(
                    NULLIF(lead.external_place_id, ''),
                    NULLIF(lead.external_source_id, ''),
                    LOWER(COALESCE(lead.name, '')) || '|' || LOWER(COALESCE(lead.address, ''))
                ) AS company_key,
                COUNT(DISTINCT contact.id) FILTER (
                    WHERE contact.verification_status IN ('confirmed_source', 'verified')
                      AND (contact.stale_after IS NULL OR contact.stale_after > NOW())
                      AND contact.contact_type IN (
                          'email', 'telegram', 'vk', 'phone', 'whatsapp', 'max', 'website_form'
                      )
                ) AS verified_routes
            FROM lead_workstreams workstream
            JOIN prospectingleads lead ON lead.id = workstream.lead_id
            JOIN latest_research research ON research.workstream_id = workstream.id
            LEFT JOIN lead_contact_points contact ON contact.lead_id = lead.id
            WHERE workstream.workstream_type = 'localos_sales'
              AND workstream.last_contact_at IS NULL
              AND lead.last_contact_at IS NULL
              AND COALESCE(lead.pipeline_status, '') <> 'disqualified'
              AND COALESCE(workstream.status, '') NOT IN (
                  'contacted', 'waiting_reply', 'second_message_sent', 'replied',
                  'converted', 'closed_lost', 'sent', 'stopped'
              )
              AND COALESCE(workstream.lifecycle_status, '') NOT IN (
                  'waiting_reply', 'stopped', 'suppressed', 'cooling_down',
                  'converted', 'closed_lost'
              )
              AND COALESCE(lead.pipeline_status, '') NOT IN (
                  'contacted', 'waiting_reply', 'second_message_sent', 'replied',
                  'converted', 'closed_lost', 'sent'
              )
              AND research.researched_at >= NOW() - INTERVAL '90 days'
              AND COALESCE(research.score, 0) >= 65
              AND LOWER(COALESCE(lead.category, '') || ' ' || COALESCE(lead.name, ''))
                  ~ '(beauty|clinic|medical|барбер|клиник|космет|медиц|ногтев|парикмах|салон красот|спа-салон|эпиляц|дерматол|стоматол)'
              AND NOT EXISTS (
                  SELECT 1
                  FROM outreach_suppressions suppression
                  WHERE suppression.lead_id = lead.id
                    AND (suppression.workstream_id IS NULL OR suppression.workstream_id = workstream.id)
                    AND (suppression.expires_at IS NULL OR suppression.expires_at > NOW())
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM outreach_inbound_events inbound
                  WHERE inbound.lead_id = lead.id
                    AND COALESCE(inbound.is_human, FALSE) = TRUE
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM outreachsendqueue queue
                  WHERE queue.lead_id = lead.id
                    AND (
                        queue.sent_at IS NOT NULL
                        OR queue.delivery_status IN ('sent', 'delivered', 'sending', 'queued', 'retry')
                    )
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM outreach_campaigns campaign
                  WHERE campaign.workstream_id = workstream.id
                    AND campaign.status IN ('approved', 'active', 'paused', 'completed', 'stopped')
              )
            GROUP BY workstream.id, lead.id, research.id, research.score,
                     research.signal_label, research.researched_at
        ), deduplicated AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY company_key
                ORDER BY
                    CASE WHEN pipeline_status = 'in_progress' THEN 0 ELSE 1 END,
                    CASE WHEN lifecycle_status = 'ready_for_draft' THEN 0 ELSE 1 END,
                    score DESC,
                    researched_at DESC,
                    workstream_id
            ) AS company_rank
            FROM eligible
            WHERE verified_routes > 0
        )
        SELECT *
        FROM deduplicated
        WHERE company_rank = 1
        ORDER BY
            CASE WHEN pipeline_status = 'in_progress' THEN 0 ELSE 1 END,
            CASE WHEN lifecycle_status = 'ready_for_draft' THEN 0 ELSE 1 END,
            score DESC,
            researched_at DESC,
            name,
            workstream_id
        LIMIT %s
        """,
        (pool_limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _gate_score(touch: dict[str, Any]) -> int | None:
    gate = touch.get("quality_gate") or {}
    value = gate.get("total_score")
    if value is None:
        value = gate.get("score")
    return int(value) if isinstance(value, (int, float)) else None


def _template_sequence(preview: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a no-padding sequence with one evidence item per template."""

    availability = preview.get("channel_availability") or {}
    route_slots = [
        (channel, day_offset)
        for channel, day_offset, _default_angle in DEFAULT_SEQUENCE
        if (availability.get(channel) or {}).get("status") in {"ready", "manual"}
    ]
    if not route_slots:
        return []

    supported: list[dict[str, Any]] = []
    used_template_keys: list[str] = []
    angles = (
        "signal",
        "crm_content",
        "average_ticket",
        "content_operations",
        "reviews_service",
        "integrated_system",
    )
    for candidate in preview.get("personalization_candidates") or []:
        for angle in angles:
            selection = select_outreach_template(
                angle,
                candidate,
                used_template_keys=used_template_keys,
            )
            if selection.get("status") != "selected":
                continue
            supported.append({
                "angle": angle,
                "personalization_candidate_id": candidate.get("id"),
                "template_key": selection.get("key"),
            })
            used_template_keys.append(str(selection.get("key")))

    return [
        {
            "channel": channel,
            "day_offset": day_offset,
            "angle": supported[index]["angle"],
            "personalization_candidate_id": supported[index]["personalization_candidate_id"],
            "skip_if_unavailable": True,
        }
        for index, (channel, day_offset) in enumerate(route_slots[:len(supported)])
    ]


def _subject_is_valid(lead_name: str, touch: dict[str, Any]) -> bool:
    if touch.get("channel") != "email":
        return True
    return touch.get("subject") == f"{lead_name} | ЛокалОС | Сотрудничество"


def _summarize(candidate: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    lead_name = str(candidate.get("name") or "")
    touches = list(preview.get("touches") or [])
    all_gates_pass = bool(touches) and all(
        bool((touch.get("quality_gate") or {}).get("passed")) for touch in touches
    )
    subjects_pass = all(_subject_is_valid(lead_name, touch) for touch in touches)
    no_long_dash = all("—" not in str(touch.get("text") or "") for touch in touches)
    template_count = sum(bool(touch.get("template_key")) for touch in touches)
    content_ready = bool(
        preview.get("status") == "ready"
        and all_gates_pass
        and subjects_pass
        and no_long_dash
        and not preview.get("sequence_issues")
    )
    return {
        **candidate,
        "classification": "content_ready" if content_ready else "revise",
        "preview_status": preview.get("status"),
        "decision": (preview.get("decision") or {}).get("action"),
        "touch_count": len(touches),
        "template_touch_count": template_count,
        "individual_touch_count": len(touches) - template_count,
        "channels": [touch.get("channel") for touch in touches],
        "angles": [touch.get("angle") for touch in touches],
        "all_quality_gates_pass": all_gates_pass,
        "email_subjects_pass": subjects_pass,
        "no_long_dash": no_long_dash,
        "sequence_issues": list(preview.get("sequence_issues") or []),
        "missing": list(preview.get("missing") or []),
        "quality_reason_codes": list((preview.get("quality_gate") or {}).get("reason_codes") or []),
        "touches": [
            {
                "sequence_index": touch.get("sequence_index"),
                "channel": touch.get("channel"),
                "channel_status": touch.get("channel_status"),
                "angle": touch.get("angle"),
                "subject": touch.get("subject"),
                "text": touch.get("text"),
                "source_url": touch.get("source_url"),
                "observation": touch.get("observation"),
                "template_key": touch.get("template_key"),
                "template_label": (touch.get("template_selection") or {}).get("label"),
                "template_selection": touch.get("template_selection") or {},
                "quality_passed": bool((touch.get("quality_gate") or {}).get("passed")),
                "quality_score": _gate_score(touch),
                "quality_reason_codes": list((touch.get("quality_gate") or {}).get("reason_codes") or []),
            }
            for touch in touches
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LocalOS - review шаблонных цепочек",
        "",
        f"- Сформировано: {payload['generated_at']}",
        f"- Проверено: {payload['audited_count']}",
        f"- Готово по контенту: {payload['content_ready_count']}",
        f"- Нужна точечная правка: {payload['revise_count']}",
        "- Отправлено / поставлено в очередь: 0 / 0",
        "",
    ]
    for index, item in enumerate(payload["results"], start=1):
        lines.extend([
            f"## {index}. {item['name']}",
            "",
            f"**Статус:** {item['classification']}",
            f"**Сигнал:** {item.get('signal_label') or '-'}",
            f"**Каналы:** {' -> '.join(item.get('channels') or []) or '-'}",
            "",
        ])
        for touch in item.get("touches") or []:
            lines.extend([
                f"### Касание {int(touch['sequence_index']) + 1} - {touch['channel']}",
                "",
                f"- Основа: {touch.get('template_label') or 'индивидуальный текст'}",
                f"- Источник: {touch.get('source_url') or '-'}",
                f"- Качество: {touch.get('quality_score')}/18",
                "",
            ])
            if touch.get("subject"):
                lines.extend([f"**Тема:** {touch['subject']}", ""])
            lines.extend([str(touch.get("text") or ""), ""])
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--pool-limit", type=int, default=DEFAULT_POOL_LIMIT)
    parser.add_argument("--output-prefix", type=Path)
    args = parser.parse_args()
    if args.limit < 1 or args.pool_limit < args.limit:
        raise SystemExit("pool_limit must be greater than or equal to limit")

    generated_at = datetime.now(timezone.utc)
    prefix = args.output_prefix or (
        REPO_ROOT / "outputs" / f"localos-template-review-{generated_at:%Y%m%d}"
    )
    connection = _connect()
    audited: list[dict[str, Any]] = []
    ready: list[dict[str, Any]] = []
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        candidates = _select_candidates(cursor, pool_limit=args.pool_limit)
        for candidate in candidates:
            availability_preview = build_preview(
                cursor,
                str(candidate["workstream_id"]),
                sender_mode="localos",
                generate_ai=False,
                manual_reviewer_role="superadmin",
            )
            sequence = _template_sequence(availability_preview)
            preview = (
                build_preview(
                    cursor,
                    str(candidate["workstream_id"]),
                    sequence=sequence,
                    sender_mode="localos",
                    generate_ai=False,
                    manual_reviewer_role="superadmin",
                )
                if sequence
                else availability_preview
            )
            item = _summarize(candidate, preview)
            audited.append(item)
            if item["classification"] == "content_ready":
                ready.append(item)
                if len(ready) >= args.limit:
                    break
        connection.rollback()
    finally:
        connection.close()

    payload = {
        "schema_version": SCHEMA_VERSION,
        "template_library_version": TEMPLATE_LIBRARY_VERSION,
        "generated_at": generated_at.isoformat(),
        "requested_ready_count": args.limit,
        "pool_limit": args.pool_limit,
        "audited_count": len(audited),
        "content_ready_count": len(ready),
        "revise_count": sum(item["classification"] == "revise" for item in audited),
        "approved": 0,
        "queued": 0,
        "sent": 0,
        "database_mutations": 0,
        "results": audited,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    payload["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()

    json_path = prefix.with_suffix(".json")
    md_path = prefix.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "json_path": str(json_path),
        "md_path": str(md_path),
        "audited_count": payload["audited_count"],
        "content_ready_count": payload["content_ready_count"],
        "revise_count": payload["revise_count"],
        "canonical_sha256": payload["canonical_sha256"],
        "database_mutations": 0,
        "queued": 0,
        "sent": 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
