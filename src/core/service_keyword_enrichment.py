from __future__ import annotations

from typing import Any

from core.service_duplicate_grouping import attach_duplicate_group_metadata
from core.service_safe_wordstat import (
    build_safe_seed_queries,
    detect_service_keyword_category,
    filter_wordstat_candidates,
)


def _fetch_wordstat_candidates(cursor: Any, seeds: list[str], limit_per_seed: int = 30) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    cursor.execute("SELECT to_regclass('public.wordstatkeywords') AS table_ref")
    table_row = cursor.fetchone()
    table_ref = None
    if hasattr(table_row, "keys"):
        table_ref = table_row.get("table_ref")
    elif table_row:
        table_ref = table_row[0]
    if not table_ref:
        return [{"keyword": seed, "views": 0, "category": "safe_seed"} for seed in seeds]
    for seed in seeds:
        candidates.append({"keyword": seed, "views": 0, "category": "safe_seed"})
        like_value = f"%{seed}%"
        cursor.execute(
            """
            SELECT keyword, views, category
            FROM wordstatkeywords
            WHERE LOWER(keyword) LIKE LOWER(%s)
            ORDER BY views DESC NULLS LAST
            LIMIT %s
            """,
            (like_value, limit_per_seed),
        )
        for row in cursor.fetchall() or []:
            if hasattr(row, "keys"):
                item = dict(row)
            else:
                item = {
                    "keyword": row[0] if len(row) > 0 else "",
                    "views": row[1] if len(row) > 1 else 0,
                    "category": row[2] if len(row) > 2 else "",
                }
            candidates.append(item)
    return candidates


def enrich_service_keywords_from_wordstat(
    cursor: Any,
    service: dict[str, Any],
    limit: int = 8,
) -> dict[str, Any]:
    seeds = build_safe_seed_queries(service)
    category_key = detect_service_keyword_category(service)
    if not seeds:
        return {
            "status": "manual_review",
            "keywords": [],
            "seeds": [],
            "blocked": [],
            "reason": "no_safe_seeds",
            "category": category_key,
        }
    candidates = _fetch_wordstat_candidates(cursor, seeds)
    filtered = filter_wordstat_candidates(candidates, category_key, limit=limit)
    allowed = filtered.get("allowed") or []
    blocked = filtered.get("blocked") or []
    if not allowed and blocked:
        status = "blocked"
        reason = "all_candidates_blocked"
    elif not allowed:
        status = "manual_review"
        reason = "no_safe_keywords"
    else:
        status = "auto_found"
        reason = None
    return {
        "status": status,
        "keywords": [str(item.get("keyword") or "").strip() for item in allowed if str(item.get("keyword") or "").strip()][:limit],
        "seeds": seeds,
        "blocked": blocked[:20],
        "reason": reason,
        "category": category_key,
        "anchors": filtered.get("anchors") or [],
    }


def attach_service_quality_metadata(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attach_duplicate_group_metadata(services)
    for service in services:
        keywords = service.get("keywords")
        has_keywords = bool(keywords)
        duplicate_group = service.get("duplicate_group") or {}
        quality_status = "ready" if has_keywords else "no_keywords"
        if int(duplicate_group.get("count") or 1) > 1:
            service["duplicate_status"] = "duplicate"
        service["quality_status"] = quality_status
        service.setdefault("keyword_enrichment", {
            "status": "not_started" if not has_keywords else "keywords_present",
            "keywords_count": len(keywords) if isinstance(keywords, list) else (1 if keywords else 0),
        })
    return services
