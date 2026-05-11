#!/usr/bin/env python3
import argparse
import json
import os
from collections import Counter
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


BAD_MARKERS = (
    "за чем сюда идти",
    "слабый визуальный слой режет доверие",
    "зоны роста",
    "реальные запросы клиентов",
    "без допрекламы",
    "social proof",
    "conversion layer",
    "всего 1 фото",
    "фото 1",
    "первое действие",
    "общее описание без структуры",
    "нет цены или формата",
    "ключевые направления",
)

TECHNICAL_KEYS = (
    "audit_full",
    "ai_enrichment",
    "debug",
    "raw_response",
    "prompt",
    "prompt_key",
    "prompt_version",
    "model",
    "reasoning",
)


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _load_offers(
    cur,
    group_id: str | None,
    group_name: str | None,
    lead_ids: list[str] | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            o.lead_id,
            o.slug,
            o.page_json,
            o.published_json,
            o.generated_json,
            o.edit_status,
            l.name,
            g.id AS group_id,
            g.name AS group_name
        FROM adminprospectingleadpublicoffers o
        JOIN prospectingleads l
          ON l.id = o.lead_id
        LEFT JOIN lead_group_items gi
          ON gi.lead_id = l.id
        LEFT JOIN lead_groups g
          ON g.id = gi.group_id
        WHERE o.is_active = TRUE
          AND (%s IS NULL OR g.id = %s)
          AND (%s IS NULL OR LOWER(g.name) LIKE %s)
          AND (%s IS NULL OR o.lead_id = ANY(%s))
        ORDER BY o.updated_at DESC NULLS LAST, l.updated_at DESC NULLS LAST
    """
    normalized_group_id = str(group_id or "").strip() or None
    normalized_group_name = str(group_name or "").strip().lower() or None
    normalized_lead_ids = [str(item).strip() for item in lead_ids or [] if str(item or "").strip()]
    group_name_pattern = f"%{normalized_group_name}%" if normalized_group_name else None
    params: list[Any] = [
        normalized_group_id,
        normalized_group_id,
        normalized_group_name,
        group_name_pattern,
        normalized_lead_ids or None,
        normalized_lead_ids or None,
    ]
    if limit and limit > 0:
        sql += " LIMIT %s"
        params.append(limit)
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall() or []]


def _page(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("published_json", "page_json", "generated_json"):
        value = row.get(key)
        if isinstance(value, dict) and value:
            return value
    return {}


def _walk(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield "", item


def _text_blob(value: Any) -> str:
    parts: list[str] = []
    for _key, item in _walk(value):
        if isinstance(item, str):
            parts.append(item)
    return "\n".join(parts).lower()


def _technical_key_hits(value: Any) -> list[str]:
    hits: set[str] = set()
    for key, _item in _walk(value):
        normalized = key.strip().lower()
        if normalized in TECHNICAL_KEYS:
            hits.add(normalized)
    return sorted(hits)


def _audit_for_row(row: dict[str, Any]) -> dict[str, Any]:
    page = _page(row)
    audit = page.get("audit") if isinstance(page.get("audit"), dict) else {}
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-id", default="")
    parser.add_argument("--group-name", default="")
    parser.add_argument("--lead-ids-file", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sample", type=int, default=12)
    args = parser.parse_args()
    lead_ids: list[str] = []
    if args.lead_ids_file:
        with open(args.lead_ids_file, encoding="utf-8") as handle:
            lead_ids = [line.strip() for line in handle.readlines() if line.strip()]

    conn = _connect()
    try:
        cur = conn.cursor()
        rows = _load_offers(
            cur,
            args.group_id,
            args.group_name,
            lead_ids,
            args.limit if args.limit > 0 else None,
        )
    finally:
        conn.close()

    summary_counter: Counter[str] = Counter()
    marker_hits: list[dict[str, Any]] = []
    long_summaries: list[dict[str, Any]] = []
    missing_variants: list[dict[str, Any]] = []
    technical_hits: list[dict[str, Any]] = []
    profile_conflicts: list[dict[str, Any]] = []
    gate_issues: list[dict[str, Any]] = []
    photo_hard_claims: list[dict[str, Any]] = []

    for row in rows:
        page = _page(row)
        audit = _audit_for_row(row)
        summary = str(audit.get("summary_text") or "").strip()
        summary_counter[summary] += 1
        blob = _text_blob(page)
        markers = [marker for marker in BAD_MARKERS if marker in blob]
        if markers:
            marker_hits.append({"lead_id": row.get("lead_id"), "name": row.get("name"), "markers": markers})
        if len(summary) > 300:
            long_summaries.append({"lead_id": row.get("lead_id"), "name": row.get("name"), "length": len(summary), "summary": summary[:220]})
        if not str(audit.get("summary_public") or "").strip() or not str(audit.get("summary_whatsapp") or "").strip():
            missing_variants.append({"lead_id": row.get("lead_id"), "name": row.get("name")})
        tech = _technical_key_hits(page)
        if tech:
            technical_hits.append({"lead_id": row.get("lead_id"), "name": row.get("name"), "keys": tech})
        conflicts = audit.get("audit_profile_conflicts")
        if isinstance(conflicts, list) and conflicts:
            profile_conflicts.append({"lead_id": row.get("lead_id"), "name": row.get("name"), "profile": audit.get("audit_profile"), "conflicts": conflicts})
        gate = audit.get("editorial_quality_gate") if isinstance(audit.get("editorial_quality_gate"), dict) else {}
        issues = gate.get("issues")
        if isinstance(issues, list) and issues:
            gate_issues.append({"lead_id": row.get("lead_id"), "name": row.get("name"), "issues": issues})
        photo_confidence = str(audit.get("photo_signal_confidence") or "").strip().lower()
        lowered_summary = summary.lower().replace("ё", "е")
        if photo_confidence != "confirmed" and any(
            claim in lowered_summary for claim in ("фотографий нет", "всего 1 фото", "фото 1", "только одно фото")
        ):
            photo_hard_claims.append(
                {
                    "lead_id": row.get("lead_id"),
                    "name": row.get("name"),
                    "photo_signal_confidence": photo_confidence,
                    "summary": summary[:220],
                }
            )

    duplicate_summaries = [
        {"count": count, "summary": summary[:240]}
        for summary, count in summary_counter.most_common()
        if summary and count >= 3
    ]
    payload = {
        "total": len(rows),
        "duplicate_summaries_5plus": duplicate_summaries[:20],
        "bad_marker_hits": marker_hits[: args.sample],
        "bad_marker_hits_count": len(marker_hits),
        "long_summaries_count": len(long_summaries),
        "long_summaries": long_summaries[: args.sample],
        "missing_summary_variants_count": len(missing_variants),
        "missing_summary_variants": missing_variants[: args.sample],
        "technical_key_hits_count": len(technical_hits),
        "technical_key_hits": technical_hits[: args.sample],
        "photo_hard_claims_count": len(photo_hard_claims),
        "photo_hard_claims": photo_hard_claims[: args.sample],
        "profile_conflicts_count": len(profile_conflicts),
        "profile_conflicts": profile_conflicts[: args.sample],
        "editorial_gate_issues_count": len(gate_issues),
        "editorial_gate_issues": gate_issues[: args.sample],
        "pass": (
            len(rows) > 0
            and not marker_hits
            and not long_summaries
            and not missing_variants
            and not technical_hits
            and not photo_hard_claims
            and not gate_issues
            and not duplicate_summaries
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
