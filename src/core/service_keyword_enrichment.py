from __future__ import annotations

import json

from typing import Any

from core.service_duplicate_grouping import attach_duplicate_group_metadata
from core.service_keyword_scoring import tokenize_keyword_text
from core.service_safe_wordstat import (
    build_safe_seed_queries,
    detect_service_keyword_category,
    filter_wordstat_candidates,
    is_unsafe_query,
    normalize_query_text,
)


_QUERY_MODIFIERS = frozenset(tokenize_keyword_text(
    "заказ купить заказать цена стоимость услуга услуги пошив разработка изготовление "
    "производство нанесение доставка подрядчик онлайн недорого"
))


def match_saved_wordstat_keywords(
    cursor: Any, business_id: str | None, name: str,
) -> list[str]:
    """Match this business's saved Wordstat phrases to the current service title."""
    title_terms = set(tokenize_keyword_text(name)) - _QUERY_MODIFIERS
    if not business_id or not title_terms:
        return []

    cursor.execute(
        """
        SELECT k.keyword
        FROM wordstatkeywordscustom k
        WHERE k.business_id = %s AND k.views > 0
          AND NOT EXISTS (
              SELECT 1 FROM wordstatkeywordsexcluded e
              WHERE e.business_id = k.business_id
                AND LOWER(BTRIM(e.keyword)) = LOWER(BTRIM(k.keyword))
          )
          AND NOT EXISTS (
              SELECT 1 FROM seonegativekeywords n
              WHERE n.business_id = k.business_id AND n.is_active IS TRUE
                AND BTRIM(n.phrase) <> ''
                AND (n.scope <> 'category' OR LOWER(n.category) = LOWER(k.category))
                AND STRPOS(LOWER(k.keyword), LOWER(BTRIM(n.phrase))) > 0
          )
        ORDER BY k.views DESC, k.keyword
        """,
        (business_id,),
    )
    selected: list[str] = []
    seen: set[str] = set()
    for row in cursor.fetchall():
        keyword = str((row["keyword"] if hasattr(row, "keys") else row[0]) or "").strip()
        terms = set(tokenize_keyword_text(keyword)) - _QUERY_MODIFIERS
        key = keyword.casefold()
        if key not in seen and terms and terms <= title_terms:
            selected.append(keyword)
            seen.add(key)
            if len(selected) >= 6:
                break
    return selected


def merge_service_wordstat_keywords(existing: list[str], matched: list[str]) -> list[str]:
    result = list(existing)
    seen = {str(keyword).strip().casefold() for keyword in existing}
    for keyword in matched:
        key = keyword.casefold()
        if key not in seen:
            result.append(keyword)
            seen.add(key)
    return result


def parse_service_keywords(raw_keywords: Any) -> list[str]:
    if not raw_keywords:
        return []
    if isinstance(raw_keywords, list):
        return raw_keywords
    if isinstance(raw_keywords, str):
        try:
            parsed = json.loads(raw_keywords)
        except ValueError:
            pass
        else:
            if isinstance(parsed, list):
                return parsed
    return [item.strip() for item in str(raw_keywords).split(",") if item.strip()]


def find_service_wordstat_evidence(
    cursor: Any, business_id: str, name: str, city: str = "", *, candidates: list[dict] | None = None,
) -> list[dict]:
    """Find measured phrases supported by the service title and its own local context."""
    ignored = _QUERY_MODIFIERS | set(tokenize_keyword_text(city))
    title_terms = set(tokenize_keyword_text(name)) - ignored
    if not title_terms:
        return []
    if candidates is None:
        cursor.execute(
            """
            SELECT keyword, views, category, updated_at FROM (
                SELECT keyword, views, category, updated_at, 0 AS priority
                FROM wordstatkeywordscustom
                WHERE business_id = %s AND views > 0
                UNION ALL
                SELECT keyword, views, category, updated_at, 1 AS priority
                FROM (
                    SELECT keyword, views, category, updated_at
                    FROM wordstatkeywords
                    WHERE views > 0 AND LOWER(REPLACE(keyword, 'ё', 'е')) LIKE ANY(%s)
                    ORDER BY views DESC, keyword
                    LIMIT 150
                ) matching_global
            ) matching
            ORDER BY priority, views DESC, keyword
            """,
            (business_id, [f"%{term}%" for term in sorted(title_terms)]),
        )
        candidates = [dict(item) for item in cursor.fetchall()]

    cursor.execute("SELECT keyword FROM wordstatkeywordsexcluded WHERE business_id = %s", (business_id,))
    excluded = {normalize_query_text(row["keyword"]) for row in cursor.fetchall()}
    cursor.execute(
        "SELECT phrase, scope, category FROM seonegativekeywords WHERE business_id = %s AND is_active IS TRUE",
        (business_id,),
    )
    negative = [
        (normalize_query_text(row["phrase"]), row["scope"], str(row["category"] or "").casefold())
        for row in cursor.fetchall()
    ]
    result = []
    seen = set()
    for candidate in candidates:
        keyword = str(candidate["keyword"] or "").strip()
        normalized = normalize_query_text(keyword)
        terms = set(tokenize_keyword_text(keyword)) - ignored
        if not terms or not terms <= title_terms or normalized in excluded or normalized in seen:
            continue
        if is_unsafe_query(keyword)[0] or not candidate["views"] or candidate["views"] <= 0:
            continue
        category = str(candidate.get("category") or "").casefold()
        if any(phrase and phrase in normalized and (scope != "category" or key == category)
               for phrase, scope, key in negative):
            continue
        result.append(candidate)
        seen.add(normalized)
        if len(result) == 5:
            break
    return result


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
