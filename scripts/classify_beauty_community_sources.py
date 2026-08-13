#!/usr/bin/env python3
"""Curate the shared beauty Pulse without admitting customer-facing channels.

Dry-run is the default. ``--apply`` updates only public Telegram sources with
strong provenance: the manually collected industry archive. Channels found
directly on business map profiles are rejected at read time and are not
rewritten here because they may belong to another industry. The explicit
archive exclusions are intentionally small and reviewable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


EXCLUDED_ARCHIVE_TITLES = {
    "ll",
    "салон красоты эгоистка",
    "салоны красоты москвы",
}
CONTENT_LIBRARY_MARKERS = (
    "бьюти контент",
    "готовые посты",
    "рилс для бьюти",
    "сторис косметологам",
)

VENDOR_MARKERS = (
    "1с beauty",
    "bliss crm",
    "kpi.bi",
    "sointera",
    "wahelp",
    "yclients",
)
COMMUNITY_MARKERS = (
    "апик",
    "владельцы салонов",
    "форум",
    "кухня косметологов",
    "парикмахеры",
    "барбер-культур",
)
OWNER_MARKERS = (
    "бизнес",
    "владел",
    "директор",
    "деньги",
    "маркетинг",
    "монетиз",
    "предприним",
    "продаж",
    "салон",
    "сервис",
    "системн",
)


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _categories(metadata: dict[str, Any]) -> list[str]:
    values = metadata.get("categories")
    return [str(item).strip().lower() for item in values if str(item).strip()] if isinstance(values, list) else []


def classify_archive_source(source: dict[str, Any]) -> dict[str, Any]:
    """Return an explicit, auditable classification for a curated archive source."""
    title = _normalized(source.get("title"))
    document_count = int(source.get("documents_count") or 0)
    if title in EXCLUDED_ARCHIVE_TITLES:
        return {"decision": "b2c", "reason": "explicit_customer_facing_archive"}
    if document_count <= 0:
        return {"decision": "review", "reason": "no_documents"}
    if any(marker in title for marker in CONTENT_LIBRARY_MARKERS):
        return {
            "decision": "content_library",
            "reason": "professional_customer_content_templates",
            "role": "expert",
            "categories": ["бьюти", "канал", "профессионалы", "контент"],
        }
    role = str(source.get("source_role") or "unknown").strip().lower()
    if any(marker in title for marker in VENDOR_MARKERS):
        role = "vendor"
    elif any(marker in title for marker in COMMUNITY_MARKERS):
        role = "community"
    elif role not in {"community", "expert", "vendor"}:
        role = "expert"
    source_kind = "чат" if role == "community" else "канал"
    categories = ["бьюти", source_kind, "профессионалы"]
    if any(marker in title for marker in OWNER_MARKERS):
        categories.append("владельцы")
    return {
        "decision": "professional",
        "reason": "curated_industry_archive",
        "role": role,
        "categories": categories,
    }


def classify_map_source(source: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(source.get("metadata_json"))
    if metadata.get("community_default") is True:
        return {"decision": "review", "reason": "admin_override"}
    if str(metadata.get("discovery_origin") or "") != "map_parse":
        return {"decision": "review", "reason": "not_map_discovered"}
    return {"decision": "b2c", "reason": "official_channel_found_on_business_map_profile"}


def _apply_classification(cursor: Any, source: dict[str, Any], result: dict[str, Any]) -> None:
    metadata = _metadata(source.get("metadata_json"))
    existing_categories = _categories(metadata)
    if result["decision"] in {"professional", "content_library"}:
        metadata.update({
            "industry_key": "beauty",
            "audience": "business_professionals",
            "community_default": result["decision"] == "professional",
            "pulse_classification": result["decision"],
            "pulse_classification_reason": result["reason"],
        })
        metadata["categories"] = list(dict.fromkeys(existing_categories + result["categories"]))
        role = result["role"]
    elif result["decision"] == "b2c":
        metadata.update({
            "audience": "b2c",
            "community_default": False,
            "pulse_classification": "customer_facing",
            "pulse_classification_reason": result["reason"],
        })
        metadata["categories"] = list(dict.fromkeys(existing_categories + ["бьюти", "канал", "для клиентов"]))
        role = "salon"
    else:
        return
    cursor.execute(
        """
        UPDATE knowledge_sources
        SET source_role = %s, metadata_json = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (role, Json(metadata), source["id"]),
    )


def run(*, apply: bool) -> dict[str, Any]:
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    changes: list[dict[str, Any]] = []
    try:
        cursor.execute(
            """
            SELECT source.*, COUNT(document.id) FILTER (WHERE document.invalidated_at IS NULL) AS documents_count
            FROM knowledge_sources source
            LEFT JOIN knowledge_documents document ON document.source_id = source.id
            WHERE source.source_type = 'telegram'
              AND source.visibility = 'public'
              AND source.status = 'active'
              AND COALESCE(source.metadata_json->>'archive_folder', '') <> ''
            GROUP BY source.id
            ORDER BY source.title
            """
        )
        for raw in cursor.fetchall() or []:
            source = dict(raw)
            metadata = _metadata(source.get("metadata_json"))
            result = classify_archive_source(source)
            if result["decision"] == "review":
                continue
            current = {
                "role": str(source.get("source_role") or "unknown"),
                "audience": metadata.get("audience"),
                "community_default": metadata.get("community_default"),
                "categories": _categories(metadata),
            }
            desired = {
                "role": result.get("role") or "salon",
                "audience": "business_professionals" if result["decision"] in {"professional", "content_library"} else "b2c",
                "community_default": result["decision"] == "professional",
                "categories": result.get("categories") or ["бьюти", "канал", "для клиентов"],
            }
            if (
                current["role"] == desired["role"]
                and current["audience"] == desired["audience"]
                and current["community_default"] == desired["community_default"]
                and set(desired["categories"]).issubset(set(current["categories"]))
            ):
                continue
            changes.append({
                "id": str(source["id"]),
                "title": source.get("title"),
                "decision": result["decision"],
                "reason": result["reason"],
                "from": current,
                "to": desired,
            })
            if apply:
                _apply_classification(cursor, source, result)
        if apply:
            conn.commit()
        else:
            conn.rollback()
        return {
            "mode": "apply" if apply else "dry_run",
            "counts": dict(Counter(item["decision"] for item in changes)),
            "changes": changes,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
