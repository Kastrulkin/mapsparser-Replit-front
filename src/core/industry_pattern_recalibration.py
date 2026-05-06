from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

from core.industry_patterns import (
    detect_industry_key,
    evaluate_pattern_fit,
    get_industry_pattern_profile,
    normalize_pattern_text,
)


SUCCESS_RATING_MIN = 4.7
SUCCESS_REVIEWS_MIN = 50
MIN_INDUSTRY_ENTITIES = 3
MIN_TEXT_SAMPLES = 3
MAX_REVISION_ATTEMPTS = 2
STOP_WORDS = {
    "для",
    "или",
    "как",
    "при",
    "без",
    "под",
    "над",
    "это",
    "что",
    "она",
    "они",
    "the",
    "and",
    "with",
    "your",
}


def _row_value(row: Any, key: str, index: int, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "get"):
        try:
            return row.get(key, default)
        except Exception:
            pass
    try:
        return row[index]
    except Exception:
        return default


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return dict(parsed)
    return {}


def previous_month_range(today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    first_day = current.replace(day=1)
    end_day = first_day - timedelta(days=1)
    start_day = end_day.replace(day=1)
    return start_day, end_day


def ensure_industry_pattern_tables(conn) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_versions (
            id TEXT PRIMARY KEY,
            industry_key TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            pattern_text TEXT NOT NULL,
            examples_json JSONB,
            source_proposal_id TEXT,
            version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            activated_by TEXT,
            activated_at TIMESTAMPTZ DEFAULT NOW(),
            disabled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_proposals (
            id TEXT PRIMARY KEY,
            industry_key TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            proposed_pattern TEXT NOT NULL,
            examples_json JSONB,
            source_period_start DATE NOT NULL,
            source_period_end DATE NOT NULL,
            source_counts_json JSONB,
            confidence NUMERIC(5, 2) NOT NULL DEFAULT 0,
            risk_level TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'pending_review',
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            decision_comment TEXT,
            activated_version_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_decisions (
            id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            decided_by TEXT,
            decision_comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_impact_events (
            id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL,
            industry_key TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            business_id TEXT,
            user_id TEXT,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            result_status TEXT,
            metrics_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_admin_events (
            id TEXT PRIMARY KEY,
            actor_id TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            metadata_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )


def record_industry_pattern_admin_event(
    conn,
    *,
    actor_id: str = "",
    action: str,
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    clean_action = " ".join(str(action or "").split())
    if not clean_action:
        return {"recorded": 0, "error": "empty_action"}
    cursor.execute(
        """
        INSERT INTO industry_pattern_admin_events (
            id, actor_id, action, target_type, target_id, metadata_json, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW())
        """,
        (
            str(uuid.uuid4()),
            str(actor_id or "") or None,
            clean_action,
            str(target_type or "") or None,
            str(target_id or "") or None,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    if commit:
        conn.commit()
    return {"recorded": 1, "action": clean_action}


def list_industry_pattern_admin_events(conn, *, limit: int = 20) -> list[dict[str, Any]]:
    ensure_industry_pattern_tables(conn)
    clean_limit = max(1, min(int(limit or 20), 100))
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, actor_id, action, target_type, target_id, metadata_json, created_at
        FROM industry_pattern_admin_events
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (clean_limit,),
    )
    events: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        events.append(
            {
                "id": str(_row_value(row, "id", 0, "") or ""),
                "actor_id": str(_row_value(row, "actor_id", 1, "") or ""),
                "action": str(_row_value(row, "action", 2, "") or ""),
                "target_type": str(_row_value(row, "target_type", 3, "") or ""),
                "target_id": str(_row_value(row, "target_id", 4, "") or ""),
                "metadata": _json_dict(_row_value(row, "metadata_json", 5, {})),
                "created_at": str(_row_value(row, "created_at", 6, "") or ""),
            }
        )
    return events


def summarize_industry_pattern_admin_safety(conn) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM industry_pattern_versions WHERE status = 'active' AND disabled_at IS NULL) active_patterns,
          (SELECT COUNT(*) FROM industry_pattern_proposals WHERE status = 'pending_review') pending_proposals,
          (SELECT COUNT(*) FROM industry_pattern_proposals WHERE status = 'needs_revision') needs_revision,
          (SELECT MAX(created_at) FROM industry_pattern_proposals) last_proposal_at,
          (SELECT MAX(created_at) FROM industry_pattern_admin_events) last_admin_action_at,
          (SELECT COUNT(*) FROM industry_pattern_admin_events WHERE action IN ('rollback_confirmed', 'disable_confirmed')) destructive_actions
        """
    )
    row = cursor.fetchone()
    return {
        "superadmin_only": True,
        "rollback_requires_preview": True,
        "destructive_actions_require_confirmation": True,
        "active_patterns": int(_row_value(row, "active_patterns", 0, 0) or 0),
        "pending_proposals": int(_row_value(row, "pending_proposals", 1, 0) or 0),
        "needs_revision": int(_row_value(row, "needs_revision", 2, 0) or 0),
        "last_proposal_at": str(_row_value(row, "last_proposal_at", 3, "") or ""),
        "last_admin_action_at": str(_row_value(row, "last_admin_action_at", 4, "") or ""),
        "destructive_actions": int(_row_value(row, "destructive_actions", 5, 0) or 0),
    }


def _classified_successful_entities_sql() -> str:
    return """
        WITH entity AS (
          SELECT
            'business' entity_source,
            id,
            name,
            rating::float8 rating,
            reviews_count,
            business_type,
            industry,
            categories::text categories,
            created_at
          FROM businesses
          WHERE (
              created_at::date BETWEEN %s AND %s
              OR EXISTS (
                  SELECT 1 FROM userservices us
                  WHERE us.business_id = businesses.id
                    AND us.created_at::date BETWEEN %s AND %s
              )
              OR EXISTS (
                  SELECT 1 FROM externalbusinessreviews er
                  WHERE er.business_id = businesses.id
                    AND (
                        er.created_at::date BETWEEN %s AND %s
                        OR er.published_at::date BETWEEN %s AND %s
                        OR er.response_at::date BETWEEN %s AND %s
                    )
              )
              OR EXISTS (
                  SELECT 1 FROM usernews un
                  WHERE un.business_id = businesses.id
                    AND un.created_at::date BETWEEN %s AND %s
              )
          )
          UNION ALL
          SELECT
            'lead' entity_source,
            id,
            name,
            rating,
            reviews_count,
            category business_type,
            category industry,
            category categories,
            created_at
          FROM prospectingleads
          WHERE created_at::date BETWEEN %s AND %s
        )
        SELECT entity_source, id, name, rating, reviews_count, business_type, industry, categories
        FROM entity
        WHERE rating >= %s
          AND COALESCE(reviews_count, 0) >= %s
    """


def _load_successful_entities(conn, start_day: date, end_day: date) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        _classified_successful_entities_sql(),
        (
            start_day,
            end_day,
            start_day,
            end_day,
            start_day,
            end_day,
            start_day,
            end_day,
            start_day,
            end_day,
            start_day,
            end_day,
            start_day,
            end_day,
            SUCCESS_RATING_MIN,
            SUCCESS_REVIEWS_MIN,
        ),
    )
    entities: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = {
            "source": str(_row_value(row, "entity_source", 0, "") or ""),
            "id": str(_row_value(row, "id", 1, "") or ""),
            "name": str(_row_value(row, "name", 2, "") or ""),
            "rating": _row_value(row, "rating", 3),
            "reviews_count": int(_row_value(row, "reviews_count", 4, 0) or 0),
            "business_type": str(_row_value(row, "business_type", 5, "") or ""),
            "industry": str(_row_value(row, "industry", 6, "") or ""),
            "categories": str(_row_value(row, "categories", 7, "") or ""),
        }
        item["industry_key"] = detect_industry_key(
            business_name=item["name"],
            business_type=item["business_type"],
            industry=item["industry"],
            categories=item["categories"],
        )
        entities.append(item)
    return entities


def _short_text(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _tokenize_pattern_text(value: str) -> list[str]:
    current = []
    words = []
    for char in normalize_pattern_text(value):
        if char.isalnum():
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return [word for word in words if len(word) >= 4 and word not in STOP_WORDS]


def _top_terms(texts: list[str], limit: int = 5) -> list[str]:
    counts: dict[str, int] = {}
    for text in texts:
        for word in _tokenize_pattern_text(text):
            counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, count in ranked[:limit] if count >= 2]


def _business_ids_for_samples(entities: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for item in entities:
        if str(item.get("source") or "") != "business":
            continue
        business_id = str(item.get("id") or "").strip()
        if business_id and business_id not in ids:
            ids.append(business_id)
    return ids


def _load_text_samples(conn, entities: list[dict[str, Any]], start_day: date, end_day: date) -> dict[str, dict[str, list[dict[str, Any]]]]:
    business_ids = _business_ids_for_samples(entities)
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}
    if not business_ids:
        return result
    for item in entities:
        business_id = str(item.get("id") or "").strip()
        industry_key = str(item.get("industry_key") or "local_business")
        if business_id in business_ids:
            result.setdefault(industry_key, {"service": [], "news": [], "review_reply": []})

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT business_id, name, description, category, price
        FROM userservices
        WHERE business_id = ANY(%s)
          AND created_at::date BETWEEN %s AND %s
          AND COALESCE(is_active, TRUE) = TRUE
        ORDER BY created_at DESC
        LIMIT 400
        """,
        (business_ids, start_day, end_day),
    )
    for row in cursor.fetchall() or []:
        business_id = str(_row_value(row, "business_id", 0, "") or "")
        industry_key = _industry_for_business_id(entities, business_id)
        if not industry_key:
            continue
        name = _short_text(_row_value(row, "name", 1, ""))
        description = _short_text(_row_value(row, "description", 2, ""))
        category = _short_text(_row_value(row, "category", 3, ""))
        price = _short_text(_row_value(row, "price", 4, ""))
        text = " ".join(part for part in [name, category, price] if part)
        result.setdefault(industry_key, {"service": [], "news": [], "review_reply": []})["service"].append(
            {
                "business_id": business_id,
                "name": name,
                "description": description,
                "category": category,
                "price": price,
                "text": _short_text(text or description),
            }
        )

    cursor.execute(
        """
        SELECT business_id, generated_text, approved, created_at
        FROM usernews
        WHERE business_id = ANY(%s)
          AND created_at::date BETWEEN %s AND %s
        ORDER BY created_at DESC
        LIMIT 300
        """,
        (business_ids, start_day, end_day),
    )
    for row in cursor.fetchall() or []:
        business_id = str(_row_value(row, "business_id", 0, "") or "")
        industry_key = _industry_for_business_id(entities, business_id)
        text = _short_text(_row_value(row, "generated_text", 1, ""))
        if industry_key and text:
            result.setdefault(industry_key, {"service": [], "news": [], "review_reply": []})["news"].append(
                {
                    "business_id": business_id,
                    "text": text,
                    "approved": bool(_row_value(row, "approved", 2, False)),
                }
            )

    cursor.execute(
        """
        SELECT business_id, text, response_text, rating
        FROM externalbusinessreviews
        WHERE business_id = ANY(%s)
          AND (
              created_at::date BETWEEN %s AND %s
              OR published_at::date BETWEEN %s AND %s
              OR response_at::date BETWEEN %s AND %s
          )
          AND response_text IS NOT NULL
        ORDER BY COALESCE(response_at, published_at, created_at) DESC
        LIMIT 400
        """,
        (business_ids, start_day, end_day, start_day, end_day, start_day, end_day),
    )
    for row in cursor.fetchall() or []:
        business_id = str(_row_value(row, "business_id", 0, "") or "")
        industry_key = _industry_for_business_id(entities, business_id)
        response_text = _short_text(_row_value(row, "response_text", 2, ""))
        if industry_key and response_text:
            result.setdefault(industry_key, {"service": [], "news": [], "review_reply": []})["review_reply"].append(
                {
                    "business_id": business_id,
                    "review": _short_text(_row_value(row, "text", 1, "")),
                    "text": response_text,
                    "rating": _row_value(row, "rating", 3),
                }
            )
    return result


def _industry_for_business_id(entities: list[dict[str, Any]], business_id: str) -> str:
    for item in entities:
        if str(item.get("source") or "") == "business" and str(item.get("id") or "") == business_id:
            return str(item.get("industry_key") or "local_business")
    return ""


def _count_source_rows(conn, start_day: date, end_day: date) -> dict[str, int]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM cards WHERE created_at::date BETWEEN %s AND %s) audits,
          (SELECT COUNT(*) FROM userservices WHERE created_at::date BETWEEN %s AND %s) services,
          (SELECT COUNT(*) FROM externalbusinessreviews WHERE created_at::date BETWEEN %s AND %s) reviews,
          (SELECT COUNT(*) FROM externalbusinessreviews WHERE response_at::date BETWEEN %s AND %s) review_replies,
          (SELECT COUNT(*) FROM usernews WHERE created_at::date BETWEEN %s AND %s) news
        """,
        (start_day, end_day, start_day, end_day, start_day, end_day, start_day, end_day, start_day, end_day),
    )
    row = cursor.fetchone()
    return {
        "audits": int(_row_value(row, "audits", 0, 0) or 0),
        "services": int(_row_value(row, "services", 1, 0) or 0),
        "reviews": int(_row_value(row, "reviews", 2, 0) or 0),
        "review_replies": int(_row_value(row, "review_replies", 3, 0) or 0),
        "news": int(_row_value(row, "news", 4, 0) or 0),
    }


def _proposal_exists(cursor, industry_key: str, pattern_type: str, pattern_text: str, start_day: date, end_day: date) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM industry_pattern_proposals
        WHERE industry_key = %s
          AND pattern_type = %s
          AND proposed_pattern = %s
          AND source_period_start = %s
          AND source_period_end = %s
        LIMIT 1
        """,
        (industry_key, pattern_type, pattern_text, start_day, end_day),
    )
    return bool(cursor.fetchone())


def _pattern_type_label(pattern_type: str) -> str:
    if pattern_type == "service":
        return "услугах"
    if pattern_type == "news":
        return "новостях"
    if pattern_type == "review_reply":
        return "ответах на отзывы"
    return pattern_type


def _sample_texts(samples: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for item in samples:
        text = str(item.get("text") or item.get("name") or "").strip()
        if text:
            texts.append(text)
    return texts


def _examples_for_pattern(
    *,
    entities: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    pattern_type: str,
) -> list[dict[str, Any]]:
    entity_by_id = {str(item.get("id") or ""): item for item in entities if str(item.get("source") or "") == "business"}
    examples: list[dict[str, Any]] = []
    for sample in samples[:5]:
        business_id = str(sample.get("business_id") or "")
        entity = entity_by_id.get(business_id) or {}
        example = {
            "business_name": entity.get("name"),
            "rating": entity.get("rating"),
            "reviews_count": entity.get("reviews_count"),
            "text": sample.get("text") or sample.get("name"),
        }
        if pattern_type == "review_reply":
            example["review"] = sample.get("review")
            example["review_rating"] = sample.get("rating")
        if pattern_type == "service":
            example["category"] = sample.get("category")
            example["price"] = sample.get("price")
        examples.append(example)
    if examples:
        return examples
    return [
        {
            "business_name": item.get("name"),
            "rating": item.get("rating"),
            "reviews_count": item.get("reviews_count"),
        }
        for item in entities[:5]
    ]


def _proposal_confidence(entity_count: int, sample_count: int, unique_terms: int) -> float:
    value = 0.45 + min(entity_count, 30) / 100 + min(sample_count, 60) / 130 + min(unique_terms, 8) / 80
    return round(min(0.92, value), 2)


def _risk_level_for(industry_key: str, pattern_type: str, confidence: float, sample_count: int) -> str:
    if industry_key == "medical":
        return "medium"
    if sample_count < 6 or confidence < 0.65:
        return "medium"
    if pattern_type == "review_reply" and confidence < 0.75:
        return "medium"
    return "low"


def _proposed_pattern_text(
    *,
    profile: dict[str, Any],
    industry_key: str,
    pattern_type: str,
    base_pattern: str,
    terms: list[str],
    sample_count: int,
) -> str:
    label = str(profile.get("label") or industry_key)
    type_label = _pattern_type_label(pattern_type)
    term_text = ", ".join(terms[:5])
    if term_text:
        return (
            f"Для индустрии {label} в {type_label} использовать проверенный формат: {base_pattern} "
            f"Частые рабочие маркеры из успешных точек: {term_text}. "
            f"Применять только когда это подтверждено исходными данными; без выдуманных фактов и обещаний."
        )
    return (
        f"Для индустрии {label} в {type_label} использовать проверенный формат: {base_pattern} "
        f"Основано на {sample_count} текстовых примерах успешных точек; применять только при совпадении с фактами."
    )


def _build_proposals(
    entities: list[dict[str, Any]],
    counts: dict[str, int],
    text_samples: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
) -> list[dict[str, Any]]:
    by_industry: dict[str, list[dict[str, Any]]] = {}
    for item in entities:
        key = str(item.get("industry_key") or "local_business")
        by_industry.setdefault(key, []).append(item)

    proposals: list[dict[str, Any]] = []
    seen_patterns: set[tuple[str, str, str]] = set()
    for industry_key, industry_entities in by_industry.items():
        if len(industry_entities) < MIN_INDUSTRY_ENTITIES:
            continue
        profile = get_industry_pattern_profile(industry_key)
        pattern_map = (
            ("service", (profile.get("service_patterns") or ["Писать конкретнее по фактам услуги."])[0]),
            ("news", (profile.get("news_patterns") or ["Писать новости с конкретным поводом."])[0]),
            ("review_reply", (profile.get("review_reply_patterns") or ["Использовать деталь из отзыва."])[0]),
        )
        industry_samples = (text_samples or {}).get(industry_key) or {}
        for pattern_type, base_pattern in pattern_map:
            samples = industry_samples.get(pattern_type) or []
            if text_samples is not None and len(samples) < MIN_TEXT_SAMPLES:
                continue
            texts = _sample_texts(samples)
            terms = _top_terms(texts)
            sample_count = len(samples)
            confidence = _proposal_confidence(len(industry_entities), sample_count, len(terms))
            pattern_text = _proposed_pattern_text(
                profile=profile,
                industry_key=industry_key,
                pattern_type=pattern_type,
                base_pattern=str(base_pattern),
                terms=terms,
                sample_count=sample_count,
            )
            dedupe_key = (industry_key, pattern_type, normalize_pattern_text(pattern_text))
            if dedupe_key in seen_patterns:
                continue
            seen_patterns.add(dedupe_key)
            examples = _examples_for_pattern(
                entities=industry_entities,
                samples=samples,
                pattern_type=pattern_type,
            )
            source_counts = dict(counts)
            source_counts["successful_entities"] = len(industry_entities)
            source_counts[f"{pattern_type}_samples"] = sample_count
            source_counts[f"{pattern_type}_terms"] = terms
            proposals.append(
                {
                    "industry_key": industry_key,
                    "pattern_type": pattern_type,
                    "proposed_pattern": pattern_text,
                    "examples": examples,
                    "source_counts": source_counts,
                    "confidence": confidence,
                    "risk_level": _risk_level_for(industry_key, pattern_type, confidence, sample_count),
                }
            )
    return proposals


def run_monthly_industry_pattern_recalibration(
    conn,
    *,
    today: date | None = None,
    create_proposals: bool = True,
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    start_day, end_day = previous_month_range(today)
    counts = _count_source_rows(conn, start_day, end_day)
    entities = _load_successful_entities(conn, start_day, end_day)
    text_samples = _load_text_samples(conn, entities, start_day, end_day)
    proposals = _build_proposals(entities, counts, text_samples)

    created_ids: list[str] = []
    if create_proposals:
        cursor = conn.cursor()
        for proposal in proposals:
            pattern_text = str(proposal.get("proposed_pattern") or "").strip()
            industry_key = str(proposal.get("industry_key") or "local_business").strip()
            pattern_type = str(proposal.get("pattern_type") or "service").strip()
            if not pattern_text:
                continue
            if _proposal_exists(cursor, industry_key, pattern_type, pattern_text, start_day, end_day):
                continue
            proposal_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO industry_pattern_proposals (
                    id, industry_key, pattern_type, proposed_pattern, examples_json,
                    source_period_start, source_period_end, source_counts_json,
                    confidence, risk_level, status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, 'pending_review', NOW(), NOW())
                """,
                (
                    proposal_id,
                    industry_key,
                    pattern_type,
                    pattern_text,
                    json.dumps(proposal.get("examples") or [], ensure_ascii=False),
                    start_day,
                    end_day,
                    json.dumps(proposal.get("source_counts") or {}, ensure_ascii=False),
                    proposal.get("confidence") or 0,
                    proposal.get("risk_level") or "medium",
                ),
            )
            created_ids.append(proposal_id)
        conn.commit()

    return {
        "period_start": start_day.isoformat(),
        "period_end": end_day.isoformat(),
        "counts": counts,
        "successful_entities": len(entities),
        "proposals": proposals,
        "created_proposal_ids": created_ids,
        "telegram_summary": format_monthly_recalibration_summary(
            start_day=start_day,
            end_day=end_day,
            counts=counts,
            proposals=proposals,
            created_count=len(created_ids),
        ),
    }


def format_monthly_recalibration_summary(
    *,
    start_day: date,
    end_day: date,
    counts: dict[str, int],
    proposals: list[dict[str, Any]],
    created_count: int,
) -> str:
    by_industry: dict[str, list[dict[str, Any]]] = {}
    for item in proposals:
        by_industry.setdefault(str(item.get("industry_key") or "local_business"), []).append(item)
    lines = [
        "Ежемесячная калибровка LocalOS",
        f"Период: {start_day.isoformat()} - {end_day.isoformat()}",
        "",
        "Обработано:",
        f"- аудитов: {counts.get('audits', 0)}",
        f"- услуг: {counts.get('services', 0)}",
        f"- отзывов: {counts.get('reviews', 0)}",
        f"- ответов на отзывы: {counts.get('review_replies', 0)}",
        f"- новостей: {counts.get('news', 0)}",
        "",
        f"Создано pending-предложений: {created_count}",
    ]
    if not proposals:
        lines.append("Новых паттернов для review не найдено.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Предложения:")
    for industry_key, items in list(by_industry.items())[:6]:
        profile = get_industry_pattern_profile(industry_key)
        lines.append(f"- {profile.get('label')}: {len(items)}")
        for item in items[:3]:
            pattern = str(item.get("proposed_pattern") or "").strip()
            if len(pattern) > 120:
                pattern = pattern[:117].rstrip() + "..."
            lines.append(f"  {item.get('pattern_type')}: {pattern}")
    lines.append("")
    lines.append("Ничего не применено автоматически. Нужна ручная проверка суперадмина.")
    return "\n".join(lines)


def load_active_industry_patterns(conn, industry_key: str, pattern_type: str, limit: int = 8) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, industry_key, pattern_type, pattern_text, version
            FROM industry_pattern_versions
            WHERE industry_key = %s
              AND pattern_type = %s
              AND status = 'active'
              AND disabled_at IS NULL
            ORDER BY activated_at DESC, created_at DESC
            LIMIT %s
            """,
            (industry_key, pattern_type, max(1, min(int(limit or 8), 20))),
        )
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    seen_texts: list[str] = []
    for row in cursor.fetchall() or []:
        text = str(_row_value(row, "pattern_text", 3, "") or "").strip()
        if text and text not in seen_texts:
            seen_texts.append(text)
            items.append(
                {
                    "id": str(_row_value(row, "id", 0, "") or ""),
                    "industry_key": str(_row_value(row, "industry_key", 1, industry_key) or industry_key),
                    "pattern_type": str(_row_value(row, "pattern_type", 2, pattern_type) or pattern_type),
                    "pattern_text": text,
                    "version": str(_row_value(row, "version", 4, "") or ""),
                }
            )
    return items


def format_loaded_active_industry_patterns(patterns: list[dict[str, Any]]) -> str:
    items: list[str] = []
    for pattern in patterns or []:
        text = str(pattern.get("pattern_text") or "").strip()
        if text and text not in items:
            items.append(text)
    if not items:
        return ""
    return "Подтвержденные суперадмином паттерны:\n" + "\n".join(f"- {item}" for item in items)


def format_active_industry_patterns(conn, industry_key: str, pattern_type: str, limit: int = 8) -> str:
    return format_loaded_active_industry_patterns(
        load_active_industry_patterns(conn, industry_key, pattern_type, limit=limit)
    )


def _impact_text_has_any(text: str, markers: list[Any]) -> bool:
    normalized = normalize_pattern_text(text)
    for marker in markers or []:
        clean_marker = normalize_pattern_text(str(marker or ""))
        if clean_marker and clean_marker in normalized:
            return True
    return False


def _impact_source_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw_token in normalize_pattern_text(text).split():
        token = raw_token.strip()
        if len(token) >= 5 and token not in STOP_WORDS and token not in tokens:
            tokens.append(token)
    return tokens[:12]


def _impact_number(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _impact_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _keyword_found_value(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    return _impact_int(value.get("found") or value.get("found_count") or 0)


def _business_effect_status(effect_score: float, total_items: int, needs_review: int) -> str:
    if total_items <= 0:
        return "no_data"
    if effect_score >= 0.25 and needs_review == 0:
        return "positive"
    if effect_score <= -0.25 or needs_review > 0:
        return "negative"
    return "neutral"


def build_pattern_impact_metrics(
    payload: Any,
    pattern_type: str,
    *,
    industry_key: str = "local_business",
    source_text: str = "",
) -> dict[str, Any]:
    if pattern_type == "service":
        services = payload if isinstance(payload, list) else _row_value(payload, "services", 0, [])
        if not isinstance(services, list):
            services = []
        total = 0
        fallback = 0
        guardrail_failed = 0
        pattern_fit = 0
        missing_keywords = 0
        weak_matches_only = 0
        no_keywords = 0
        needs_review_services = 0
        seo_score_delta_total = 0.0
        keyword_found_delta_total = 0
        manual_edits = 0
        accepted = 0
        for service in services:
            if not isinstance(service, dict):
                continue
            total += 1
            if bool(service.get("accepted") or service.get("applied") or service.get("approved")):
                accepted += 1
            if bool(service.get("manual_edit") or service.get("manual_edited") or service.get("edited_by_user")):
                manual_edits += 1
            seo_before = service.get("seo_score_before")
            seo_after = service.get("seo_score_after")
            if seo_before is not None and seo_after is not None:
                seo_score_delta_total += _impact_number(seo_after) - _impact_number(seo_before)
            elif service.get("seo_score_delta") is not None:
                seo_score_delta_total += _impact_number(service.get("seo_score_delta"))
            before_keyword_score = service.get("seo_keyword_score_before") or service.get("keyword_score_before")
            after_keyword_score = service.get("seo_keyword_score") or service.get("keyword_score") or service.get("seo_keyword_score_after")
            keyword_found_delta_total += max(0, _keyword_found_value(after_keyword_score) - _keyword_found_value(before_keyword_score))
            service_needs_review = False
            if bool(service.get("fallback_used")):
                fallback += 1
                service_needs_review = True
            guardrail_reasons = service.get("guardrail_reasons")
            if isinstance(guardrail_reasons, list) and guardrail_reasons:
                guardrail_failed += 1
                service_needs_review = True
            service_pattern_fit = service.get("pattern_fit")
            if isinstance(service_pattern_fit, dict) and service_pattern_fit.get("status") == "needs_review":
                pattern_fit += 1
                service_needs_review = True
            keyword_score = after_keyword_score
            if isinstance(keyword_score, dict):
                missing = keyword_score.get("missing")
                if isinstance(missing, list) and missing:
                    missing_keywords += 1
                    service_needs_review = True
                try:
                    found = int(keyword_score.get("found") or 0)
                    close_count = int(keyword_score.get("close_count") or 0)
                    score_total = int(keyword_score.get("total") or 0)
                except Exception:
                    found = 0
                    close_count = 0
                    score_total = 0
                if score_total == 0:
                    no_keywords += 1
                    service_needs_review = True
                if found > 0 and found == close_count:
                    weak_matches_only += 1
                    service_needs_review = True
            if service_needs_review:
                needs_review_services += 1
        needs_review = len(
            [
                item
                for item in [fallback, guardrail_failed, pattern_fit, missing_keywords, weak_matches_only, no_keywords]
                if item > 0
            ]
        )
        effect_score = round(
            (
                max(0, total - needs_review_services)
                + min(keyword_found_delta_total, total * 2) * 0.2
                + seo_score_delta_total * 0.02
                + accepted * 0.2
                - needs_review_services
                - fallback * 0.5
                - manual_edits * 0.3
            )
            / max(total, 1),
            3,
        )
        return {
            "total": total,
            "good": max(0, total - needs_review_services),
            "needs_review": needs_review_services,
            "fallback": fallback,
            "guardrail_failed": guardrail_failed,
            "pattern_fit": pattern_fit,
            "missing_keywords": missing_keywords,
            "weak_matches_only": weak_matches_only,
            "no_keywords": no_keywords,
            "issue_groups": needs_review,
            "seo_score_delta": round(seo_score_delta_total, 3),
            "keyword_found_delta": keyword_found_delta_total,
            "manual_edits": manual_edits,
            "accepted": accepted,
            "business_effect_score": effect_score,
            "business_effect_status": _business_effect_status(effect_score, total, needs_review_services),
            "sample_text": _impact_pattern_short_text(
                {
                    "pattern_text": "; ".join(
                        str(service.get("optimized_name") or service.get("original_name") or "").strip()
                        for service in services[:3]
                        if isinstance(service, dict)
                    )
                },
                limit=220,
            ),
        }

    text = ""
    if isinstance(payload, dict):
        text = str(payload.get("text") or payload.get("generated_text") or payload.get("reply") or "").strip()
    else:
        text = str(payload or "").strip()
    profile = get_industry_pattern_profile(industry_key or "local_business")
    forbidden_claims = 1 if _impact_text_has_any(text, profile.get("forbidden_claims") or []) else 0
    industry_drift = 1 if _impact_text_has_any(text, profile.get("forbidden_industry_drifts") or []) else 0
    pattern_fit = evaluate_pattern_fit(text, industry_key or "local_business", mode=pattern_type)
    pattern_fit_failed = 1 if pattern_fit.get("status") == "needs_review" else 0

    if pattern_type == "news":
        factual_risk_markers = [
            "скидка",
            "акция",
            "цена",
            "стоимость",
            "бесплатно",
            "подарок",
            "только сегодня",
            "до конца дня",
        ]
        source_has_risk_marker = _impact_text_has_any(source_text, factual_risk_markers)
        factual_risk = 1 if _impact_text_has_any(text, factual_risk_markers) and not source_has_risk_marker else 0
        too_long = 1 if len(text) > 1200 else 0
        empty = 0 if text else 1
        needs_review = 1 if any([empty, too_long, forbidden_claims, industry_drift, factual_risk, pattern_fit_failed]) else 0
        manual_edits = _impact_int(payload.get("manual_edits") if isinstance(payload, dict) else 0)
        accepted = 1 if isinstance(payload, dict) and bool(payload.get("accepted") or payload.get("published") or payload.get("approved")) else 0
        effect_score = round((1 - needs_review + accepted * 0.3 - manual_edits * 0.25) if text else 0, 3)
        return {
            "total": 1 if text else 0,
            "good": 0 if needs_review else 1,
            "needs_review": needs_review,
            "text_length": len(text),
            "too_long": too_long,
            "forbidden_claims": forbidden_claims,
            "industry_drift": industry_drift,
            "factual_risk": factual_risk,
            "pattern_fit": pattern_fit_failed,
            "empty": empty,
            "manual_edits": manual_edits,
            "accepted": accepted,
            "business_effect_score": effect_score,
            "business_effect_status": _business_effect_status(effect_score, 1 if text else 0, needs_review),
            "sample_text": text[:220],
            "source_excerpt": str(source_text or "").strip()[:220],
        }

    if pattern_type == "review_reply":
        gratitude_markers = ["спасибо", "благодар", "рады", "жаль", "извин"]
        no_gratitude = 0 if _impact_text_has_any(text, gratitude_markers) else 1
        source_tokens = _impact_source_tokens(source_text)
        has_review_detail = any(token in normalize_pattern_text(text) for token in source_tokens[:8]) if source_tokens else True
        no_review_detail = 0 if has_review_detail else 1
        too_long = 1 if len(text) > 350 else 0
        empty = 0 if text else 1
        needs_review = 1 if any([empty, too_long, no_gratitude, no_review_detail, forbidden_claims, industry_drift, pattern_fit_failed]) else 0
        manual_edits = _impact_int(payload.get("manual_edits") if isinstance(payload, dict) else 0)
        accepted = 1 if isinstance(payload, dict) and bool(payload.get("accepted") or payload.get("sent") or payload.get("approved")) else 0
        effect_score = round((1 - needs_review + accepted * 0.3 - no_review_detail * 0.4 - manual_edits * 0.25) if text else 0, 3)
        return {
            "total": 1 if text else 0,
            "good": 0 if needs_review else 1,
            "needs_review": needs_review,
            "text_length": len(text),
            "too_long": too_long,
            "no_gratitude": no_gratitude,
            "no_review_detail": no_review_detail,
            "forbidden_claims": forbidden_claims,
            "industry_drift": industry_drift,
            "pattern_fit": pattern_fit_failed,
            "empty": empty,
            "manual_edits": manual_edits,
            "accepted": accepted,
            "business_effect_score": effect_score,
            "business_effect_status": _business_effect_status(effect_score, 1 if text else 0, needs_review),
            "sample_text": text[:220],
            "source_excerpt": str(source_text or "").strip()[:220],
        }

    effect_score = 1 if text else 0
    return {
        "total": 1 if text else 0,
        "good": 1 if text else 0,
        "needs_review": 0,
        "text_length": len(text),
        "business_effect_score": effect_score,
        "business_effect_status": _business_effect_status(effect_score, 1 if text else 0, 0),
        "sample_text": text[:220],
    }


def record_industry_pattern_impact_event(
    conn,
    patterns: list[dict[str, Any]],
    *,
    industry_key: str,
    pattern_type: str,
    business_id: str = "",
    user_id: str = "",
    source: str,
    event_type: str,
    result_status: str = "",
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_patterns = [pattern for pattern in patterns or [] if str(pattern.get("id") or "").strip()]
    if not clean_patterns:
        return {"recorded": 0}
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    recorded = 0
    try:
        for pattern in clean_patterns:
            cursor.execute(
                """
                INSERT INTO industry_pattern_impact_events (
                    id, version_id, industry_key, pattern_type, business_id, user_id,
                    source, event_type, result_status, metrics_json, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    str(pattern.get("id") or ""),
                    industry_key,
                    pattern_type,
                    business_id or None,
                    user_id or None,
                    source,
                    event_type,
                    result_status or None,
                    json.dumps(metrics or {}, ensure_ascii=False),
                ),
            )
            recorded += 1
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"recorded": 0, "error": "impact_event_failed"}
    return {"recorded": recorded}


def summarize_industry_pattern_health(
    conn,
    *,
    industry_key: str = "all",
    pattern_type: str = "all",
    days: int = 30,
    limit: int = 8,
) -> list[dict[str, Any]]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    where_parts = ["status = 'active'", "disabled_at IS NULL"]
    params: list[Any] = []
    if industry_key and industry_key != "all":
        where_parts.append("industry_key = %s")
        params.append(industry_key)
    if pattern_type and pattern_type != "all":
        where_parts.append("pattern_type = %s")
        params.append(pattern_type)
    cursor.execute(
        f"""
        SELECT id, industry_key, pattern_type, pattern_text, version, activated_at, source_proposal_id
        FROM industry_pattern_versions
        WHERE {' AND '.join(where_parts)}
        ORDER BY activated_at DESC, created_at DESC
        LIMIT %s
        """,
        params + [max(1, min(int(limit or 8), 20))],
    )
    versions = cursor.fetchall() or []
    version_ids = [str(_row_value(row, "id", 0, "") or "") for row in versions]
    if not version_ids:
        return []

    placeholders = ", ".join(["%s"] * len(version_ids))
    cursor.execute(
        f"""
        SELECT version_id, event_type, result_status, metrics_json
        FROM industry_pattern_impact_events
        WHERE version_id IN ({placeholders})
          AND created_at >= NOW() - INTERVAL '1 day' * %s
        """,
        version_ids + [max(1, min(int(days or 30), 365))],
    )
    event_rows = cursor.fetchall() or []
    by_version: dict[str, dict[str, Any]] = {}
    for row in versions:
        version_id = str(_row_value(row, "id", 0, "") or "")
        by_version[version_id] = {
            "version_id": version_id,
            "industry_key": str(_row_value(row, "industry_key", 1, "") or ""),
            "pattern_type": str(_row_value(row, "pattern_type", 2, "") or ""),
            "pattern_text": str(_row_value(row, "pattern_text", 3, "") or ""),
            "version": str(_row_value(row, "version", 4, "") or ""),
            "source_proposal_id": str(_row_value(row, "source_proposal_id", 6, "") or ""),
            "applied_count": 0,
            "result_count": 0,
            "total_items": 0,
            "good": 0,
            "needs_review": 0,
            "fallback": 0,
            "guardrail_failed": 0,
            "pattern_fit": 0,
            "missing_keywords": 0,
            "weak_matches_only": 0,
            "no_keywords": 0,
            "too_long": 0,
            "forbidden_claims": 0,
            "industry_drift": 0,
            "factual_risk": 0,
            "no_gratitude": 0,
            "no_review_detail": 0,
            "empty": 0,
            "seo_score_delta": 0.0,
            "keyword_found_delta": 0,
            "manual_edits": 0,
            "accepted": 0,
            "business_effect_score_total": 0.0,
            "business_effect_positive": 0,
            "business_effect_neutral": 0,
            "business_effect_negative": 0,
        }
    for row in event_rows:
        version_id = str(_row_value(row, "version_id", 0, "") or "")
        summary = by_version.get(version_id)
        if not summary:
            continue
        event_type = str(_row_value(row, "event_type", 1, "") or "")
        metrics = _json_dict(_row_value(row, "metrics_json", 3, {}))
        if event_type == "applied":
            summary["applied_count"] += 1
        elif event_type == "result":
            summary["result_count"] += 1
            for key in (
                "total",
                "good",
                "needs_review",
                "fallback",
                "guardrail_failed",
                "pattern_fit",
                "missing_keywords",
                "weak_matches_only",
                "no_keywords",
                "too_long",
                "forbidden_claims",
                "industry_drift",
                "factual_risk",
                "no_gratitude",
                "no_review_detail",
                "empty",
                "keyword_found_delta",
                "manual_edits",
                "accepted",
            ):
                try:
                    value = int(metrics.get(key) or 0)
                except Exception:
                    value = 0
                if key == "total":
                    summary["total_items"] += value
                else:
                    summary[key] += value
            summary["seo_score_delta"] += _impact_number(metrics.get("seo_score_delta") or 0)
            summary["business_effect_score_total"] += _impact_number(metrics.get("business_effect_score") or 0)
            effect_status = str(metrics.get("business_effect_status") or "").strip()
            if effect_status == "positive":
                summary["business_effect_positive"] += 1
            elif effect_status == "negative":
                summary["business_effect_negative"] += 1
            elif effect_status == "neutral":
                summary["business_effect_neutral"] += 1

    items = list(by_version.values())
    for item in items:
        total_items = max(0, int(item.get("total_items") or 0))
        bad_items = int(item.get("needs_review") or 0)
        item["bad_rate"] = round(bad_items / total_items, 2) if total_items > 0 else 0
        result_count = max(1, int(item.get("result_count") or 0))
        item["business_effect_score"] = round(float(item.get("business_effect_score_total") or 0) / result_count, 3)
        if int(item.get("business_effect_positive") or 0) > int(item.get("business_effect_negative") or 0) and item["business_effect_score"] > 0:
            item["business_effect_status"] = "positive"
        elif int(item.get("business_effect_negative") or 0) > 0 or item["business_effect_score"] < 0:
            item["business_effect_status"] = "negative"
        elif int(item.get("result_count") or 0) > 0:
            item["business_effect_status"] = "neutral"
        else:
            item["business_effect_status"] = "no_data"
        item["suspicious"] = bool(total_items >= 5 and item["bad_rate"] >= 0.35)
    return sorted(items, key=lambda value: (not value.get("suspicious"), -int(value.get("applied_count") or 0)))


def classify_industry_pattern_impact_item(item: dict[str, Any]) -> str:
    total_items = int(item.get("total_items") or 0)
    needs_review = int(item.get("needs_review") or 0)
    applied_count = int(item.get("applied_count") or 0)
    bad_rate = float(item.get("bad_rate") or 0)
    effect_score = float(item.get("business_effect_score") or 0)
    effect_negative = int(item.get("business_effect_negative") or 0)
    effect_positive = int(item.get("business_effect_positive") or 0)
    hard_risks = sum(
        int(item.get(key) or 0)
        for key in ("industry_drift", "factual_risk", "forbidden_claims", "guardrail_failed")
    )
    soft_risks = sum(
        int(item.get(key) or 0)
        for key in ("fallback", "pattern_fit", "missing_keywords", "too_long", "no_review_detail")
    )
    if total_items >= 5 and (bad_rate >= 0.5 or hard_risks >= 2 or effect_score <= -0.4):
        return "disable_candidate"
    if total_items >= 3 and (bad_rate >= 0.35 or soft_risks >= 2 or hard_risks >= 1 or effect_negative > effect_positive):
        return "revise_candidate"
    if total_items >= 5 and needs_review == 0 and applied_count >= 5 and effect_score >= 0:
        return "stable"
    if applied_count > 0:
        return "watch"
    return "no_data"


def build_monthly_industry_pattern_impact_report(conn, *, days: int = 30, limit: int = 50) -> dict[str, Any]:
    items = summarize_industry_pattern_health(conn, days=days, limit=limit)
    totals = {
        "active_patterns": len(items),
        "applied_count": sum(int(item.get("applied_count") or 0) for item in items),
        "result_count": sum(int(item.get("result_count") or 0) for item in items),
        "total_items": sum(int(item.get("total_items") or 0) for item in items),
        "good": sum(int(item.get("good") or 0) for item in items),
        "needs_review": sum(int(item.get("needs_review") or 0) for item in items),
        "fallback": sum(int(item.get("fallback") or 0) for item in items),
        "guardrail_failed": sum(int(item.get("guardrail_failed") or 0) for item in items),
        "missing_keywords": sum(int(item.get("missing_keywords") or 0) for item in items),
        "industry_drift": sum(int(item.get("industry_drift") or 0) for item in items),
        "factual_risk": sum(int(item.get("factual_risk") or 0) for item in items),
        "too_long": sum(int(item.get("too_long") or 0) for item in items),
        "no_review_detail": sum(int(item.get("no_review_detail") or 0) for item in items),
        "seo_score_delta": round(sum(float(item.get("seo_score_delta") or 0) for item in items), 3),
        "keyword_found_delta": sum(int(item.get("keyword_found_delta") or 0) for item in items),
        "manual_edits": sum(int(item.get("manual_edits") or 0) for item in items),
        "accepted": sum(int(item.get("accepted") or 0) for item in items),
        "business_effect_positive": sum(int(item.get("business_effect_positive") or 0) for item in items),
        "business_effect_neutral": sum(int(item.get("business_effect_neutral") or 0) for item in items),
        "business_effect_negative": sum(int(item.get("business_effect_negative") or 0) for item in items),
    }
    result_count = max(1, int(totals.get("result_count") or 0))
    totals["business_effect_score"] = round(
        sum(float(item.get("business_effect_score_total") or 0) for item in items) / result_count,
        3,
    )
    by_type: dict[str, dict[str, Any]] = {}
    by_industry: dict[str, dict[str, Any]] = {}
    for item in items:
        pattern_type = str(item.get("pattern_type") or "unknown")
        bucket = by_type.setdefault(
            pattern_type,
            {
                "applied_count": 0,
                "result_count": 0,
                "total_items": 0,
                "good": 0,
                "needs_review": 0,
            },
        )
        for key in ("applied_count", "result_count", "total_items", "good", "needs_review"):
            bucket[key] += int(item.get(key) or 0)
        bucket["business_effect_score"] = round(
            (float(bucket.get("business_effect_score", 0)) + float(item.get("business_effect_score") or 0)),
            3,
        )
        industry = str(item.get("industry_key") or "unknown")
        industry_bucket = by_industry.setdefault(
            industry,
            {
                "applied_count": 0,
                "result_count": 0,
                "total_items": 0,
                "good": 0,
                "needs_review": 0,
                "business_effect_score": 0.0,
            },
        )
        for key in ("applied_count", "result_count", "total_items", "good", "needs_review"):
            industry_bucket[key] += int(item.get(key) or 0)
        industry_bucket["business_effect_score"] = round(
            float(industry_bucket.get("business_effect_score") or 0) + float(item.get("business_effect_score") or 0),
            3,
        )
    classified_items: list[dict[str, Any]] = []
    for item in items:
        enriched = dict(item)
        enriched["recommendation"] = classify_industry_pattern_impact_item(enriched)
        classified_items.append(enriched)
    problematic = [
        item
        for item in classified_items
        if item.get("recommendation") in {"disable_candidate", "revise_candidate"}
    ]
    problematic = sorted(
        problematic,
        key=lambda value: (
            value.get("recommendation") != "disable_candidate",
            -float(value.get("bad_rate") or 0),
            -int(value.get("needs_review") or 0),
        ),
    )
    stable = sorted(
        [item for item in classified_items if item.get("recommendation") == "stable"],
        key=lambda value: (-int(value.get("applied_count") or 0), str(value.get("industry_key") or "")),
    )
    watch = sorted(
        [item for item in classified_items if item.get("recommendation") == "watch"],
        key=lambda value: -int(value.get("applied_count") or 0),
    )
    effective = sorted(
        [item for item in classified_items if float(item.get("business_effect_score") or 0) > 0 and item.get("recommendation") in {"stable", "watch"}],
        key=lambda value: (-float(value.get("business_effect_score") or 0), -int(value.get("applied_count") or 0)),
    )
    questionable = sorted(
        [item for item in classified_items if item.get("business_effect_status") in {"negative", "no_data"} or item.get("recommendation") in {"disable_candidate", "revise_candidate"}],
        key=lambda value: (
            str(value.get("business_effect_status") or "") != "negative",
            float(value.get("business_effect_score") or 0),
            -float(value.get("bad_rate") or 0),
        ),
    )
    return {
        "period_days": max(1, min(int(days or 30), 365)),
        "totals": totals,
        "by_type": by_type,
        "by_industry": by_industry,
        "problematic": problematic[:10],
        "effective": effective[:10],
        "questionable": questionable[:10],
        "stable": stable[:10],
        "watch": watch[:10],
        "items": classified_items,
    }


def _impact_pattern_short_text(item: dict[str, Any], limit: int = 120) -> str:
    text = " ".join(str(item.get("pattern_text") or "").split())
    if len(text) > limit:
        return text[: max(20, limit - 3)].rstrip() + "..."
    return text


def format_monthly_industry_pattern_impact_report(report: dict[str, Any], *, max_items: int = 5) -> str:
    totals = report.get("totals") or {}
    by_type = report.get("by_type") or {}
    period_days = int(report.get("period_days") or 30)
    lines = [
        "📊 Monthly impact report по active-паттернам",
        f"Период: последние {period_days} дней",
        (
            f"Active-паттернов: {int(totals.get('active_patterns') or 0)}; "
            f"применений: {int(totals.get('applied_count') or 0)}; "
            f"результатов: {int(totals.get('result_count') or 0)}"
        ),
        (
            f"Проверено единиц: {int(totals.get('total_items') or 0)}; "
            f"OK: {int(totals.get('good') or 0)}; "
            f"needs_review: {int(totals.get('needs_review') or 0)}"
        ),
        (
            "Причины: "
            f"fallback {int(totals.get('fallback') or 0)}, "
            f"guardrails {int(totals.get('guardrail_failed') or 0)}, "
            f"missing keys {int(totals.get('missing_keywords') or 0)}, "
            f"drift {int(totals.get('industry_drift') or 0)}, "
            f"facts risk {int(totals.get('factual_risk') or 0)}, "
            f"too long {int(totals.get('too_long') or 0)}, "
            f"no detail {int(totals.get('no_review_detail') or 0)}"
        ),
        (
            "Business effect: "
            f"score {totals.get('business_effect_score', 0)}, "
            f"SEO delta {totals.get('seo_score_delta', 0)}, "
            f"keyword delta {int(totals.get('keyword_found_delta') or 0)}, "
            f"accepted {int(totals.get('accepted') or 0)}, "
            f"manual edits {int(totals.get('manual_edits') or 0)}, "
            f"positive/neutral/negative "
            f"{int(totals.get('business_effect_positive') or 0)}/"
            f"{int(totals.get('business_effect_neutral') or 0)}/"
            f"{int(totals.get('business_effect_negative') or 0)}"
        ),
    ]
    type_lines: list[str] = []
    for key in ("service", "news", "review_reply"):
        bucket = by_type.get(key) or {}
        if not bucket:
            continue
        type_lines.append(
            f"- {key}: применений {int(bucket.get('applied_count') or 0)}, "
            f"OK {int(bucket.get('good') or 0)}, needs_review {int(bucket.get('needs_review') or 0)}, "
            f"effect {bucket.get('business_effect_score', 0)}"
        )
    if type_lines:
        lines.append("По типам:\n" + "\n".join(type_lines))

    problematic = report.get("problematic") or []
    if problematic:
        lines.append("Топ кандидатов на действие:")
        for index, item in enumerate(problematic[:max_items], start=1):
            action = "отключить" if item.get("recommendation") == "disable_candidate" else "на доработку"
            lines.append(
                f"{index}. {item.get('industry_key')} / {item.get('pattern_type')} -> {action}; "
                f"bad rate {item.get('bad_rate')}; needs_review {item.get('needs_review')}; "
                f"{_impact_pattern_short_text(item)}"
            )
    else:
        lines.append("Кандидатов на отключение/доработку по текущему периоду нет.")

    stable = report.get("stable") or []
    if stable:
        lines.append("Стабильные паттерны:")
        for index, item in enumerate(stable[:max_items], start=1):
            lines.append(
                f"{index}. {item.get('industry_key')} / {item.get('pattern_type')}; "
                f"применений {item.get('applied_count')}; {_impact_pattern_short_text(item)}"
            )
    effective = report.get("effective") or []
    if effective:
        lines.append("Эффективные по business effect:")
        for index, item in enumerate(effective[:max_items], start=1):
            lines.append(
                f"{index}. {item.get('industry_key')} / {item.get('pattern_type')}; "
                f"effect {item.get('business_effect_score')}; accepted {item.get('accepted', 0)}; "
                f"{_impact_pattern_short_text(item)}"
            )
    questionable = report.get("questionable") or []
    if questionable:
        lines.append("Сомнительные по business effect:")
        for index, item in enumerate(questionable[:max_items], start=1):
            lines.append(
                f"{index}. {item.get('industry_key')} / {item.get('pattern_type')}; "
                f"effect {item.get('business_effect_score')}; status {item.get('business_effect_status')}; "
                f"{_impact_pattern_short_text(item)}"
            )
    lines.append("Ничего не применяется автоматически. Решение принимает суперадмин.")
    return "\n".join(lines)


def _impact_metric_reason_labels(metrics: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    reason_map = {
        "fallback": "fallback",
        "guardrail_failed": "guardrails",
        "pattern_fit": "pattern_fit",
        "missing_keywords": "missing keywords",
        "weak_matches_only": "weak matches only",
        "no_keywords": "no keywords",
        "too_long": "too long",
        "forbidden_claims": "forbidden claims",
        "industry_drift": "industry drift",
        "factual_risk": "facts risk",
        "no_gratitude": "no gratitude",
        "no_review_detail": "no review detail",
        "empty": "empty",
    }
    for key, label in reason_map.items():
        try:
            value = int(metrics.get(key) or 0)
        except Exception:
            value = 0
        if value > 0:
            labels.append(label)
    return labels


def _impact_event_to_detail(row: Any) -> dict[str, Any]:
    metrics = _json_dict(_row_value(row, "metrics_json", 4, {}))
    return {
        "id": str(_row_value(row, "id", 0, "") or ""),
        "source": str(_row_value(row, "source", 1, "") or ""),
        "event_type": str(_row_value(row, "event_type", 2, "") or ""),
        "result_status": str(_row_value(row, "result_status", 3, "") or ""),
        "metrics": metrics,
        "created_at": str(_row_value(row, "created_at", 5, "") or ""),
        "reasons": _impact_metric_reason_labels(metrics),
        "sample_text": str(metrics.get("sample_text") or "").strip(),
        "source_excerpt": str(metrics.get("source_excerpt") or "").strip(),
    }


def summarize_industry_pattern_detail_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "applied_count": 0,
        "result_count": 0,
        "total_items": 0,
        "good": 0,
        "needs_review": 0,
        "fallback": 0,
        "guardrail_failed": 0,
        "missing_keywords": 0,
        "industry_drift": 0,
        "factual_risk": 0,
        "bad_rate": 0,
    }
    for event in events or []:
        event_type = str(event.get("event_type") or "")
        metrics = event.get("metrics") or {}
        if event_type == "applied":
            summary["applied_count"] += 1
            continue
        if event_type != "result":
            continue
        summary["result_count"] += 1
        summary["total_items"] += int(metrics.get("total") or 0)
        summary["good"] += int(metrics.get("good") or 0)
        summary["needs_review"] += int(metrics.get("needs_review") or 0)
        summary["fallback"] += int(metrics.get("fallback") or 0)
        summary["guardrail_failed"] += int(metrics.get("guardrail_failed") or 0)
        summary["missing_keywords"] += int(metrics.get("missing_keywords") or 0)
        summary["industry_drift"] += int(metrics.get("industry_drift") or 0)
        summary["factual_risk"] += int(metrics.get("factual_risk") or 0)
    total_items = int(summary.get("total_items") or 0)
    if total_items:
        summary["bad_rate"] = round(float(summary.get("needs_review") or 0) / total_items, 3)
    return summary


def compare_industry_pattern_version_texts(current_text: str, target_text: str) -> dict[str, Any]:
    current_clean = " ".join(str(current_text or "").split())
    target_clean = " ".join(str(target_text or "").split())
    current_words = [word for word in normalize_pattern_text(current_clean).split() if word not in STOP_WORDS]
    target_words = [word for word in normalize_pattern_text(target_clean).split() if word not in STOP_WORDS]
    current_set = set(current_words)
    target_set = set(target_words)
    removed = sorted(current_set - target_set)[:10]
    added = sorted(target_set - current_set)[:10]
    common_count = len(current_set & target_set)
    union_count = len(current_set | target_set)
    similarity = round(common_count / union_count, 3) if union_count else 1
    return {
        "current_length": len(current_clean),
        "target_length": len(target_clean),
        "length_delta": len(target_clean) - len(current_clean),
        "added_terms": added,
        "removed_terms": removed,
        "similarity": similarity,
        "same_text": current_clean == target_clean,
    }


def get_industry_pattern_detail_card(
    conn,
    *,
    version_id: str,
    days: int = 30,
    event_limit: int = 20,
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, industry_key, pattern_type, pattern_text, examples_json,
               source_proposal_id, version, status, activated_by, activated_at,
               disabled_at, created_at
        FROM industry_pattern_versions
        WHERE id = %s
        LIMIT 1
        """,
        (version_id,),
    )
    version_row = cursor.fetchone()
    if not version_row:
        raise ValueError("pattern version not found")
    version = {
        "version_id": str(_row_value(version_row, "id", 0, "") or ""),
        "industry_key": str(_row_value(version_row, "industry_key", 1, "") or ""),
        "pattern_type": str(_row_value(version_row, "pattern_type", 2, "") or ""),
        "pattern_text": str(_row_value(version_row, "pattern_text", 3, "") or ""),
        "examples": _row_value(version_row, "examples_json", 4, []) or [],
        "source_proposal_id": str(_row_value(version_row, "source_proposal_id", 5, "") or ""),
        "version": str(_row_value(version_row, "version", 6, "") or ""),
        "status": str(_row_value(version_row, "status", 7, "") or ""),
        "activated_by": str(_row_value(version_row, "activated_by", 8, "") or ""),
        "activated_at": str(_row_value(version_row, "activated_at", 9, "") or ""),
        "disabled_at": str(_row_value(version_row, "disabled_at", 10, "") or ""),
        "created_at": str(_row_value(version_row, "created_at", 11, "") or ""),
    }

    cursor.execute(
        """
        SELECT id, source, event_type, result_status, metrics_json, created_at
        FROM industry_pattern_impact_events
        WHERE version_id = %s
          AND created_at >= NOW() - INTERVAL '1 day' * %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (
            version_id,
            max(1, min(int(days or 30), 365)),
            max(1, min(int(event_limit or 20), 100)),
        ),
    )
    events = [_impact_event_to_detail(row) for row in cursor.fetchall() or []]
    result_events = [event for event in events if event.get("event_type") == "result"]
    good_examples = [
        event
        for event in result_events
        if str(event.get("result_status") or "") == "good" and str(event.get("sample_text") or "").strip()
    ][:3]
    bad_examples = [
        event
        for event in result_events
        if str(event.get("result_status") or "") != "good" and str(event.get("sample_text") or "").strip()
    ][:3]
    recent_reasons: list[str] = []
    for event in result_events:
        for reason in event.get("reasons") or []:
            if reason not in recent_reasons:
                recent_reasons.append(reason)

    source_proposal_id = str(version.get("source_proposal_id") or "").strip()
    proposal_ids = [item for item in (source_proposal_id, version_id) if item]
    cursor.execute(
        """
        SELECT id
        FROM industry_pattern_proposals
        WHERE activated_version_id = %s
           OR source_counts_json::text LIKE %s
        LIMIT 20
        """,
        (version_id, f"%{version_id}%"),
    )
    for row in cursor.fetchall() or []:
        proposal_id = str(_row_value(row, "id", 0, "") or "")
        if proposal_id and proposal_id not in proposal_ids:
            proposal_ids.append(proposal_id)

    decisions: list[dict[str, Any]] = []
    if proposal_ids:
        placeholders = ", ".join(["%s"] * len(proposal_ids))
        cursor.execute(
            f"""
            SELECT id, proposal_id, decision, decided_by, decision_comment, created_at
            FROM industry_pattern_decisions
            WHERE proposal_id IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT 10
            """,
            proposal_ids,
        )
        for row in cursor.fetchall() or []:
            decisions.append(
                {
                    "id": str(_row_value(row, "id", 0, "") or ""),
                    "proposal_id": str(_row_value(row, "proposal_id", 1, "") or ""),
                    "decision": str(_row_value(row, "decision", 2, "") or ""),
                    "decided_by": str(_row_value(row, "decided_by", 3, "") or ""),
                    "decision_comment": str(_row_value(row, "decision_comment", 4, "") or ""),
                    "created_at": str(_row_value(row, "created_at", 5, "") or ""),
                }
            )

    health_items = summarize_industry_pattern_health(
        conn,
        industry_key=str(version.get("industry_key") or "all"),
        pattern_type=str(version.get("pattern_type") or "all"),
        days=days,
        limit=20,
    )
    health = next((item for item in health_items if item.get("version_id") == version_id), {})
    if health:
        health["recommendation"] = classify_industry_pattern_impact_item(health)
    cursor.execute(
        """
        SELECT id, industry_key, pattern_type, pattern_text, version, status,
               activated_by, activated_at, disabled_at, created_at
        FROM industry_pattern_versions
        WHERE industry_key = %s
          AND pattern_type = %s
          AND id <> %s
        ORDER BY COALESCE(activated_at, created_at) DESC, created_at DESC
        LIMIT 8
        """,
        (
            str(version.get("industry_key") or ""),
            str(version.get("pattern_type") or ""),
            version_id,
        ),
    )
    version_candidates: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        candidate_id = str(_row_value(row, "id", 0, "") or "")
        candidate_health = {}
        if candidate_id:
            candidate_health_items = summarize_industry_pattern_health(
                conn,
                industry_key=str(_row_value(row, "industry_key", 1, "") or ""),
                pattern_type=str(_row_value(row, "pattern_type", 2, "") or ""),
                days=days,
                limit=20,
            )
            candidate_health = next((item for item in candidate_health_items if item.get("version_id") == candidate_id), {})
        version_candidates.append(
            {
                "version_id": candidate_id,
                "industry_key": str(_row_value(row, "industry_key", 1, "") or ""),
                "pattern_type": str(_row_value(row, "pattern_type", 2, "") or ""),
                "pattern_text": str(_row_value(row, "pattern_text", 3, "") or ""),
                "version": str(_row_value(row, "version", 4, "") or ""),
                "status": str(_row_value(row, "status", 5, "") or ""),
                "activated_by": str(_row_value(row, "activated_by", 6, "") or ""),
                "activated_at": str(_row_value(row, "activated_at", 7, "") or ""),
                "disabled_at": str(_row_value(row, "disabled_at", 8, "") or ""),
                "created_at": str(_row_value(row, "created_at", 9, "") or ""),
                "health": candidate_health,
            }
        )
    return {
        "version": version,
        "health": health,
        "events": events,
        "good_examples": good_examples,
        "bad_examples": bad_examples,
        "recent_reasons": recent_reasons,
        "decisions": decisions,
        "version_candidates": version_candidates,
        "period_days": max(1, min(int(days or 30), 365)),
    }


def get_industry_pattern_rollback_preview(
    conn,
    *,
    current_version_id: str,
    target_version_id: str,
    days: int = 30,
) -> dict[str, Any]:
    current_id = str(current_version_id or "").strip()
    target_id = str(target_version_id or "").strip()
    if not current_id:
        raise ValueError("current active version is required for rollback preview")
    if not target_id:
        raise ValueError("target version is required for rollback preview")
    current_detail = get_industry_pattern_detail_card(conn, version_id=current_id, days=days, event_limit=30)
    target_detail = get_industry_pattern_detail_card(conn, version_id=target_id, days=days, event_limit=30)
    current_version = current_detail.get("version") or {}
    target_version = target_detail.get("version") or {}
    same_scope = (
        str(current_version.get("industry_key") or "") == str(target_version.get("industry_key") or "")
        and str(current_version.get("pattern_type") or "") == str(target_version.get("pattern_type") or "")
    )
    current_active = (
        str(current_version.get("status") or "") == "active"
        and not str(current_version.get("disabled_at") or "").strip()
    )
    target_status = str(target_version.get("status") or "")
    target_disabled = bool(str(target_version.get("disabled_at") or "").strip())
    current_health = current_detail.get("health") or summarize_industry_pattern_detail_events(current_detail.get("events") or [])
    target_health = target_detail.get("health") or summarize_industry_pattern_detail_events(target_detail.get("events") or [])
    warnings: list[str] = []
    if not same_scope:
        warnings.append("rollback_scope_mismatch")
    if not current_active:
        warnings.append("current_not_active")
    if target_status == "disabled" or target_disabled:
        warnings.append("target_is_disabled")
    if current_id == target_id:
        warnings.append("same_version")
    confirmation_token = f"rollback:{current_id}:{target_id}"
    return {
        "current": current_version,
        "target": target_version,
        "current_health": current_health,
        "target_health": target_health,
        "text_diff": compare_industry_pattern_version_texts(
            str(current_version.get("pattern_text") or ""),
            str(target_version.get("pattern_text") or ""),
        ),
        "same_scope": same_scope,
        "can_confirm": same_scope and current_active and current_id != target_id,
        "confirmation_token": confirmation_token,
        "warnings": warnings,
        "period_days": max(1, min(int(days or 30), 365)),
    }


def create_industry_pattern_version_proposal(
    conn,
    *,
    version_id: str,
    decided_by: str,
    reason: str = "",
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, industry_key, pattern_type, pattern_text, examples_json, source_proposal_id, status, disabled_at
        FROM industry_pattern_versions
        WHERE id = %s
        LIMIT 1
        """,
        (version_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("active pattern version not found")
    status = str(_row_value(row, "status", 6, "") or "")
    disabled_at = _row_value(row, "disabled_at", 7)
    if status != "active" or disabled_at is not None:
        raise ValueError("pattern version is not active")

    comment = " ".join(str(reason or "создать новую версию active-паттерна").split())
    proposal_id = str(uuid.uuid4())
    today = date.today()
    current_text = str(_row_value(row, "pattern_text", 3, "") or "")
    proposed_text = build_revised_pattern_text(current_text, comment, 1)
    cursor.execute(
        """
        INSERT INTO industry_pattern_proposals (
            id, industry_key, pattern_type, proposed_pattern, examples_json,
            source_period_start, source_period_end, source_counts_json,
            confidence, risk_level, status, decision_comment, activated_version_id,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, 0.5, 'medium',
                'pending_review', %s, %s, NOW(), NOW())
        """,
        (
            proposal_id,
            _row_value(row, "industry_key", 1),
            _row_value(row, "pattern_type", 2),
            proposed_text,
            json.dumps(_row_value(row, "examples_json", 4, []) or [], ensure_ascii=False),
            today - timedelta(days=30),
            today,
            json.dumps(
                {
                    "versioning": {
                        "source_version_id": version_id,
                        "source_proposal_id": str(_row_value(row, "source_proposal_id", 5, "") or ""),
                        "reason": comment,
                    }
                },
                ensure_ascii=False,
            ),
            comment,
            version_id,
        ),
    )
    cursor.execute(
        """
        INSERT INTO industry_pattern_decisions (
            id, proposal_id, decision, decided_by, decision_comment, created_at
        )
        VALUES (%s, %s, 'create_version_proposal', %s, %s, NOW())
        """,
        (str(uuid.uuid4()), proposal_id, decided_by, comment),
    )
    conn.commit()
    return {
        "version_id": version_id,
        "proposal_id": proposal_id,
        "status": "pending_review",
        "reason": comment,
    }


def rollback_industry_pattern_version(
    conn,
    *,
    target_version_id: str,
    decided_by: str,
    current_version_id: str = "",
    reason: str = "",
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, industry_key, pattern_type, source_proposal_id, status
        FROM industry_pattern_versions
        WHERE id = %s
        LIMIT 1
        """,
        (target_version_id,),
    )
    target_row = cursor.fetchone()
    if not target_row:
        raise ValueError("rollback target version not found")
    industry_key = str(_row_value(target_row, "industry_key", 1, "") or "")
    pattern_type = str(_row_value(target_row, "pattern_type", 2, "") or "")
    current_ids: list[str] = []
    clean_current_version_id = str(current_version_id or "").strip()
    if clean_current_version_id and clean_current_version_id != target_version_id:
        cursor.execute(
            """
            SELECT id
            FROM industry_pattern_versions
            WHERE id = %s
              AND industry_key = %s
              AND pattern_type = %s
              AND status = 'active'
              AND disabled_at IS NULL
            LIMIT 1
            """,
            (clean_current_version_id, industry_key, pattern_type),
        )
        current_row = cursor.fetchone()
        if current_row:
            current_ids = [str(_row_value(current_row, "id", 0, "") or "")]
    comment = " ".join(str(reason or "rollback active pattern version").split())
    if current_ids:
        cursor.execute(
            """
            UPDATE industry_pattern_versions
            SET status = 'disabled',
                disabled_at = NOW()
            WHERE id = ANY(%s)
            """,
            (current_ids,),
        )
    cursor.execute(
        """
        UPDATE industry_pattern_versions
        SET status = 'active',
            disabled_at = NULL,
            activated_by = %s,
            activated_at = NOW()
        WHERE id = %s
        """,
        (decided_by, target_version_id),
    )
    decision_ref = str(_row_value(target_row, "source_proposal_id", 3, "") or target_version_id)
    cursor.execute(
        """
        INSERT INTO industry_pattern_decisions (
            id, proposal_id, decision, decided_by, decision_comment, created_at
        )
        VALUES (%s, %s, 'rollback_activate', %s, %s, NOW())
        """,
        (
            str(uuid.uuid4()),
            decision_ref,
            decided_by,
            f"{comment}; target_version={target_version_id}; disabled_versions={','.join(current_ids)}",
        ),
    )
    cursor.execute(
        """
        INSERT INTO industry_pattern_impact_events (
            id, version_id, industry_key, pattern_type, business_id, user_id,
            source, event_type, result_status, metrics_json, created_at
        )
        VALUES (%s, %s, %s, %s, NULL, %s, 'telegram_hitl', 'admin_rollback',
                'active', %s::jsonb, NOW())
        """,
        (
            str(uuid.uuid4()),
            target_version_id,
            industry_key,
            pattern_type,
            decided_by,
            json.dumps(
                {
                    "reason": comment,
                    "target_version_id": target_version_id,
                    "current_version_id": clean_current_version_id,
                    "disabled_versions": current_ids,
                },
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()
    return {
        "target_version_id": target_version_id,
        "disabled_versions": current_ids,
        "status": "active",
        "reason": comment,
    }


def mark_industry_pattern_version_for_revision(
    conn,
    *,
    version_id: str,
    decided_by: str,
    reason: str = "",
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, industry_key, pattern_type, pattern_text, examples_json, source_proposal_id, status, disabled_at
        FROM industry_pattern_versions
        WHERE id = %s
        LIMIT 1
        """,
        (version_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("active pattern version not found")
    status = str(_row_value(row, "status", 6, "") or "")
    disabled_at = _row_value(row, "disabled_at", 7)
    if status != "active" or disabled_at is not None:
        raise ValueError("pattern version is not active")

    comment = " ".join(str(reason or "monthly impact report: needs revision").split())
    proposal_id = str(uuid.uuid4())
    today = date.today()
    cursor.execute(
        """
        INSERT INTO industry_pattern_proposals (
            id, industry_key, pattern_type, proposed_pattern, examples_json,
            source_period_start, source_period_end, source_counts_json,
            confidence, risk_level, status, reviewed_by, reviewed_at, decision_comment,
            activated_version_id, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, 0.5, 'medium',
                'needs_revision', %s, NOW(), %s, %s, NOW(), NOW())
        """,
        (
            proposal_id,
            _row_value(row, "industry_key", 1),
            _row_value(row, "pattern_type", 2),
            _row_value(row, "pattern_text", 3),
            json.dumps(_row_value(row, "examples_json", 4, []) or [], ensure_ascii=False),
            today - timedelta(days=30),
            today,
            json.dumps(
                {
                    "impact_revision": {
                        "source_version_id": version_id,
                        "source_proposal_id": str(_row_value(row, "source_proposal_id", 5, "") or ""),
                        "reason": comment,
                    }
                },
                ensure_ascii=False,
            ),
            decided_by,
            comment,
            version_id,
        ),
    )
    cursor.execute(
        """
        INSERT INTO industry_pattern_decisions (
            id, proposal_id, decision, decided_by, decision_comment, created_at
        )
        VALUES (%s, %s, 'active_needs_revision', %s, %s, NOW())
        """,
        (str(uuid.uuid4()), proposal_id, decided_by, comment),
    )
    conn.commit()
    return {
        "version_id": version_id,
        "proposal_id": proposal_id,
        "status": "needs_revision",
        "reason": comment,
    }


def build_revised_pattern_text(pattern_text: str, revision_comment: str, attempt: int) -> str:
    base = " ".join(str(pattern_text or "").split())
    comment = " ".join(str(revision_comment or "").split())
    if not comment:
        comment = "уточнить формулировку и приложить более явные примеры"
    prefix = f"Уточненная версия {max(1, int(attempt or 1))}: "
    suffix = (
        f" Учитывать замечание суперадмина: {comment}. "
        "Оставить только проверяемый паттерн, подтвержденный примерами; без общих советов и автоприменения."
    )
    return f"{prefix}{base}{suffix}"


def regenerate_industry_pattern_revision(
    conn,
    *,
    proposal_id: str,
    decided_by: str,
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, industry_key, pattern_type, proposed_pattern, examples_json,
               source_period_start, source_period_end, source_counts_json,
               confidence, risk_level, status, decision_comment
        FROM industry_pattern_proposals
        WHERE id = %s
        LIMIT 1
        """,
        (proposal_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("proposal not found")
    status = str(_row_value(row, "status", 10, "") or "")
    if status != "needs_revision":
        raise ValueError("proposal is not needs_revision")

    source_counts = _json_dict(_row_value(row, "source_counts_json", 7, {}))
    revision_meta = _json_dict(source_counts.get("revision"))
    attempt = int(revision_meta.get("attempt") or 0) + 1
    if attempt > MAX_REVISION_ATTEMPTS:
        cursor.execute(
            """
            UPDATE industry_pattern_proposals
            SET status = 'manual_review',
                updated_at = NOW()
            WHERE id = %s
            """,
            (proposal_id,),
        )
        cursor.execute(
            """
            INSERT INTO industry_pattern_decisions (
                id, proposal_id, decision, decided_by, decision_comment, created_at
            )
            VALUES (%s, %s, 'manual_review', %s, %s, NOW())
            """,
            (
                str(uuid.uuid4()),
                proposal_id,
                decided_by,
                "revision attempts exceeded",
            ),
        )
        conn.commit()
        return {
            "proposal_id": proposal_id,
            "status": "manual_review",
            "created_proposal_id": "",
            "attempt": attempt,
        }

    revision_comment = str(_row_value(row, "decision_comment", 11, "") or "").strip()
    new_pattern_text = build_revised_pattern_text(
        str(_row_value(row, "proposed_pattern", 3, "") or ""),
        revision_comment,
        attempt,
    )
    new_source_counts = dict(source_counts)
    new_source_counts["revision"] = {
        "parent_proposal_id": proposal_id,
        "root_proposal_id": revision_meta.get("root_proposal_id") or proposal_id,
        "attempt": attempt,
        "reason": revision_comment,
    }
    new_proposal_id = str(uuid.uuid4())
    confidence = float(_row_value(row, "confidence", 8, 0) or 0)
    cursor.execute(
        """
        INSERT INTO industry_pattern_proposals (
            id, industry_key, pattern_type, proposed_pattern, examples_json,
            source_period_start, source_period_end, source_counts_json,
            confidence, risk_level, status, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, 'pending_review', NOW(), NOW())
        """,
        (
            new_proposal_id,
            _row_value(row, "industry_key", 1),
            _row_value(row, "pattern_type", 2),
            new_pattern_text,
            json.dumps(_row_value(row, "examples_json", 4, []) or [], ensure_ascii=False),
            _row_value(row, "source_period_start", 5),
            _row_value(row, "source_period_end", 6),
            json.dumps(new_source_counts, ensure_ascii=False),
            max(0.1, round(confidence - 0.05, 2)),
            "medium",
        ),
    )
    cursor.execute(
        """
        UPDATE industry_pattern_proposals
        SET status = 'revision_generated',
            activated_version_id = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (new_proposal_id, proposal_id),
    )
    cursor.execute(
        """
        INSERT INTO industry_pattern_decisions (
            id, proposal_id, decision, decided_by, decision_comment, created_at
        )
        VALUES (%s, %s, 'regenerate_revision', %s, %s, NOW())
        """,
        (str(uuid.uuid4()), proposal_id, decided_by, revision_comment),
    )
    conn.commit()
    return {
        "proposal_id": proposal_id,
        "status": "revision_generated",
        "created_proposal_id": new_proposal_id,
        "attempt": attempt,
    }


def disable_industry_pattern_version(
    conn,
    *,
    version_id: str,
    decided_by: str,
    reason: str = "",
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, source_proposal_id, status, disabled_at
        FROM industry_pattern_versions
        WHERE id = %s
        LIMIT 1
        """,
        (version_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("active pattern version not found")
    status = str(_row_value(row, "status", 2, "") or "")
    disabled_at = _row_value(row, "disabled_at", 3)
    if status != "active" or disabled_at is not None:
        raise ValueError("pattern version is not active")

    source_proposal_id = str(_row_value(row, "source_proposal_id", 1, "") or "").strip()
    audit_ref = source_proposal_id or version_id
    comment = " ".join(str(reason or "disabled by superadmin").split())
    cursor.execute(
        """
        UPDATE industry_pattern_versions
        SET status = 'disabled',
            disabled_at = NOW()
        WHERE id = %s
        """,
        (version_id,),
    )
    cursor.execute(
        """
        INSERT INTO industry_pattern_decisions (
            id, proposal_id, decision, decided_by, decision_comment, created_at
        )
        VALUES (%s, %s, 'disable_active', %s, %s, NOW())
        """,
        (str(uuid.uuid4()), audit_ref, decided_by, comment),
    )
    conn.commit()
    return {
        "version_id": version_id,
        "status": "disabled",
        "source_proposal_id": source_proposal_id,
        "reason": comment,
    }


def decide_industry_pattern_proposal(
    conn,
    *,
    proposal_id: str,
    decision: str,
    decided_by: str,
    decision_comment: str = "",
) -> dict[str, Any]:
    ensure_industry_pattern_tables(conn)
    normalized_decision = normalize_pattern_text(decision)
    if normalized_decision not in {"accept", "reject", "revise"}:
        raise ValueError("decision must be accept, reject, or revise")

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, industry_key, pattern_type, proposed_pattern, examples_json, status
        FROM industry_pattern_proposals
        WHERE id = %s
        LIMIT 1
        """,
        (proposal_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("proposal not found")
    status = str(_row_value(row, "status", 5, "") or "")
    if status != "pending_review":
        raise ValueError("proposal is not pending_review")

    activated_version_id = ""
    next_status = "rejected" if normalized_decision == "reject" else "needs_revision"
    if normalized_decision == "accept":
        activated_version_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO industry_pattern_versions (
                id, industry_key, pattern_type, pattern_text, examples_json,
                source_proposal_id, version, status, activated_by, activated_at, created_at
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, 'active', %s, NOW(), NOW())
            """,
            (
                activated_version_id,
                _row_value(row, "industry_key", 1),
                _row_value(row, "pattern_type", 2),
                _row_value(row, "proposed_pattern", 3),
                json.dumps(_row_value(row, "examples_json", 4, []) or [], ensure_ascii=False),
                proposal_id,
                date.today().isoformat(),
                decided_by,
            ),
        )
        next_status = "accepted"

    decision_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO industry_pattern_decisions (
            id, proposal_id, decision, decided_by, decision_comment, created_at
        )
        VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (decision_id, proposal_id, normalized_decision, decided_by, decision_comment),
    )
    cursor.execute(
        """
        UPDATE industry_pattern_proposals
        SET status = %s,
            reviewed_by = %s,
            reviewed_at = NOW(),
            decision_comment = %s,
            activated_version_id = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (next_status, decided_by, decision_comment, activated_version_id or None, proposal_id),
    )
    conn.commit()
    return {
        "proposal_id": proposal_id,
        "decision": normalized_decision,
        "status": next_status,
        "activated_version_id": activated_version_id,
    }
