from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from psycopg2.extras import Json, RealDictCursor

from services.creator_catalog_service import canonical_creator_url, creator_platform, upsert_creator_catalog_entity
from services.lead_workstream_service import CREATOR_COLLABORATION, create_workstream


SCORING_VERSION = "creator-fit-v3"
TRUE_VALUES = {"1", "true", "yes", "on"}
SEARCH_RESULT_GROUPS = {
    "best_fit",
    "strong_local",
    "precise_small_audience",
    "needs_review",
    "insufficient_data",
    "excluded",
}
COLLABORATION_STATUSES = {
    "draft", "invited", "replied", "negotiating", "agreed", "visit_scheduled",
    "awaiting_content", "published", "measuring", "completed", "declined",
    "no_reply", "rescheduled", "overdue", "disputed", "stopped",
}
DELIVERABLE_VERIFICATION_STATUSES = {"expected", "submitted", "verified", "rejected", "overdue"}
MEASUREMENT_CHECKPOINTS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "14d": timedelta(days=14),
}
TOKEN_STOPWORDS = {
    "and", "the", "with", "for", "from", "private", "business", "city", "local",
    "для", "или", "это", "как", "что", "при", "про", "под", "над", "без", "его",
    "ее", "её", "их", "наш", "ваш", "важны", "которым", "жизнь", "городская",
    "получить", "обращения", "люди", "женщины", "жители", "посетители",
}


def creator_feature_state(business_id: str = "") -> dict[str, Any]:
    master = str(os.getenv("PROMOTION_HUB_ENABLED") or "false").strip().lower() in TRUE_VALUES
    discovery = str(os.getenv("INFLUENCER_DISCOVERY_ENABLED") or "false").strip().lower() in TRUE_VALUES
    outreach = str(os.getenv("INFLUENCER_OUTREACH_ENABLED") or "false").strip().lower() in TRUE_VALUES
    metrics = str(os.getenv("INFLUENCER_METRICS_ENABLED") or "false").strip().lower() in TRUE_VALUES
    source_enrichment = str(os.getenv("INFLUENCER_SOURCE_ENRICHMENT_ENABLED") or "false").strip().lower() in TRUE_VALUES
    profile_revalidation_setting = os.getenv("INFLUENCER_PROFILE_REVALIDATION_ENABLED")
    profile_revalidation = (
        str(profile_revalidation_setting).strip().lower() in TRUE_VALUES
        if profile_revalidation_setting is not None
        else source_enrichment
    )
    allowed = {
        item.strip()
        for item in str(os.getenv("INFLUENCER_BUSINESS_IDS") or "").split(",")
        if item.strip()
    }
    eligible = not allowed or str(business_id or "") in allowed
    return {
        "promotion_hub": master and eligible,
        "discovery": master and discovery and eligible,
        "outreach": master and outreach and eligible,
        "metrics": master and metrics and eligible,
        "source_enrichment": source_enrichment,
        "profile_revalidation": profile_revalidation,
        "supported_platforms": ["telegram", "vk", "website", "instagram", "threads", "tiktok", "youtube"],
        "pilot_restricted": bool(allowed),
    }


def _dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _json_ready(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def _tokens(value: Any) -> list[str]:
    text = str(value or "").lower().replace("ё", "е")
    return [
        token
        for token in re.findall(r"[a-zа-я0-9]{3,}", text)
        if token and token not in TOKEN_STOPWORDS
    ]


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _creator_result_limit(brief: dict[str, Any]) -> int:
    try:
        raw_value = brief.get("result_limit")
        requested = 30 if raw_value is None or raw_value == "" else int(raw_value)
    except (TypeError, ValueError):
        requested = 30
    return max(1, min(requested, 100))


def _taxonomy_names(value: Any) -> list[str]:
    return [
        str(item.get("name") or "").strip()
        for item in _json(value, [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]


def _requested_audience_types(brief: dict[str, Any]) -> set[str]:
    text = " ".join([str(brief.get("audience") or ""), *(_text_list(brief.get("audience_types")))]).casefold().replace("ё", "е")
    rules = {
        "parents_and_families": ("родител", "мама", "папа", "семейн", "дети"),
        "food_and_cafe_visitors": ("кафе", "ресторан", "еда", "кофе"),
        "local_residents": ("жител", "локальн", "район", "город"),
        "beauty_and_wellness_audience": ("beauty", "бьюти", "красот", "уход"),
        "travelers": ("турист", "путешеств", "travel"),
    }
    return {name for name, aliases in rules.items() if any(alias in text for alias in aliases)}


def _canonical_url(value: Any) -> str:
    return canonical_creator_url(value)


def _platform_for_url(url: str, fallback: str = "other") -> str:
    return creator_platform(url, fallback)


def _tracking_token(value: Any, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower()).strip("-")
    return normalized[:80] or fallback


def build_tracking_plan(
    payload: dict[str, Any] | None,
    *,
    platform: str,
    campaign_id: str,
    creator_profile_id: str,
) -> dict[str, Any]:
    source = _json(payload, {})
    destination_url = _canonical_url(source.get("destination_url"))
    promo_code = re.sub(r"[^A-ZА-Я0-9_-]+", "", str(source.get("promo_code") or "").strip().upper())[:64]
    cta = str(source.get("cta") or "").strip()[:280]
    plan: dict[str, Any] = {
        "destination_url": destination_url or None,
        "tracked_url": None,
        "utm_source": _tracking_token(source.get("utm_source") or platform, "creator"),
        "utm_medium": _tracking_token(source.get("utm_medium") or "influencer", "influencer"),
        "utm_campaign": _tracking_token(source.get("utm_campaign") or f"creator-{campaign_id[:8]}", "creator-campaign"),
        "utm_content": _tracking_token(source.get("utm_content") or f"creator-{creator_profile_id[:8]}", "creator-placement"),
        "promo_code": promo_code or None,
        "cta": cta or None,
    }
    if destination_url:
        parts = urlsplit(destination_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("Ссылка для отслеживания должна начинаться с http:// или https://")
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update({
            "utm_source": plan["utm_source"],
            "utm_medium": plan["utm_medium"],
            "utm_campaign": plan["utm_campaign"],
            "utm_content": plan["utm_content"],
        })
        plan["tracked_url"] = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    plan["measurement_schedule"] = ["24h", "7d", "14d"]
    return plan


def _ensure_measurement_checkpoints(cursor: Any, *, deliverable_id: str, published_at: datetime) -> None:
    for checkpoint, offset in MEASUREMENT_CHECKPOINTS.items():
        cursor.execute(
            """
            INSERT INTO creator_measurement_checkpoints (id, deliverable_id, checkpoint, due_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (deliverable_id, checkpoint) DO UPDATE SET
                due_at = EXCLUDED.due_at,
                updated_at = NOW()
            WHERE creator_measurement_checkpoints.status = 'pending'
            """,
            (str(uuid.uuid4()), deliverable_id, checkpoint, published_at + offset),
        )


def score_creator_candidate(candidate: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    content_geography_names = _taxonomy_names(candidate.get("content_geographies"))
    audience_geography_names = _taxonomy_names(candidate.get("audience_geography"))
    metro_names = _text_list(candidate.get("metro_stations"))
    audience_types = set(_text_list(candidate.get("audience_types")))
    requested_audience_types = _requested_audience_types(brief)
    content_styles = set(_text_list(candidate.get("content_styles")))
    requested_styles = set(_text_list(brief.get("content_styles")))
    combined = " ".join(
        [
            str(candidate.get("display_name") or ""),
            str(candidate.get("description") or ""),
            " ".join(_text_list(candidate.get("topics"))),
            " ".join(_text_list(candidate.get("evidence_texts"))),
            str(candidate.get("primary_city") or ""),
            str(candidate.get("primary_area") or ""),
            " ".join(content_geography_names),
            " ".join(audience_geography_names),
            " ".join(metro_names),
            " ".join(audience_types),
            " ".join(content_styles),
        ]
    ).lower().replace("ё", "е")
    city = str(brief.get("city") or "").strip().lower().replace("ё", "е")
    area = str(brief.get("area") or brief.get("district") or "").strip().lower().replace("ё", "е")
    audience_tokens = set(_tokens(brief.get("audience")))
    topic_tokens = set(_tokens(" ".join(_text_list(brief.get("topics"))) + " " + str(brief.get("service") or "")))
    combined_tokens = set(_tokens(combined))

    candidate_city = str(candidate.get("primary_city") or "").strip().lower().replace("ё", "е")
    candidate_area = str(candidate.get("primary_area") or "").strip().lower().replace("ё", "е")
    content_geographies = " ".join(content_geography_names).lower().replace("ё", "е")
    audience_geographies = " ".join(audience_geography_names).lower().replace("ё", "е")
    candidate_metros = " ".join(metro_names).lower().replace("ё", "е")
    locality = 0
    locality_reasons: list[str] = []
    if area and audience_geographies and area in audience_geographies:
        locality = 30
        locality_reasons.append(f"Аудитория привязана к району «{brief.get('area') or brief.get('district')}»")
    elif area and (area in content_geographies or area in candidate_metros):
        locality = 30
        locality_reasons.append(f"Есть публичный контент про район «{brief.get('area') or brief.get('district')}»")
    elif area and candidate_area and (area in candidate_area or candidate_area in area):
        locality = 30
        locality_reasons.append(f"Подтверждена базовая связь с районом «{brief.get('area') or brief.get('district')}»")
    elif city and city in audience_geographies:
        locality = 28
        locality_reasons.append(f"Подтверждена аудитория в городе «{brief.get('city')}»")
    elif city and candidate_city and city == candidate_city:
        locality = 24
        locality_reasons.append(f"Подтверждён город автора «{brief.get('city')}»")
    elif city and city in content_geographies:
        locality = 22
        locality_reasons.append(f"Автор публикует материалы про город «{brief.get('city')}»; место жительства не предполагаем")
    elif candidate_city:
        locality = 6
        locality_reasons.append("География указана, но не совпала с заданной")

    audience_matches = audience_tokens.intersection(combined_tokens)
    topic_matches = topic_tokens.intersection(combined_tokens)
    audience_denominator = max(1, len(audience_tokens.union(topic_tokens)))
    audience_fit = min(25, round(25 * len(audience_matches.union(topic_matches)) / audience_denominator))
    if requested_audience_types and requested_audience_types.intersection(audience_types):
        audience_fit = max(audience_fit, 22)

    metrics = _json(candidate.get("public_metrics"), {})
    views = int(metrics.get("median_views") or metrics.get("views") or 0)
    reactions = int(metrics.get("median_reactions") or metrics.get("reactions") or 0)
    engagement = 0
    if views > 0:
        engagement = 8
        if reactions > 0:
            engagement = min(15, 8 + round(7 * min(1, reactions / max(views, 1) / 0.05)))
    elif int(candidate.get("document_count") or 0) >= 8:
        engagement = 7

    desired_formats = set(_text_list(brief.get("formats")))
    candidate_formats = set(_text_list(candidate.get("formats")))
    format_fit = 10 if not desired_formats or desired_formats.intersection(candidate_formats) else 4

    last_observed = candidate.get("last_observed_at")
    freshness = 3
    if isinstance(last_observed, datetime):
        observed = last_observed if last_observed.tzinfo else last_observed.replace(tzinfo=timezone.utc)
        age_days = max(0, (datetime.now(timezone.utc) - observed).days)
        freshness = 10 if age_days <= 30 else 7 if age_days <= 90 else 3 if age_days <= 365 else 0
    elif int(candidate.get("document_count") or 0) > 0:
        freshness = 6

    contactability = str(candidate.get("contactability") or "unknown")
    price_known = candidate.get("price_min") is not None or candidate.get("price_max") is not None
    commercial = 0
    if contactability in {"public_contact", "advertising_contact"}:
        commercial += 6
    elif contactability == "manual_only":
        commercial += 3
    if price_known or candidate.get("accepts_barter") is not None:
        commercial += 4
    commercial = min(10, commercial)

    requested_platforms = set(_text_list(brief.get("platforms")))
    requested_size_bands = set(_text_list(brief.get("audience_size_bands")))
    candidate_platforms = set(_text_list(candidate.get("platforms"))) or {str(candidate.get("platform") or "")}
    contact_required = brief.get("contact_required") is True

    gates = {
        "creator_eligible": candidate.get("creator_eligible") is not False,
        "brand_safety": str(candidate.get("brand_safety_status") or "unknown") != "blocked",
        "active": freshness > 0,
        "contactable": contactability != "not_contactable",
        "geography_known": locality > 0,
        "geography_compatible": not city or locality >= 22,
        "format_compatible": not desired_formats or not candidate_formats or bool(desired_formats.intersection(candidate_formats)),
        "platform_compatible": not requested_platforms or bool(requested_platforms.intersection(candidate_platforms)),
        "content_style_compatible": not requested_styles or bool(requested_styles.intersection(content_styles)),
        "audience_size_compatible": not requested_size_bands or str(candidate.get("audience_size_band") or "unknown") in requested_size_bands,
        "public_contact_available": not contact_required or contactability in {"public_contact", "advertising_contact"} or bool(candidate.get("preferred_contact")),
    }
    score = min(100, locality + audience_fit + engagement + format_fit + freshness + commercial)
    required_gates = (
        "creator_eligible", "brand_safety", "active", "contactable",
        "geography_compatible", "format_compatible", "platform_compatible",
        "content_style_compatible", "audience_size_compatible", "public_contact_available",
    )
    if not all(gates[key] for key in required_gates):
        result_group = "excluded"
    elif score >= 78 and locality >= 24:
        result_group = "best_fit"
    elif score >= 62 and locality >= 20:
        result_group = "strong_local"
    elif score >= 48 and audience_fit >= 12:
        result_group = "precise_small_audience"
    elif locality == 0 or int(candidate.get("document_count") or 0) == 0:
        result_group = "insufficient_data"
    else:
        result_group = "needs_review"
    if result_group not in SEARCH_RESULT_GROUPS:
        result_group = "needs_review"

    reasons = list(locality_reasons)
    if audience_matches or topic_matches:
        matches = sorted(audience_matches.union(topic_matches))[:5]
        reasons.append(f"Совпадают темы: {', '.join(matches)}")
    if requested_audience_types.intersection(audience_types):
        reasons.append("Совпадает тип аудитории")
    if requested_styles.intersection(content_styles):
        reasons.append("Совпадает подача контента")
    if int(candidate.get("document_count") or 0) > 0:
        reasons.append(f"Проанализировано публикаций: {int(candidate.get('document_count') or 0)}")
    if contactability in {"public_contact", "advertising_contact"}:
        reasons.append("Найден публичный способ связи")
    if not reasons:
        reasons.append("Нужно больше публичных данных для уверенной рекомендации")

    return {
        "score": score,
        "result_group": result_group,
        "reasons": reasons,
        "gates": gates,
        "breakdown": {
            "locality": locality,
            "audience_fit": audience_fit,
            "engagement": engagement,
            "format_fit": format_fit,
            "freshness": freshness,
            "commercial_readiness": commercial,
        },
        "scoring_version": SCORING_VERSION,
    }


def _load_business(cursor: Any, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, name, city, address, business_type, industry, categories, website
        FROM businesses WHERE id = %s LIMIT 1
        """,
        (business_id,),
    )
    row = _dict(cursor.fetchone())
    if not row:
        raise LookupError("Бизнес не найден")
    return row


def _search_source_candidates(cursor: Any, anchors: list[str] | None = None, limit: int = 160) -> list[dict[str, Any]]:
    patterns = [f"%{anchor}%" for anchor in (anchors or []) if str(anchor).strip()]
    if not patterns:
        patterns = ["%%"]
    cursor.execute(
        """
        SELECT source.id, source.title, source.canonical_url, source.source_type,
               source.source_role, source.status, source.metadata_json,
               source.last_collected_at,
               COUNT(document.id)::INT AS document_count,
               COUNT(document.id) FILTER (WHERE document.content_text ILIKE ANY(%s))::INT AS relevance_hits,
               MAX(document.published_at) AS latest_document_at,
               STRING_AGG(LEFT(document.content_text, 700), ' ') AS evidence_text
        FROM knowledge_sources source
        LEFT JOIN knowledge_documents document
          ON document.source_id = source.id AND document.invalidated_at IS NULL
        WHERE source.visibility = 'public'
          AND source.sensitivity_class = 'public'
          AND source.status IN ('candidate', 'active')
          AND source.source_type IN ('telegram', 'website', 'vk')
        GROUP BY source.id
        HAVING COUNT(document.id) FILTER (WHERE document.content_text ILIKE ANY(%s)) > 0
            OR source.title ILIKE ANY(%s)
            OR source.metadata_json::text ILIKE ANY(%s)
        ORDER BY COUNT(document.id) FILTER (WHERE document.content_text ILIKE ANY(%s)) DESC,
                 COUNT(document.id) DESC, source.last_collected_at DESC NULLS LAST
        LIMIT %s
        """,
        (patterns, patterns, patterns, patterns, patterns, max(1, min(limit, 500))),
    )
    return [_dict(row) for row in cursor.fetchall()]


def _search_catalog_candidates(
    cursor: Any,
    anchors: list[str] | None = None,
    limit: int = 500,
    brief: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    search_brief = brief or {}
    requested_platforms = _text_list(search_brief.get("platforms"))
    structured_terms = [
        *_requested_audience_types(search_brief),
        *_text_list(search_brief.get("content_styles")),
        *_text_list(search_brief.get("audience_size_bands")),
    ]
    patterns = [f"%{anchor}%" for anchor in [*(anchors or []), *structured_terms] if str(anchor).strip()]
    if not patterns:
        patterns = ["%%"]
    cursor.execute(
        """
        SELECT profile.id, profile.display_name, profile.description,
               COALESCE(taxonomy.home_city, profile.primary_city) AS primary_city,
               COALESCE(taxonomy.home_district, profile.primary_area) AS primary_area,
               profile.topics_json, profile.brand_safety_status,
               profile.metadata_json,
               channel.platform, channel.canonical_url, channel.contactability,
               channel.public_metrics_json, channel.last_observed_at,
               channel.verification_status AS channel_verification_status,
               commercial.formats_json, commercial.accepts_barter,
               commercial.price_min, commercial.price_max, commercial.preferred_contact,
               evidence.evidence_count, evidence.evidence_texts,
               taxonomy.primary_topic, taxonomy.secondary_topics_json,
               taxonomy.content_styles_json, taxonomy.observed_formats_json,
               taxonomy.confirmed_formats_json, taxonomy.metro_stations_json,
               taxonomy.content_geographies_json, taxonomy.audience_geography_json,
               taxonomy.audience_types_json, taxonomy.audience_size_band,
               taxonomy.segment_fit_json, taxonomy.confidence_json,
               taxonomy.evidence_json AS taxonomy_evidence_json,
               taxonomy.classification_status, taxonomy.classification_version,
               profile_channels.platforms
        FROM creator_profiles profile
        JOIN LATERAL (
            SELECT item.* FROM creator_channels item
            WHERE item.creator_profile_id = profile.id
              AND (COALESCE(ARRAY_LENGTH(%s::text[], 1), 0) = 0 OR item.platform = ANY(%s::text[]))
            ORDER BY
                CASE item.verification_status WHEN 'verified' THEN 0 WHEN 'pending' THEN 1 WHEN 'stale' THEN 2 ELSE 3 END,
                item.last_observed_at DESC NULLS LAST,
                item.created_at
            LIMIT 1
        ) channel ON TRUE
        LEFT JOIN LATERAL (
            SELECT ARRAY_AGG(DISTINCT item.platform) AS platforms
            FROM creator_channels item WHERE item.creator_profile_id = profile.id
        ) profile_channels ON TRUE
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
        LEFT JOIN LATERAL (
            SELECT COUNT(item.id)::INT AS evidence_count,
                   COALESCE(ARRAY_AGG(item.summary_text) FILTER (WHERE item.summary_text IS NOT NULL), ARRAY[]::TEXT[]) AS evidence_texts
            FROM creator_evidence item WHERE item.creator_profile_id = profile.id
        ) evidence ON TRUE
        WHERE profile.verification_status <> 'rejected'
          AND (
              profile.display_name ILIKE ANY(%s)
              OR COALESCE(profile.description, '') ILIKE ANY(%s)
              OR COALESCE(profile.primary_city, '') ILIKE ANY(%s)
              OR COALESCE(profile.primary_area, '') ILIKE ANY(%s)
              OR profile.topics_json::text ILIKE ANY(%s)
              OR profile.metadata_json::text ILIKE ANY(%s)
              OR COALESCE(taxonomy.primary_topic, '') ILIKE ANY(%s)
              OR taxonomy.secondary_topics_json::text ILIKE ANY(%s)
              OR taxonomy.content_styles_json::text ILIKE ANY(%s)
              OR taxonomy.content_geographies_json::text ILIKE ANY(%s)
              OR taxonomy.audience_geography_json::text ILIKE ANY(%s)
              OR taxonomy.audience_types_json::text ILIKE ANY(%s)
              OR taxonomy.metro_stations_json::text ILIKE ANY(%s)
          )
        ORDER BY
            CASE channel.verification_status WHEN 'verified' THEN 0 WHEN 'pending' THEN 1 WHEN 'stale' THEN 2 ELSE 3 END,
            evidence.evidence_count DESC,
            channel.last_observed_at DESC NULLS LAST
        LIMIT %s
        """,
        (
            requested_platforms, requested_platforms,
            patterns, patterns, patterns, patterns, patterns, patterns,
            patterns, patterns, patterns, patterns, patterns, patterns, patterns,
            max(1, min(limit, 1000)),
        ),
    )
    candidates: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        item = _dict(row)
        profile_metadata = _json(item.get("metadata_json"), {})
        channel_status = str(item.get("channel_verification_status") or "pending")
        profile_topics = _json(item.get("topics_json"), [])
        taxonomy_topics = [
            str(item.get("primary_topic") or "").strip(),
            *_text_list(_json(item.get("secondary_topics_json"), [])),
        ]
        commercial_formats = _json(item.get("formats_json"), [])
        taxonomy_formats = [
            *_text_list(_json(item.get("observed_formats_json"), [])),
            *_text_list(_json(item.get("confirmed_formats_json"), [])),
        ]
        candidates.append({
            "id": str(item["id"]),
            "display_name": item.get("display_name"),
            "description": item.get("description"),
            "primary_city": item.get("primary_city"),
            "primary_area": item.get("primary_area"),
            "topics": sorted({str(value) for value in [*profile_topics, *taxonomy_topics] if str(value).strip()}),
            "evidence_texts": _text_list(item.get("evidence_texts")),
            "document_count": int(item.get("evidence_count") or 0),
            "public_metrics": _json(item.get("public_metrics_json"), {}),
            "formats": sorted({str(value) for value in [*commercial_formats, *taxonomy_formats] if str(value).strip()}),
            "last_observed_at": item.get("last_observed_at"),
            "contactability": item.get("contactability"),
            "creator_eligible": channel_status not in {"mismatch", "inaccessible", "excluded"},
            "brand_safety_status": item.get("brand_safety_status"),
            "accepts_barter": item.get("accepts_barter"),
            "price_min": item.get("price_min"),
            "price_max": item.get("price_max"),
            "preferred_contact": item.get("preferred_contact"),
            "catalog_source": profile_metadata.get("import_source"),
            "channel_verification_status": channel_status,
            "platform": item.get("platform"),
            "platforms": _text_list(item.get("platforms")),
            "primary_topic": item.get("primary_topic"),
            "content_styles": _json(item.get("content_styles_json"), []),
            "metro_stations": _json(item.get("metro_stations_json"), []),
            "content_geographies": _json(item.get("content_geographies_json"), []),
            "audience_geography": _json(item.get("audience_geography_json"), []),
            "audience_types": _json(item.get("audience_types_json"), []),
            "audience_size_band": item.get("audience_size_band") or "unknown",
            "segment_fit": _json(item.get("segment_fit_json"), {}),
            "taxonomy_confidence": _json(item.get("confidence_json"), {}),
            "taxonomy_evidence": _json(item.get("taxonomy_evidence_json"), []),
            "classification_status": item.get("classification_status"),
            "classification_version": item.get("classification_version"),
        })
    return candidates


def _store_creator_search_candidate(cursor: Any, *, job_id: str, candidate: dict[str, Any], brief: dict[str, Any]) -> None:
    scoring = score_creator_candidate(candidate, brief)
    cursor.execute(
        """
        INSERT INTO creator_search_results (
            id, search_job_id, creator_profile_id, score, score_json,
            reasons_json, gates_json, result_group, scoring_version
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (search_job_id, creator_profile_id) DO UPDATE SET
            score = EXCLUDED.score, score_json = EXCLUDED.score_json,
            reasons_json = EXCLUDED.reasons_json, gates_json = EXCLUDED.gates_json,
            result_group = EXCLUDED.result_group, scoring_version = EXCLUDED.scoring_version,
            updated_at = NOW()
        """,
        (
            str(uuid.uuid4()), job_id, candidate["id"], scoring["score"],
            Json(scoring["breakdown"]), Json(scoring["reasons"]), Json(scoring["gates"]),
            scoring["result_group"], SCORING_VERSION,
        ),
    )


def _creator_from_source(cursor: Any, source: dict[str, Any]) -> dict[str, Any]:
    metadata = _json(source.get("metadata_json"), {})
    canonical_url = _canonical_url(source.get("canonical_url"))
    platform = _platform_for_url(canonical_url, str(source.get("source_type") or "other"))
    cursor.execute(
        """
        SELECT profile.* FROM creator_profiles profile
        JOIN creator_channels channel ON channel.creator_profile_id = profile.id
        WHERE channel.platform = %s AND LOWER(RTRIM(channel.canonical_url, '/')) = LOWER(RTRIM(%s, '/'))
        LIMIT 1
        """,
        (platform, canonical_url),
    )
    existing = _dict(cursor.fetchone())
    profile_id = str(existing.get("id") or uuid.uuid4())
    profile_type = str(metadata.get("creator_profile_type") or "").strip()
    if profile_type not in {"author", "channel", "community", "media", "aggregator"}:
        profile_type = "community" if str(source.get("source_role") or "") == "community" else "channel"
    topics = _text_list(metadata.get("topics") or metadata.get("categories") or metadata.get("keywords"))
    city = str(metadata.get("city") or metadata.get("location_city") or "").strip() or None
    area = str(metadata.get("area") or metadata.get("district") or "").strip() or None
    if existing:
        cursor.execute(
            """
            UPDATE creator_profiles
            SET display_name = %s, description = COALESCE(NULLIF(%s, ''), description),
                primary_city = COALESCE(NULLIF(%s, ''), primary_city),
                primary_area = COALESCE(NULLIF(%s, ''), primary_area),
                topics_json = CASE WHEN %s::jsonb = '[]'::jsonb THEN topics_json ELSE %s::jsonb END,
                metadata_json = metadata_json || %s, updated_at = NOW()
            WHERE id = %s
            """,
            (
                str(source.get("title") or "Локальная площадка"),
                str(metadata.get("description") or ""), city or "", area or "",
                Json(topics), Json(topics), Json({"knowledge_source_id": str(source.get("id") or "")}), profile_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO creator_profiles (
                id, profile_type, display_name, description, primary_city, primary_area,
                languages_json, topics_json, verification_status, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'observed', %s)
            """,
            (
                profile_id, profile_type, str(source.get("title") or "Локальная площадка"),
                str(metadata.get("description") or "") or None, city, area,
                Json(_text_list(metadata.get("languages"))), Json(topics),
                Json({"knowledge_source_id": str(source.get("id") or "")}),
            ),
        )
    contactability = str(metadata.get("contactability") or "unknown")
    if contactability not in {"unknown", "public_contact", "advertising_contact", "manual_only", "not_contactable"}:
        contactability = "unknown"
    channel_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_channels (
            id, creator_profile_id, platform, canonical_url, username, knowledge_source_id,
            contactability, public_metrics_json, metadata_json, last_observed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, %s, NOW()))
        ON CONFLICT (platform, canonical_url) DO UPDATE SET
            creator_profile_id = EXCLUDED.creator_profile_id,
            knowledge_source_id = EXCLUDED.knowledge_source_id,
            contactability = EXCLUDED.contactability,
            public_metrics_json = creator_channels.public_metrics_json || EXCLUDED.public_metrics_json,
            metadata_json = creator_channels.metadata_json || EXCLUDED.metadata_json,
            last_observed_at = EXCLUDED.last_observed_at,
            updated_at = NOW()
        """,
        (
            channel_id, profile_id, platform, canonical_url,
            str(metadata.get("telegram_username") or metadata.get("username") or "") or None,
            source.get("id"), contactability,
            Json(_json(metadata.get("public_metrics"), {})), Json({"source_role": source.get("source_role")}),
            source.get("latest_document_at"), source.get("last_collected_at"),
        ),
    )
    preferred_contact = str(metadata.get("preferred_contact") or "").strip()
    formats = _text_list(metadata.get("formats"))
    if preferred_contact or formats:
        cursor.execute(
            """
            INSERT INTO creator_commercial_profiles (
                id, creator_profile_id, formats_json, preferred_contact,
                confirmation_status, metadata_json
            ) VALUES (%s, %s, %s, NULLIF(%s, ''), 'observed', %s)
            ON CONFLICT (creator_profile_id) DO UPDATE SET
                formats_json = CASE
                    WHEN EXCLUDED.formats_json = '[]'::jsonb THEN creator_commercial_profiles.formats_json
                    ELSE EXCLUDED.formats_json
                END,
                preferred_contact = COALESCE(EXCLUDED.preferred_contact, creator_commercial_profiles.preferred_contact),
                metadata_json = creator_commercial_profiles.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), profile_id, Json(formats), preferred_contact,
                Json({"source": "creator_source_enrichment", "source_id": str(source.get("id") or "")}),
            ),
        )
    evidence_text = str(source.get("evidence_text") or "").strip()
    evidence_summary = f"Публичный источник содержит {int(source.get('document_count') or 0)} доступных публикаций."
    fingerprint = hashlib.sha256(f"{profile_id}:{source.get('id')}:activity".encode("utf-8")).hexdigest()
    cursor.execute(
        """
        SELECT id FROM creator_evidence
        WHERE creator_profile_id = %s AND metadata_json->>'fingerprint' = %s
        LIMIT 1
        """,
        (profile_id, fingerprint),
    )
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO creator_evidence (
                id, creator_profile_id, evidence_type, source_url, source_id,
                summary_text, confidence, observed_at, stale_after, metadata_json
            ) VALUES (%s, %s, 'public_activity', %s, %s, %s, %s,
                      COALESCE(%s, NOW()), COALESCE(%s, NOW()) + INTERVAL '180 days', %s)
            """,
            (
                str(uuid.uuid4()), profile_id, canonical_url, source.get("id"), evidence_summary,
                Decimal("0.75") if int(source.get("document_count") or 0) >= 5 else Decimal("0.55"),
                source.get("latest_document_at"), source.get("last_collected_at"),
                Json({"fingerprint": fingerprint, "document_count": int(source.get("document_count") or 0)}),
            ),
        )
    return {
        "id": profile_id,
        "display_name": str(source.get("title") or "Локальная площадка"),
        "description": str(metadata.get("description") or ""),
        "primary_city": city,
        "primary_area": area,
        "topics": topics,
        "evidence_texts": [evidence_text] if evidence_text else [],
        "document_count": int(source.get("document_count") or 0),
        "public_metrics": _json(metadata.get("public_metrics"), {}),
        "platform": platform,
        "platforms": [platform],
        "formats": formats,
        "last_observed_at": source.get("latest_document_at") or source.get("last_collected_at"),
        "contactability": contactability,
        "creator_eligible": metadata.get("creator_eligible") is not False,
        "brand_safety_status": "unknown",
        "accepts_barter": metadata.get("accepts_barter"),
        "price_min": metadata.get("price_min"),
        "price_max": metadata.get("price_max"),
    }


def enqueue_creator_search(cursor: Any, *, business_id: str, user_id: str, brief: dict[str, Any]) -> dict[str, Any]:
    business = _load_business(cursor, business_id)
    normalized_brief = dict(brief or {})
    normalized_brief.setdefault("city", business.get("city") or "")
    normalized_brief.setdefault("area", business.get("address") or "")
    normalized_brief.setdefault("topics", _text_list(business.get("categories")) or [str(business.get("industry") or business.get("business_type") or "")])
    normalized_brief.setdefault("goal", "Получить локальный охват и обращения")
    normalized_brief["platforms"] = [item.lower() for item in _text_list(normalized_brief.get("platforms"))]
    normalized_brief["result_limit"] = _creator_result_limit(normalized_brief)
    normalized_brief["_business_id"] = business_id
    normalized_brief["_own_urls"] = [url for url in [_canonical_url(business.get("website"))] if url]
    job_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_search_jobs (
            id, business_id, created_by, status, phase, brief_json,
            progress_json, scoring_version, created_at, updated_at
        ) VALUES (%s, %s, NULLIF(%s, ''), 'created', 'setup', %s, %s, %s, NOW(), NOW())
        """,
        (job_id, business_id, user_id, Json(normalized_brief), Json({"found": 0, "processed": 0}), SCORING_VERSION),
    )
    return load_search_job(cursor, business_id=business_id, job_id=job_id)


def process_creator_search_job(cursor: Any, *, business_id: str, job_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT brief_json FROM creator_search_jobs
        WHERE id = %s AND business_id = %s AND status IN ('created', 'searching')
        FOR UPDATE
        """,
        (job_id, business_id),
    )
    job = _dict(cursor.fetchone())
    if not job:
        raise LookupError("Поиск не найден или уже завершён")
    cursor.execute(
        "UPDATE creator_search_jobs SET status = 'searching', phase = 'sources', started_at = COALESCE(started_at, NOW()), updated_at = NOW() WHERE id = %s",
        (job_id,),
    )
    normalized_brief = _json(job.get("brief_json"), {})
    anchors = [
        str(normalized_brief.get("area") or "").strip(),
        str(normalized_brief.get("city") or "").strip(),
        str(normalized_brief.get("service") or "").strip(),
        *_text_list(normalized_brief.get("topics")),
        *_text_list(normalized_brief.get("nearby_places")),
        *_text_list(normalized_brief.get("events")),
        *_text_list(normalized_brief.get("competitors")),
    ]
    active_anchors = [item for item in anchors if item]
    sources = _search_source_candidates(cursor, anchors=active_anchors)
    requested_platforms = set(_text_list(normalized_brief.get("platforms")))
    if requested_platforms:
        sources = [
            source for source in sources
            if _platform_for_url(str(source.get("canonical_url") or ""), str(source.get("source_type") or "other")) in requested_platforms
        ]
    catalog_candidates = _search_catalog_candidates(cursor, anchors=active_anchors, brief=normalized_brief)
    processed = 0
    errors = 0
    for source in sources:
        source_metadata = _json(source.get("metadata_json"), {})
        source_url = _canonical_url(source.get("canonical_url")).lower()
        own_urls = {str(url).lower() for url in _text_list(normalized_brief.get("_own_urls"))}
        if source_url in own_urls or str(source_metadata.get("business_id") or "") == str(normalized_brief.get("_business_id") or ""):
            continue
        cursor.execute("SAVEPOINT creator_candidate")
        try:
            candidate = _creator_from_source(cursor, source)
            _store_creator_search_candidate(cursor, job_id=job_id, candidate=candidate, brief=normalized_brief)
            cursor.execute("RELEASE SAVEPOINT creator_candidate")
            processed += 1
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT creator_candidate")
            cursor.execute("RELEASE SAVEPOINT creator_candidate")
            errors += 1
    for candidate in catalog_candidates:
        cursor.execute("SAVEPOINT creator_catalog_candidate")
        try:
            _store_creator_search_candidate(cursor, job_id=job_id, candidate=candidate, brief=normalized_brief)
            cursor.execute("RELEASE SAVEPOINT creator_catalog_candidate")
            processed += 1
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT creator_catalog_candidate")
            cursor.execute("RELEASE SAVEPOINT creator_catalog_candidate")
            errors += 1
    status = "partial" if errors and processed else "failed" if errors and not processed else "ready"
    cursor.execute(
        """
        UPDATE creator_search_jobs
        SET status = %s, phase = 'ready', progress_json = %s,
            error_json = %s, completed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            Json({"found": len(sources) + len(catalog_candidates), "source_candidates": len(sources), "catalog_candidates": len(catalog_candidates), "processed": processed}),
            Json({"candidate_errors": errors}),
            job_id,
        ),
    )
    return load_search_job(cursor, business_id=business_id, job_id=job_id)


def run_creator_search(cursor: Any, *, business_id: str, user_id: str, brief: dict[str, Any]) -> dict[str, Any]:
    job = enqueue_creator_search(cursor, business_id=business_id, user_id=user_id, brief=brief)
    return process_creator_search_job(cursor, business_id=business_id, job_id=str(job["id"]))


def process_next_creator_search_job() -> dict[str, Any] | None:
    from database_manager import DatabaseManager

    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    job: dict[str, Any] = {}
    try:
        cursor.execute(
            """
            SELECT id, business_id FROM creator_search_jobs
            WHERE status = 'created'
               OR (status = 'searching' AND updated_at < NOW() - INTERVAL '10 minutes')
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        )
        job = _dict(cursor.fetchone())
        if not job:
            db.conn.rollback()
            return None
        cursor.execute(
            "UPDATE creator_search_jobs SET status = 'searching', phase = 'sources', started_at = NOW(), updated_at = NOW() WHERE id = %s",
            (job["id"],),
        )
        db.conn.commit()
        result = process_creator_search_job(cursor, business_id=str(job["business_id"]), job_id=str(job["id"]))
        db.conn.commit()
        return result
    except Exception as exc:
        db.conn.rollback()
        if job:
            cursor.execute(
                """
                UPDATE creator_search_jobs SET status = 'failed', phase = 'ready',
                    error_json = %s, completed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (Json({"error": str(exc)[:1000]}), job["id"]),
            )
            db.conn.commit()
        raise
    finally:
        db.close()


def load_search_job(cursor: Any, *, business_id: str, job_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM creator_search_jobs WHERE id = %s AND business_id = %s", (job_id, business_id))
    job = _dict(cursor.fetchone())
    if not job:
        raise LookupError("Поиск не найден")
    brief = _json(job.get("brief_json"), {})
    result_limit = _creator_result_limit(brief)
    requested_platforms = _text_list(brief.get("platforms"))
    cursor.execute(
        """
        SELECT result.*, profile.display_name, profile.profile_type, profile.description,
               profile.primary_city, profile.primary_area, profile.topics_json,
               profile.verification_status, profile.brand_safety_status,
               channel.id AS channel_id, channel.platform, channel.canonical_url,
               channel.username, channel.contactability, channel.public_metrics_json,
               channel.last_observed_at, channel.verification_status AS channel_verification_status,
               channel.verified_at AS channel_verified_at, channel.next_check_at AS channel_next_check_at,
               channel.verification_note AS channel_verification_note,
               commercial.formats_json, commercial.accepts_barter,
               commercial.price_min, commercial.price_max, commercial.currency,
               commercial.media_kit_url, commercial.preferred_contact,
               taxonomy.primary_topic, taxonomy.secondary_topics_json,
               taxonomy.content_styles_json, taxonomy.observed_formats_json,
               taxonomy.confirmed_formats_json, taxonomy.home_city,
               taxonomy.home_district, taxonomy.metro_stations_json,
               taxonomy.discovery_geography_json, taxonomy.content_geographies_json,
               taxonomy.audience_geography_json, taxonomy.audience_types_json,
               taxonomy.audience_size_band, taxonomy.segment_fit_json,
               taxonomy.confidence_json AS taxonomy_confidence_json,
               taxonomy.evidence_json AS taxonomy_evidence_json,
               taxonomy.classification_status, taxonomy.classification_version,
               evidence.items_json AS evidence_json
        FROM creator_search_results result
        JOIN creator_profiles profile ON profile.id = result.creator_profile_id
        JOIN LATERAL (
            SELECT * FROM creator_channels candidate
            WHERE candidate.creator_profile_id = profile.id
              AND (COALESCE(ARRAY_LENGTH(%s::text[], 1), 0) = 0 OR candidate.platform = ANY(%s::text[]))
            ORDER BY
                CASE candidate.verification_status WHEN 'verified' THEN 0 WHEN 'pending' THEN 1 WHEN 'stale' THEN 2 ELSE 3 END,
                candidate.last_observed_at DESC NULLS LAST,
                candidate.created_at
            LIMIT 1
        ) channel ON TRUE
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
        LEFT JOIN LATERAL (
            SELECT COALESCE(
                JSONB_AGG(
                    JSONB_BUILD_OBJECT(
                        'type', item.evidence_type,
                        'summary', item.summary_text,
                        'source_url', item.source_url,
                        'observed_at', item.observed_at,
                        'stale_after', item.stale_after,
                        'confidence', item.confidence
                    ) ORDER BY item.observed_at DESC NULLS LAST
                ),
                '[]'::jsonb
            ) AS items_json
            FROM creator_evidence item
            WHERE item.creator_profile_id = profile.id
        ) evidence ON TRUE
        WHERE result.search_job_id = %s
        ORDER BY
            CASE result.result_group
                WHEN 'best_fit' THEN 0
                WHEN 'strong_local' THEN 1
                WHEN 'precise_small_audience' THEN 2
                WHEN 'needs_review' THEN 3
                WHEN 'insufficient_data' THEN 4
                ELSE 5
            END,
            result.score DESC,
            profile.display_name
        LIMIT %s
        """,
        (requested_platforms, requested_platforms, job_id, result_limit),
    )
    results: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        item = _dict(row)
        item["topics"] = _json(item.pop("topics_json", []), [])
        item["public_metrics"] = _json(item.pop("public_metrics_json", {}), {})
        item["formats"] = _json(item.pop("formats_json", []), [])
        item["secondary_topics"] = _json(item.pop("secondary_topics_json", []), [])
        item["content_styles"] = _json(item.pop("content_styles_json", []), [])
        item["observed_formats"] = _json(item.pop("observed_formats_json", []), [])
        item["confirmed_formats"] = _json(item.pop("confirmed_formats_json", []), [])
        item["metro_stations"] = _json(item.pop("metro_stations_json", []), [])
        item["discovery_geography"] = _json(item.pop("discovery_geography_json", []), [])
        item["content_geographies"] = _json(item.pop("content_geographies_json", []), [])
        item["audience_geography"] = _json(item.pop("audience_geography_json", []), [])
        item["audience_types"] = _json(item.pop("audience_types_json", []), [])
        item["segment_fit"] = _json(item.pop("segment_fit_json", {}), {})
        item["taxonomy_confidence"] = _json(item.pop("taxonomy_confidence_json", {}), {})
        item["taxonomy_evidence"] = _json(item.pop("taxonomy_evidence_json", []), [])
        item["score_breakdown"] = _json(item.pop("score_json", {}), {})
        item["reasons"] = _json(item.pop("reasons_json", []), [])
        item["gates"] = _json(item.pop("gates_json", {}), {})
        item["evidence"] = _json(item.pop("evidence_json", []), [])
        results.append(_json_ready(item))
    job.pop("brief_json", None)
    job["brief"] = brief
    job["progress"] = _json(job.pop("progress_json", {}), {})
    job["errors"] = _json(job.pop("error_json", {}), {})
    job["results"] = results
    return _json_ready(job)


def list_search_jobs(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT job.*, COUNT(result.id)::INT AS results_count,
               COUNT(result.id) FILTER (WHERE result.shortlist_status = 'shortlisted')::INT AS shortlisted_count
        FROM creator_search_jobs job
        LEFT JOIN creator_search_results result ON result.search_job_id = job.id
        WHERE job.business_id = %s
        GROUP BY job.id
        ORDER BY job.created_at DESC LIMIT 50
        """,
        (business_id,),
    )
    items = []
    for row in cursor.fetchall():
        item = _dict(row)
        item["brief"] = _json(item.pop("brief_json", {}), {})
        item["progress"] = _json(item.pop("progress_json", {}), {})
        item["errors"] = _json(item.pop("error_json", {}), {})
        items.append(_json_ready(item))
    return items


def update_shortlist(cursor: Any, *, business_id: str, result_id: str, status: str) -> dict[str, Any]:
    if status not in {"suggested", "shortlisted", "rejected"}:
        raise ValueError("Недопустимый статус shortlist")
    cursor.execute(
        """
        UPDATE creator_search_results result
        SET shortlist_status = %s, updated_at = NOW()
        FROM creator_search_jobs job
        WHERE result.id = %s AND result.search_job_id = job.id AND job.business_id = %s
        RETURNING result.search_job_id
        """,
        (status, result_id, business_id),
    )
    row = _dict(cursor.fetchone())
    if not row:
        raise LookupError("Кандидат не найден")
    return load_search_job(cursor, business_id=business_id, job_id=str(row["search_job_id"]))


def upsert_manual_creator(cursor: Any, *, business_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _load_business(cursor, business_id)
    name = str(payload.get("display_name") or payload.get("name") or "").strip()
    url = _canonical_url(payload.get("url") or payload.get("canonical_url"))
    if not name or not url:
        raise ValueError("Укажите имя и публичную ссылку")
    platform = _platform_for_url(url, str(payload.get("platform") or "other"))
    cursor.execute(
        """
        SELECT profile.id FROM creator_profiles profile
        JOIN creator_channels channel ON channel.creator_profile_id = profile.id
        WHERE channel.platform = %s AND LOWER(RTRIM(channel.canonical_url, '/')) = LOWER(RTRIM(%s, '/'))
        LIMIT 1
        """,
        (platform, url),
    )
    existing = _dict(cursor.fetchone())
    profile_id = str(existing.get("id") or uuid.uuid4())
    if existing:
        cursor.execute(
            """
            UPDATE creator_profiles SET display_name = %s, description = %s,
                primary_city = %s, primary_area = %s, topics_json = %s,
                metadata_json = metadata_json || %s, updated_at = NOW()
            WHERE id = %s
            """,
            (
                name, str(payload.get("description") or "") or None,
                str(payload.get("city") or "") or None, str(payload.get("area") or "") or None,
                Json(_text_list(payload.get("topics"))), Json({"manual_business_ids": [business_id]}), profile_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO creator_profiles (
                id, profile_type, display_name, description, primary_city, primary_area,
                topics_json, verification_status, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'candidate', %s)
            """,
            (
                profile_id, str(payload.get("profile_type") or "author"), name,
                str(payload.get("description") or "") or None, str(payload.get("city") or "") or None,
                str(payload.get("area") or "") or None, Json(_text_list(payload.get("topics"))),
                Json({"manual_business_ids": [business_id]}),
            ),
        )
    contactability = str(payload.get("contactability") or "manual_only")
    if contactability not in {"unknown", "public_contact", "advertising_contact", "manual_only", "not_contactable"}:
        contactability = "manual_only"
    evidence_items = [item for item in payload.get("evidence_items", []) if isinstance(item, dict)]
    evidence_texts = _text_list(payload.get("evidence"))
    evidence_texts.extend(
        str(item.get("summary") or "").strip()
        for item in evidence_items
        if str(item.get("summary") or "").strip()
    )
    channel_metadata = {
        "added_manually": True,
        "business_id": business_id,
        "provenance_urls": [
            str(item.get("source_url") or "").strip()
            for item in evidence_items
            if str(item.get("source_url") or "").strip()
        ],
    }
    cursor.execute(
        """
        INSERT INTO creator_channels (
            id, creator_profile_id, platform, canonical_url, username, contactability,
            public_metrics_json, metadata_json, last_observed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (platform, canonical_url) DO UPDATE SET
            creator_profile_id = EXCLUDED.creator_profile_id,
            contactability = EXCLUDED.contactability,
            public_metrics_json = creator_channels.public_metrics_json || EXCLUDED.public_metrics_json,
            metadata_json = creator_channels.metadata_json || EXCLUDED.metadata_json,
            last_observed_at = NOW(), updated_at = NOW()
        """,
        (
            str(uuid.uuid4()), profile_id, platform, url, str(payload.get("username") or "") or None,
            contactability, Json(_json(payload.get("public_metrics"), {})), Json(channel_metadata),
        ),
    )
    for evidence in evidence_items:
        source_url = str(evidence.get("source_url") or url).strip()
        summary = str(evidence.get("summary") or "Публичный профиль проверен вручную").strip()
        cursor.execute(
            """
            SELECT id FROM creator_evidence
            WHERE creator_profile_id = %s AND evidence_type = 'manual_public_source'
              AND COALESCE(source_url, '') = %s AND summary_text = %s
            LIMIT 1
            """,
            (profile_id, source_url, summary),
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO creator_evidence (
                id, creator_profile_id, evidence_type, source_url, summary_text,
                confidence, observed_at, stale_after, metadata_json
            ) VALUES (%s, %s, 'manual_public_source', %s, %s, %s, NOW(),
                      NOW() + INTERVAL '90 days', %s)
            """,
            (
                str(uuid.uuid4()), profile_id, source_url, summary,
                float(evidence.get("confidence") or 0.8),
                Json({"added_manually": True, "business_id": business_id}),
            ),
        )
    formats = _text_list(payload.get("formats"))
    preferred_contact = str(payload.get("preferred_contact") or "").strip() or None
    if formats or preferred_contact or payload.get("accepts_barter") is not None or payload.get("price_min") is not None or payload.get("price_max") is not None:
        cursor.execute(
            """
            INSERT INTO creator_commercial_profiles (
                id, creator_profile_id, formats_json, accepts_barter, price_min,
                price_max, currency, media_kit_url, preferred_contact,
                availability_text, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (creator_profile_id) DO UPDATE SET
                formats_json = CASE WHEN EXCLUDED.formats_json = '[]'::jsonb
                                    THEN creator_commercial_profiles.formats_json
                                    ELSE EXCLUDED.formats_json END,
                accepts_barter = COALESCE(EXCLUDED.accepts_barter, creator_commercial_profiles.accepts_barter),
                price_min = COALESCE(EXCLUDED.price_min, creator_commercial_profiles.price_min),
                price_max = COALESCE(EXCLUDED.price_max, creator_commercial_profiles.price_max),
                currency = COALESCE(EXCLUDED.currency, creator_commercial_profiles.currency),
                media_kit_url = COALESCE(EXCLUDED.media_kit_url, creator_commercial_profiles.media_kit_url),
                preferred_contact = COALESCE(EXCLUDED.preferred_contact, creator_commercial_profiles.preferred_contact),
                availability_text = COALESCE(EXCLUDED.availability_text, creator_commercial_profiles.availability_text),
                metadata_json = creator_commercial_profiles.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), profile_id, Json(formats), payload.get("accepts_barter"),
                payload.get("price_min"), payload.get("price_max"),
                str(payload.get("currency") or "RUB"),
                str(payload.get("media_kit_url") or "").strip() or None,
                preferred_contact,
                str(payload.get("availability_text") or "").strip() or None,
                Json({"added_manually": True, "business_id": business_id}),
            ),
        )
    cursor.execute("SELECT * FROM creator_profiles WHERE id = %s", (profile_id,))
    result = _dict(cursor.fetchone())
    result["topics"] = _json(result.pop("topics_json", []), [])
    search_job_id = str(payload.get("search_job_id") or "").strip()
    if search_job_id:
        cursor.execute(
            "SELECT brief_json FROM creator_search_jobs WHERE id = %s AND business_id = %s",
            (search_job_id, business_id),
        )
        job = _dict(cursor.fetchone())
        if not job:
            raise LookupError("Поиск для ручного кандидата не найден")
        scoring = score_creator_candidate(
            {
                "display_name": name,
                "description": payload.get("description"),
                "primary_city": payload.get("city"),
                "primary_area": payload.get("area"),
                "topics": _text_list(payload.get("topics")),
                "evidence_texts": evidence_texts,
                "document_count": max(1, int(payload.get("evidence_count") or len(evidence_items) or len(evidence_texts))) if evidence_texts or evidence_items else 0,
                "public_metrics": _json(payload.get("public_metrics"), {}),
                "formats": _text_list(payload.get("formats")),
                "last_observed_at": datetime.now(timezone.utc),
                "contactability": contactability,
                "brand_safety_status": "unknown",
                "accepts_barter": payload.get("accepts_barter"),
                "price_min": payload.get("price_min"),
                "price_max": payload.get("price_max"),
            },
            _json(job.get("brief_json"), {}),
        )
        cursor.execute(
            """
            INSERT INTO creator_search_results (
                id, search_job_id, creator_profile_id, score, score_json,
                reasons_json, gates_json, result_group, scoring_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (search_job_id, creator_profile_id) DO UPDATE SET
                score = EXCLUDED.score, score_json = EXCLUDED.score_json,
                reasons_json = EXCLUDED.reasons_json, gates_json = EXCLUDED.gates_json,
                result_group = EXCLUDED.result_group, scoring_version = EXCLUDED.scoring_version,
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), search_job_id, profile_id, scoring["score"],
                Json(scoring["breakdown"]), Json(scoring["reasons"]), Json(scoring["gates"]),
                scoring["result_group"], SCORING_VERSION,
            ),
        )
        result["search_job_id"] = search_job_id
    return _json_ready(result)


def import_creator_candidates(cursor: Any, *, business_id: str, candidates: list[dict[str, Any]], search_job_id: str = "") -> dict[str, Any]:
    if not candidates:
        raise ValueError("Файл не содержит кандидатов")
    if len(candidates) > 500:
        raise ValueError("За один импорт можно добавить не более 500 кандидатов")
    imported: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    search_brief: dict[str, Any] = {}
    if search_job_id:
        cursor.execute(
            "SELECT brief_json FROM creator_search_jobs WHERE id = %s AND business_id = %s",
            (search_job_id, business_id),
        )
        search_row = _dict(cursor.fetchone())
        if not search_row:
            raise LookupError("Поиск для импорта не найден")
        search_brief = _json(search_row.get("brief_json"), {})
    for index, candidate in enumerate(candidates):
        cursor.execute("SAVEPOINT creator_import_item")
        try:
            item = dict(candidate)
            if item.get("channels") or item.get("canonical_urls"):
                catalog_result = upsert_creator_catalog_entity(
                    cursor,
                    entity=item,
                    public_contact=item.get("public_contact") if isinstance(item.get("public_contact"), dict) else None,
                    import_source="business_file_import",
                )
                profile_id = str(catalog_result["profile_id"])
                if search_job_id:
                    catalog_candidates = _search_catalog_candidates(
                        cursor,
                        anchors=[str(item.get("display_name") or item.get("name") or "")],
                        limit=50,
                        brief=search_brief,
                    )
                    catalog_candidate = next((entry for entry in catalog_candidates if str(entry.get("id")) == profile_id), None)
                    if not catalog_candidate:
                        raise LookupError("Импортированный профиль не удалось добавить в текущий поиск")
                    _store_creator_search_candidate(cursor, job_id=search_job_id, candidate=catalog_candidate, brief=search_brief)
                imported.append({"id": profile_id, "display_name": item.get("display_name") or item.get("name"), "search_job_id": search_job_id or None})
            else:
                if search_job_id:
                    item["search_job_id"] = search_job_id
                imported.append(upsert_manual_creator(cursor, business_id=business_id, payload=item))
            cursor.execute("RELEASE SAVEPOINT creator_import_item")
        except (LookupError, ValueError) as exc:
            cursor.execute("ROLLBACK TO SAVEPOINT creator_import_item")
            cursor.execute("RELEASE SAVEPOINT creator_import_item")
            errors.append({"row": index + 1, "error": str(exc)})
    return {"imported": imported, "errors": errors, "imported_count": len(imported), "error_count": len(errors)}


def create_campaign(cursor: Any, *, business_id: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _load_business(cursor, business_id)
    title = str(payload.get("title") or "Кампания с локальными авторами").strip()
    goal = str(payload.get("goal") or "Локальный охват и обращения").strip()
    sender_mode = str(payload.get("sender_mode") or "partner_business")
    if sender_mode not in {"partner_business", "localos_for_partner"}:
        raise ValueError("Недопустимый отправитель")
    campaign_id = str(uuid.uuid4())
    search_job_id = str(payload.get("search_job_id") or "").strip() or None
    cursor.execute(
        """
        INSERT INTO creator_campaigns (
            id, business_id, search_job_id, title, goal, sender_mode, audience_json,
            geography_json, formats_json, offer_json, budget_json, period_json,
            constraints_json, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, ''))
        """,
        (
            campaign_id, business_id, search_job_id, title, goal, sender_mode,
            Json(_json(payload.get("audience"), {})), Json(_json(payload.get("geography"), {})),
            Json(_text_list(payload.get("formats"))), Json(_json(payload.get("offer"), {})),
            Json(_json(payload.get("budget"), {})), Json(_json(payload.get("period"), {})),
            Json(_json(payload.get("constraints"), {})), user_id,
        ),
    )
    result_ids = _text_list(payload.get("search_result_ids"))
    if search_job_id:
        if result_ids:
            cursor.execute(
                """
                SELECT * FROM creator_search_results
                WHERE search_job_id = %s AND id = ANY(%s)
                """,
                (search_job_id, result_ids),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM creator_search_results
                WHERE search_job_id = %s AND shortlist_status = 'shortlisted'
                """,
                (search_job_id,),
            )
        for row in cursor.fetchall():
            result = _dict(row)
            cursor.execute(
                """
                INSERT INTO creator_campaign_candidates (
                    id, campaign_id, creator_profile_id, search_result_id,
                    score_snapshot_json, selection_reason
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (campaign_id, creator_profile_id) DO NOTHING
                """,
                (
                    str(uuid.uuid4()), campaign_id, result.get("creator_profile_id"), result.get("id"),
                    Json({"score": result.get("score"), "breakdown": _json(result.get("score_json"), {}), "version": result.get("scoring_version")}),
                    "Добавлен из подтверждённого shortlist",
                ),
            )
    return load_campaign(cursor, business_id=business_id, campaign_id=campaign_id)


def load_campaign(cursor: Any, *, business_id: str, campaign_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM creator_campaigns WHERE id = %s AND business_id = %s", (campaign_id, business_id))
    campaign = _dict(cursor.fetchone())
    if not campaign:
        raise LookupError("Кампания не найдена")
    for key in ("audience_json", "geography_json", "formats_json", "offer_json", "budget_json", "period_json", "constraints_json"):
        campaign[key.removesuffix("_json")] = _json(campaign.pop(key, None), [] if key == "formats_json" else {})
    cursor.execute(
        """
        SELECT candidate.*, profile.display_name, profile.profile_type,
               profile.primary_city, profile.primary_area,
               channel.platform, channel.canonical_url, channel.contactability,
               collaboration.id AS collaboration_id,
               collaboration.status AS collaboration_status
        FROM creator_campaign_candidates candidate
        JOIN creator_profiles profile ON profile.id = candidate.creator_profile_id
        LEFT JOIN LATERAL (
            SELECT * FROM creator_channels item WHERE item.creator_profile_id = profile.id
            ORDER BY item.last_observed_at DESC NULLS LAST LIMIT 1
        ) channel ON TRUE
        LEFT JOIN creator_collaborations collaboration
          ON collaboration.campaign_candidate_id = candidate.id
        WHERE candidate.campaign_id = %s
        ORDER BY candidate.created_at
        """,
        (campaign_id,),
    )
    campaign["candidates"] = [_json_ready(_dict(row)) for row in cursor.fetchall()]
    return _json_ready(campaign)


def list_campaigns(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT campaign.*, COUNT(candidate.id)::INT AS candidates_count,
               COUNT(candidate.id) FILTER (WHERE candidate.status IN ('replied', 'negotiating', 'agreed'))::INT AS engaged_count
        FROM creator_campaigns campaign
        LEFT JOIN creator_campaign_candidates candidate ON candidate.campaign_id = campaign.id
        WHERE campaign.business_id = %s
        GROUP BY campaign.id ORDER BY campaign.updated_at DESC
        """,
        (business_id,),
    )
    rows = [_dict(row) for row in cursor.fetchall()]
    items = []
    for row in rows:
        item = load_campaign(cursor, business_id=business_id, campaign_id=str(row["id"]))
        item["candidates_count"] = int(row.get("candidates_count") or 0)
        item["engaged_count"] = int(row.get("engaged_count") or 0)
        items.append(item)
    return items


def _has_campaign_term(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_campaign_term(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_campaign_term(item) for item in value)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool(value.strip())
    return value not in {None, ""}


def campaign_terms_review(campaign: dict[str, Any]) -> dict[str, Any]:
    offer = _json(campaign.get("offer"), {})
    budget = _json(campaign.get("budget"), {})
    constraints = _json(campaign.get("constraints"), {})
    rights = _json(constraints.get("usage_rights"), {}) or _json(offer.get("usage_rights"), {})
    checks = {
        "format": bool(_text_list(campaign.get("formats"))),
        "compensation": (
            _has_campaign_term(budget)
            or _has_campaign_term(offer.get("compensation"))
            or offer.get("barter") is True
        ),
        "period": _has_campaign_term(_json(campaign.get("period"), {})),
        "usage_rights": _has_campaign_term(rights),
    }
    labels = {
        "format": "формат",
        "compensation": "бюджет или бартер",
        "period": "сроки",
        "usage_rights": "права на материал",
    }
    return {"checks": checks, "missing": [label for key, label in labels.items() if not checks[key]]}


def approve_campaign_terms(cursor: Any, *, business_id: str, campaign_id: str) -> dict[str, Any]:
    campaign = load_campaign(cursor, business_id=business_id, campaign_id=campaign_id)
    review = campaign_terms_review(campaign)
    if review["missing"]:
        raise ValueError(f"Перед подтверждением заполните: {', '.join(review['missing'])}")
    cursor.execute(
        """
        UPDATE creator_campaigns SET status = 'approved', approved_terms_version = terms_version,
            approved_at = NOW(), updated_at = NOW()
        WHERE id = %s AND business_id = %s AND status IN ('draft', 'needs_review', 'paused')
        RETURNING id
        """,
        (campaign_id, business_id),
    )
    if not cursor.fetchone():
        raise ValueError("Кампания не готова к подтверждению")
    return load_campaign(cursor, business_id=business_id, campaign_id=campaign_id)


def update_campaign_terms(cursor: Any, *, business_id: str, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    campaign = load_campaign(cursor, business_id=business_id, campaign_id=campaign_id)
    title = str(payload.get("title") if "title" in payload else campaign.get("title") or "").strip()
    goal = str(payload.get("goal") if "goal" in payload else campaign.get("goal") or "").strip()
    sender_mode = str(payload.get("sender_mode") if "sender_mode" in payload else campaign.get("sender_mode") or "partner_business")
    if not title or not goal:
        raise ValueError("Название и цель кампании обязательны")
    if sender_mode not in {"partner_business", "localos_for_partner"}:
        raise ValueError("Недопустимый отправитель")
    cursor.execute(
        """
        UPDATE creator_campaigns SET
            title = %s, goal = %s, sender_mode = %s,
            audience_json = %s, geography_json = %s, formats_json = %s,
            offer_json = %s, budget_json = %s, period_json = %s,
            constraints_json = %s, terms_version = terms_version + 1,
            approved_terms_version = NULL, approved_at = NULL,
            status = 'needs_review', updated_at = NOW()
        WHERE id = %s AND business_id = %s
        """,
        (
            title, goal, sender_mode,
            Json(_json(payload.get("audience"), campaign.get("audience") or {})),
            Json(_json(payload.get("geography"), campaign.get("geography") or {})),
            Json(_text_list(payload.get("formats")) if "formats" in payload else campaign.get("formats") or []),
            Json(_json(payload.get("offer"), campaign.get("offer") or {})),
            Json(_json(payload.get("budget"), campaign.get("budget") or {})),
            Json(_json(payload.get("period"), campaign.get("period") or {})),
            Json(_json(payload.get("constraints"), campaign.get("constraints") or {})),
            campaign_id, business_id,
        ),
    )
    return load_campaign(cursor, business_id=business_id, campaign_id=campaign_id)


def preview_candidate_outreach(
    cursor: Any,
    *,
    business_id: str,
    campaign_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT candidate.id, candidate.creator_profile_id, candidate.status AS candidate_status,
               candidate.score_snapshot_json,
               campaign.status AS campaign_status, campaign.sender_mode, campaign.goal, campaign.formats_json,
               campaign.offer_json, campaign.budget_json, campaign.period_json,
               campaign.constraints_json,
               profile.display_name, profile.primary_city, profile.primary_area,
               result.reasons_json,
               channel.platform, channel.canonical_url, channel.contactability,
               commercial.preferred_contact, commercial.confirmation_status AS contact_confirmation_status,
               business.name AS business_name, business.city AS business_city,
               business.address AS business_address,
               evidence.summary_text AS evidence_summary,
               evidence.source_url AS evidence_source_url,
               evidence.confidence AS evidence_confidence
        FROM creator_campaign_candidates candidate
        JOIN creator_campaigns campaign ON campaign.id = candidate.campaign_id
        JOIN creator_profiles profile ON profile.id = candidate.creator_profile_id
        JOIN businesses business ON business.id = campaign.business_id
        LEFT JOIN creator_search_results result ON result.id = candidate.search_result_id
        LEFT JOIN LATERAL (
            SELECT * FROM creator_channels item WHERE item.creator_profile_id = profile.id
            ORDER BY item.last_observed_at DESC NULLS LAST LIMIT 1
        ) channel ON TRUE
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        LEFT JOIN LATERAL (
            SELECT item.summary_text, item.source_url, item.confidence
            FROM creator_evidence item
            WHERE item.creator_profile_id = profile.id
            ORDER BY item.confidence DESC, item.observed_at DESC NULLS LAST, item.created_at DESC
            LIMIT 1
        ) evidence ON TRUE
        WHERE candidate.id = %s AND campaign.id = %s AND campaign.business_id = %s
        """,
        (candidate_id, campaign_id, business_id),
    )
    candidate = _dict(cursor.fetchone())
    if not candidate:
        raise LookupError("Кандидат не найден")

    reasons = _json(candidate.get("reasons_json"), [])
    evidence_summary = str(candidate.get("evidence_summary") or "").strip()
    personalization = evidence_summary or next((str(reason).strip() for reason in reasons if str(reason).strip()), "")
    if not personalization:
        personalization = "ваша площадка совпадает с локальной аудиторией нашей кампании"
    personalization = personalization.rstrip(". ")
    formats = _json(candidate.get("formats_json"), [])
    offer = _json(candidate.get("offer_json"), {})
    budget = _json(candidate.get("budget_json"), {})
    period = _json(candidate.get("period_json"), {})
    constraints = _json(candidate.get("constraints_json"), {})
    format_text = ", ".join(_text_list(formats)) or "публикацию или обзор"
    offer_text = str(offer.get("details") or offer.get("service") or "").strip()
    business_city = str(candidate.get("business_city") or "").strip()
    business_address = str(candidate.get("business_address") or "").strip()
    address_markers = (
        "ул.", "улица", "просп", "пр-т", "переул", "наб.", "набереж",
        "шоссе", "бульвар", "площад", "street", "road", "avenue", "tee", "maantee",
    )
    public_address = business_address if (
        any(character.isdigit() for character in business_address)
        or any(marker in business_address.casefold() for marker in address_markers)
    ) else ""
    if public_address and business_city and public_address.casefold().startswith(business_city.casefold()):
        business_location = public_address
    else:
        business_location = ", ".join(item for item in (business_city, public_address) if item)
    representation = str(candidate.get("business_name") or "бизнес")
    if business_location:
        representation += f" ({business_location})"
    goal = str(candidate.get("goal") or "познакомить аудиторию с бизнесом").strip()
    goal_continuation = goal[:1].lower() + goal[1:] if goal else "познакомить аудиторию с бизнесом"
    if str(candidate.get("sender_mode") or "partner_business") == "localos_for_partner":
        message_parts = [
            "Здравствуйте!",
            "Мы в LocalOS помогаем локальным бизнесам находить подходящих авторов для сотрудничества.",
            f"Обратили внимание на «{candidate.get('display_name')}»: {personalization}.",
            "Сейчас собираем актуальные условия, чтобы предлагать авторам только релевантные проекты. Подскажите, пожалуйста, ваши форматы, цены, географию аудитории, свежие охваты и удобный контакт.",
            "Если найдём подходящий бизнес, вернёмся с конкретным брифом; размещение, сроки и права на материал согласуем отдельно.",
        ]
    else:
        message_parts = [
            "Здравствуйте!",
            f"Обратили внимание на «{candidate.get('display_name')}»: {personalization}.",
            f"Мы — {representation}. Ищем локального автора, чтобы {goal_continuation}.",
            f"Предлагаем обсудить формат: {format_text}." + (f" {offer_text.rstrip('.')}.") if offer_text else f"Предлагаем обсудить формат: {format_text}.",
            "Если вам это интересно, сначала отдельно согласуем формат, бюджет, даты и права на материал. До подтверждения ничего публиковать не нужно.",
            "Подскажите, рассматриваете ли вы такие локальные коллаборации?",
        ]
    contact = str(candidate.get("preferred_contact") or "").strip()
    confirmation_status = str(candidate.get("contact_confirmation_status") or "observed")
    candidate_snapshot = _json(candidate.get("score_snapshot_json"), {})
    business_confirmation = _json(candidate_snapshot.get("contact_confirmation"), {})
    if contact and (confirmation_status == "creator_confirmed" or business_confirmation.get("confirmed") is True):
        contact_status = "confirmed"
    elif contact:
        contact_status = "public_unverified"
    elif candidate.get("contactability") in {"public_contact", "advertising_contact"}:
        contact_status = "source_only"
    else:
        contact_status = "missing"
    terms_review = campaign_terms_review({
        "formats": formats,
        "offer": offer,
        "budget": budget,
        "period": period,
        "constraints": constraints,
    })
    checks = {**terms_review["checks"], "contact_confirmed": contact_status == "confirmed"}
    missing_labels = {
        "format": "формат",
        "compensation": "бюджет или бартер",
        "period": "сроки",
        "usage_rights": "права на материал",
        "contact_confirmed": "принадлежность контакта автору",
    }
    return _json_ready({
        "candidate_id": candidate_id,
        "display_name": candidate.get("display_name"),
        "message": "\n\n".join(message_parts),
        "personalization": {
            "summary": personalization,
            "source_url": candidate.get("evidence_source_url"),
            "confidence": candidate.get("evidence_confidence"),
        },
        "contact": {
            "value": contact or None,
            "status": contact_status,
            "source_url": candidate.get("canonical_url"),
        },
        "terms_review": {
            "checks": checks,
            "missing": [label for key, label in missing_labels.items() if not checks[key]],
        },
        "campaign_status": candidate.get("campaign_status"),
        "sender_mode": candidate.get("sender_mode"),
        "requires_campaign_approval": candidate.get("campaign_status") != "approved",
        "writes_performed": 0,
        "external_messages_sent": 0,
    })


def confirm_candidate_contact(
    cursor: Any,
    *,
    business_id: str,
    campaign_id: str,
    candidate_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if payload.get("confirmed") is not True:
        raise ValueError("Подтвердите, что контакт проверен")
    confirmation_note = str(payload.get("confirmation_note") or "").strip()
    if len(confirmation_note) < 10:
        raise ValueError("Добавьте краткое основание проверки контакта")
    cursor.execute(
        """
        SELECT candidate.creator_profile_id, candidate.score_snapshot_json,
               commercial.preferred_contact
        FROM creator_campaign_candidates candidate
        JOIN creator_campaigns campaign ON campaign.id = candidate.campaign_id
        LEFT JOIN creator_commercial_profiles commercial
            ON commercial.creator_profile_id = candidate.creator_profile_id
        WHERE candidate.id = %s AND campaign.id = %s AND campaign.business_id = %s
        """,
        (candidate_id, campaign_id, business_id),
    )
    candidate = _dict(cursor.fetchone())
    if not candidate:
        raise LookupError("Кандидат не найден")
    if not str(candidate.get("preferred_contact") or "").strip():
        raise ValueError("Сначала добавьте публичный контакт автора или его представителя")
    audit_metadata = {
        "confirmed": True,
        "confirmed_by": user_id,
        "note": confirmation_note,
        "source_url": str(payload.get("confirmation_source_url") or "").strip() or None,
        "method": "business_manual_review",
    }
    candidate_snapshot = _json(candidate.get("score_snapshot_json"), {})
    candidate_snapshot["contact_confirmation"] = audit_metadata
    cursor.execute(
        """
        UPDATE creator_campaign_candidates SET
            score_snapshot_json = %s, updated_at = NOW()
        WHERE id = %s AND campaign_id = %s
        """,
        (Json(candidate_snapshot), candidate_id, campaign_id),
    )
    return preview_candidate_outreach(
        cursor,
        business_id=business_id,
        campaign_id=campaign_id,
        candidate_id=candidate_id,
    )


def prepare_candidate_outreach(
    cursor: Any,
    conn: Any,
    *,
    business_id: str,
    campaign_id: str,
    candidate_id: str,
    user_id: str,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT candidate.*, campaign.status AS campaign_status,
               campaign.terms_version AS campaign_terms_version,
               campaign.approved_terms_version AS campaign_approved_terms_version,
               profile.display_name, profile.primary_city,
               channel.platform, channel.canonical_url, channel.contactability,
               commercial.preferred_contact,
               commercial.confirmation_status AS contact_confirmation_status
        FROM creator_campaign_candidates candidate
        JOIN creator_campaigns campaign ON campaign.id = candidate.campaign_id
        JOIN creator_profiles profile ON profile.id = candidate.creator_profile_id
        LEFT JOIN LATERAL (
            SELECT * FROM creator_channels item WHERE item.creator_profile_id = profile.id
            ORDER BY item.last_observed_at DESC NULLS LAST LIMIT 1
        ) channel ON TRUE
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        WHERE candidate.id = %s AND campaign.id = %s AND campaign.business_id = %s
        """,
        (candidate_id, campaign_id, business_id),
    )
    candidate = _dict(cursor.fetchone())
    if not candidate:
        raise LookupError("Кандидат не найден")
    if candidate.get("campaign_status") != "approved":
        raise ValueError("Сначала подтвердите условия кампании")
    if candidate.get("campaign_terms_version") != candidate.get("campaign_approved_terms_version"):
        raise ValueError("Условия изменились и требуют повторного подтверждения")
    preferred_contact = str(candidate.get("preferred_contact") or "").strip()
    candidate_snapshot = _json(candidate.get("score_snapshot_json"), {})
    business_confirmation = _json(candidate_snapshot.get("contact_confirmation"), {})
    contact_confirmed = (
        str(candidate.get("contact_confirmation_status") or "") == "creator_confirmed"
        or business_confirmation.get("confirmed") is True
    )
    if not preferred_contact:
        raise ValueError("Сначала добавьте публичный контакт автора или его представителя")
    if not contact_confirmed:
        raise ValueError("Сначала подтвердите принадлежность контакта")
    source_external_id = f"creator:{candidate['creator_profile_id']}"
    cursor.execute("SELECT id FROM prospectingleads WHERE source_external_id = %s LIMIT 1", (source_external_id,))
    existing = _dict(cursor.fetchone())
    lead_id = str(existing.get("id") or uuid.uuid4())
    email = preferred_contact if "@" in preferred_contact and not preferred_contact.startswith(("http", "@")) else None
    telegram_url = None
    lowered_contact = preferred_contact.lower()
    if lowered_contact.startswith(("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/")):
        telegram_url = preferred_contact
    elif preferred_contact.startswith("@") and len(preferred_contact) > 1:
        telegram_url = f"https://t.me/{preferred_contact[1:]}"
    elif str(candidate.get("platform") or "") == "telegram" and str(candidate.get("contactability") or "") == "public_contact":
        telegram_url = str(candidate.get("canonical_url") or "") or None
    if existing:
        cursor.execute(
            """
            UPDATE prospectingleads SET name = %s, city = %s, source_url = %s,
                email = COALESCE(%s, email), telegram_url = COALESCE(%s, telegram_url),
                business_id = %s, intent = 'creator_collaboration', updated_at = NOW()
            WHERE id = %s
            """,
            (
                candidate.get("display_name"), candidate.get("primary_city"), candidate.get("canonical_url"),
                email, telegram_url, business_id, lead_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO prospectingleads (
                id, name, city, source_url, source, source_external_id, category,
                status, email, telegram_url, intent, business_id, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'creator_discovery', %s, 'creator', 'shortlisted',
                      %s, %s, 'creator_collaboration', %s, NOW(), NOW())
            """,
            (
                lead_id, candidate.get("display_name"), candidate.get("primary_city"), candidate.get("canonical_url"),
                source_external_id, email, telegram_url, business_id,
            ),
        )
    workstream = create_workstream(
        conn,
        lead_id=lead_id,
        workstream_type=CREATOR_COLLABORATION,
        client_business_id=business_id,
        actor_id=user_id,
    )
    cursor.execute(
        """
        UPDATE creator_campaign_candidates
        SET lead_id = %s, workstream_id = %s, status = 'invitation_ready', updated_at = NOW()
        WHERE id = %s
        """,
        (lead_id, workstream.get("id"), candidate_id),
    )
    return {
        "lead_id": lead_id,
        "workstream": _json_ready(workstream),
        "recipient_ready": bool(email or telegram_url),
        "next_action": "Подготовить и проверить сообщение" if email or telegram_url else "Добавить публичный контакт автора",
    }


def create_collaboration(cursor: Any, *, business_id: str, campaign_id: str, candidate_id: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT candidate.creator_profile_id, campaign.status AS campaign_status,
               campaign.terms_version, campaign.approved_terms_version
        FROM creator_campaign_candidates candidate
        JOIN creator_campaigns campaign ON campaign.id = candidate.campaign_id
        WHERE candidate.id = %s AND campaign.id = %s AND campaign.business_id = %s
        """,
        (candidate_id, campaign_id, business_id),
    )
    candidate = _dict(cursor.fetchone())
    if not candidate:
        raise LookupError("Кандидат не найден")
    if candidate.get("campaign_status") != "approved" or candidate.get("terms_version") != candidate.get("approved_terms_version"):
        raise ValueError("Условия кампании не подтверждены")
    status = str(payload.get("status") or "draft")
    if status not in COLLABORATION_STATUSES:
        raise ValueError("Недопустимый статус коллаборации")
    collaboration_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_collaborations (
            id, campaign_id, campaign_candidate_id, business_id, creator_profile_id,
            status, agreed_terms_json, scheduled_visit_at, owner_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, ''))
        ON CONFLICT (campaign_candidate_id) DO UPDATE SET
            agreed_terms_json = EXCLUDED.agreed_terms_json,
            scheduled_visit_at = EXCLUDED.scheduled_visit_at,
            terms_version = creator_collaborations.terms_version + 1,
            approved_terms_version = NULL, updated_at = NOW()
        RETURNING id
        """,
        (
            collaboration_id, campaign_id, candidate_id, business_id, candidate["creator_profile_id"],
            status, Json(_json(payload.get("terms"), {})),
            payload.get("scheduled_visit_at"), user_id,
        ),
    )
    row = _dict(cursor.fetchone())
    return load_collaboration(cursor, business_id=business_id, collaboration_id=str(row["id"]))


def update_collaboration(cursor: Any, *, business_id: str, collaboration_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    collaboration = load_collaboration(cursor, business_id=business_id, collaboration_id=collaboration_id)
    status = str(payload.get("status") if "status" in payload else collaboration.get("status") or "draft")
    if status not in COLLABORATION_STATUSES:
        raise ValueError("Недопустимый статус коллаборации")
    terms_changed = "terms" in payload
    terms = _json(payload.get("terms"), collaboration.get("agreed_terms") or {})
    cursor.execute(
        """
        UPDATE creator_collaborations SET
            status = %s, agreed_terms_json = %s,
            scheduled_visit_at = COALESCE(%s, scheduled_visit_at),
            terms_version = terms_version + CASE WHEN %s THEN 1 ELSE 0 END,
            approved_terms_version = CASE WHEN %s THEN NULL ELSE approved_terms_version END,
            updated_at = NOW()
        WHERE id = %s AND business_id = %s
        """,
        (status, Json(terms), payload.get("scheduled_visit_at"), terms_changed, terms_changed, collaboration_id, business_id),
    )
    return load_collaboration(cursor, business_id=business_id, collaboration_id=collaboration_id)


def _load_measurement_checkpoints(cursor: Any, deliverable_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, checkpoint, due_at, status, completed_metric_id, completed_at
        FROM creator_measurement_checkpoints
        WHERE deliverable_id = %s
        ORDER BY due_at, checkpoint
        """,
        (deliverable_id,),
    )
    return [_json_ready(_dict(row)) for row in cursor.fetchall()]


def load_collaboration(cursor: Any, *, business_id: str, collaboration_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT collaboration.*, profile.display_name, profile.profile_type
        FROM creator_collaborations collaboration
        JOIN creator_profiles profile ON profile.id = collaboration.creator_profile_id
        WHERE collaboration.id = %s AND collaboration.business_id = %s
        """,
        (collaboration_id, business_id),
    )
    collaboration = _dict(cursor.fetchone())
    if not collaboration:
        raise LookupError("Коллаборация не найдена")
    collaboration["agreed_terms"] = _json(collaboration.pop("agreed_terms_json", {}), {})
    collaboration["public_room_ready"] = bool(collaboration.pop("public_token_hash", None))
    cursor.execute("SELECT * FROM creator_deliverables WHERE collaboration_id = %s ORDER BY due_at NULLS LAST", (collaboration_id,))
    deliverables = []
    for row in cursor.fetchall():
        item = _dict(row)
        item["required_elements"] = _json(item.pop("required_elements_json", []), [])
        item["proof"] = _json(item.pop("proof_json", {}), {})
        item["usage_rights"] = _json(item.pop("usage_rights_json", {}), {})
        item["tracking"] = _json(item.pop("tracking_json", {}), {})
        item["measurement_checkpoints"] = _load_measurement_checkpoints(cursor, str(item["id"]))
        deliverables.append(_json_ready(item))
    collaboration["deliverables"] = deliverables
    return _json_ready(collaboration)


def create_creator_room(cursor: Any, *, business_id: str, collaboration_id: str) -> dict[str, Any]:
    load_collaboration(cursor, business_id=business_id, collaboration_id=collaboration_id)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    cursor.execute(
        """
        UPDATE creator_collaborations
        SET public_token_hash = %s, public_token_expires_at = %s, updated_at = NOW()
        WHERE id = %s AND business_id = %s
        """,
        (token_hash, expires_at, collaboration_id, business_id),
    )
    base_url = str(os.getenv("PUBLIC_BASE_URL") or os.getenv("FRONTEND_URL") or "https://localos.pro").rstrip("/")
    return {
        "public_url": f"{base_url}/creator-room/{token}",
        "expires_at": expires_at.isoformat(),
        "external_messages_sent": 0,
    }


def _creator_room_by_token(cursor: Any, token: str) -> dict[str, Any]:
    token_hash = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
    cursor.execute(
        """
        SELECT collaboration.*, profile.display_name, profile.profile_type,
               campaign.title AS campaign_title, campaign.goal AS campaign_goal,
               campaign.formats_json, campaign.offer_json, campaign.period_json,
               campaign.budget_json, campaign.constraints_json,
               business.name AS business_name, business.city AS business_city,
               business.address AS business_address,
               commercial.media_kit_url, commercial.availability_text,
               commercial.preferred_contact
        FROM creator_collaborations collaboration
        JOIN creator_profiles profile ON profile.id = collaboration.creator_profile_id
        JOIN creator_campaigns campaign ON campaign.id = collaboration.campaign_id
        JOIN businesses business ON business.id = collaboration.business_id
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        WHERE collaboration.public_token_hash = %s
          AND collaboration.public_token_expires_at > NOW()
        LIMIT 1
        """,
        (token_hash,),
    )
    room = _dict(cursor.fetchone())
    if not room:
        raise LookupError("Ссылка недействительна или истекла")
    for key in ("agreed_terms_json", "formats_json", "offer_json", "period_json", "budget_json", "constraints_json"):
        target = key.removesuffix("_json")
        room[target] = _json(room.pop(key, None), [] if key == "formats_json" else {})
    cursor.execute(
        """
        SELECT id, platform, deliverable_type, due_at, required_elements_json,
               publication_url, verification_status, published_at, tracking_json
        FROM creator_deliverables
        WHERE collaboration_id = %s ORDER BY due_at NULLS LAST, created_at
        """,
        (room["id"],),
    )
    deliverables = []
    for row in cursor.fetchall():
        item = _dict(row)
        item["required_elements"] = _json(item.pop("required_elements_json", []), [])
        item["tracking"] = _json(item.pop("tracking_json", {}), {})
        item["measurement_checkpoints"] = _load_measurement_checkpoints(cursor, str(item["id"]))
        deliverables.append(_json_ready(item))
    safe_keys = (
        "id", "status", "display_name", "profile_type", "campaign_title", "campaign_goal",
        "business_name", "business_city", "business_address", "scheduled_visit_at",
        "agreed_terms", "formats", "offer", "period", "budget", "constraints",
        "terms_version", "approved_terms_version", "public_token_expires_at",
        "media_kit_url", "availability_text", "preferred_contact",
    )
    response = {key: room.get(key) for key in safe_keys}
    response["deliverables"] = deliverables
    return _json_ready(response)


def load_creator_room(cursor: Any, token: str) -> dict[str, Any]:
    return _creator_room_by_token(cursor, token)


def respond_in_creator_room(cursor: Any, *, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    room = _creator_room_by_token(cursor, token)
    action = str(payload.get("action") or "").strip()
    collaboration_id = str(room["id"])
    if action == "accept":
        cursor.execute(
            "UPDATE creator_collaborations SET status = 'agreed', approved_terms_version = terms_version, updated_at = NOW() WHERE id = %s",
            (collaboration_id,),
        )
        cursor.execute(
            "UPDATE creator_campaign_candidates SET status = 'agreed', updated_at = NOW() WHERE id = (SELECT campaign_candidate_id FROM creator_collaborations WHERE id = %s)",
            (collaboration_id,),
        )
    elif action == "decline":
        cursor.execute("UPDATE creator_collaborations SET status = 'declined', updated_at = NOW() WHERE id = %s", (collaboration_id,))
        cursor.execute(
            "UPDATE creator_campaign_candidates SET status = 'declined', updated_at = NOW() WHERE id = (SELECT campaign_candidate_id FROM creator_collaborations WHERE id = %s)",
            (collaboration_id,),
        )
    elif action == "propose_changes":
        comment = str(payload.get("comment") or "").strip()
        if not comment:
            raise ValueError("Опишите предлагаемые изменения")
        next_terms = dict(room.get("agreed_terms") or {})
        next_terms["creator_proposal"] = {"comment": comment, "submitted_at": datetime.now(timezone.utc).isoformat()}
        cursor.execute(
            """
            UPDATE creator_collaborations SET status = 'negotiating', agreed_terms_json = %s,
                terms_version = terms_version + 1, approved_terms_version = NULL, updated_at = NOW()
            WHERE id = %s
            """,
            (Json(next_terms), collaboration_id),
        )
    elif action == "add_publication":
        publication_url = _canonical_url(payload.get("publication_url"))
        if not publication_url.startswith("http"):
            raise ValueError("Добавьте полную публичную ссылку на материал")
        deliverable_id = str(payload.get("deliverable_id") or "").strip()
        if deliverable_id:
            cursor.execute(
                """
                UPDATE creator_deliverables SET publication_url = %s, verification_status = 'submitted',
                    published_at = COALESCE(published_at, NOW()), updated_at = NOW()
                WHERE id = %s AND collaboration_id = %s
                RETURNING id
                """,
                (publication_url, deliverable_id, collaboration_id),
            )
            if not cursor.fetchone():
                raise LookupError("Материал не найден")
        else:
            cursor.execute(
                """
                INSERT INTO creator_deliverables (
                    id, collaboration_id, platform, deliverable_type, publication_url,
                    verification_status, proof_json, usage_rights_json, published_at
                ) VALUES (%s, %s, %s, %s, %s, 'submitted', %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()), collaboration_id,
                    str(payload.get("platform") or "other"), str(payload.get("deliverable_type") or "post"),
                    publication_url, Json({"submitted_by": "creator_room"}), Json({"confirmed": False}),
                ),
            )
        cursor.execute("UPDATE creator_collaborations SET status = 'published', updated_at = NOW() WHERE id = %s", (collaboration_id,))
    elif action == "add_metrics":
        deliverable_id = str(payload.get("deliverable_id") or "").strip()
        if not deliverable_id:
            raise ValueError("Выберите опубликованный материал")
        cursor.execute("SELECT business_id FROM creator_collaborations WHERE id = %s", (collaboration_id,))
        business_row = _dict(cursor.fetchone())
        add_metric_snapshot(
            cursor,
            business_id=str(business_row.get("business_id") or ""),
            deliverable_id=deliverable_id,
            payload={**payload, "source_type": "creator_reported", "confidence": 0.7, "confirmed_revenue": None},
        )
    elif action == "update_profile":
        media_kit_url = _canonical_url(payload.get("media_kit_url"))
        if media_kit_url and not media_kit_url.startswith("http"):
            raise ValueError("Добавьте полную ссылку на медиакит")
        cursor.execute(
            """
            INSERT INTO creator_commercial_profiles (
                id, creator_profile_id, media_kit_url, preferred_contact,
                availability_text, confirmation_status, confirmed_at
            ) VALUES (%s, (SELECT creator_profile_id FROM creator_collaborations WHERE id = %s),
                      %s, %s, %s, 'creator_confirmed', NOW())
            ON CONFLICT (creator_profile_id) DO UPDATE SET
                media_kit_url = COALESCE(NULLIF(EXCLUDED.media_kit_url, ''), creator_commercial_profiles.media_kit_url),
                preferred_contact = COALESCE(NULLIF(EXCLUDED.preferred_contact, ''), creator_commercial_profiles.preferred_contact),
                availability_text = COALESCE(NULLIF(EXCLUDED.availability_text, ''), creator_commercial_profiles.availability_text),
                confirmation_status = 'creator_confirmed', confirmed_at = NOW(), updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), collaboration_id, media_kit_url or None,
                str(payload.get("preferred_contact") or "").strip() or None,
                str(payload.get("availability_text") or "").strip() or None,
            ),
        )
    elif action == "recommend_creator":
        cursor.execute("SELECT business_id FROM creator_collaborations WHERE id = %s", (collaboration_id,))
        business_row = _dict(cursor.fetchone())
        upsert_manual_creator(
            cursor,
            business_id=str(business_row.get("business_id") or ""),
            payload={
                "display_name": payload.get("display_name"),
                "url": payload.get("url"),
                "profile_type": "author",
                "contactability": "manual_only",
                "description": "Рекомендован автором через приватную комнату",
            },
        )
    else:
        raise ValueError("Недопустимое действие")
    return _creator_room_by_token(cursor, token)


def list_collaborations(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT collaboration.id FROM creator_collaborations collaboration
        WHERE collaboration.business_id = %s ORDER BY collaboration.updated_at DESC
        """,
        (business_id,),
    )
    return [load_collaboration(cursor, business_id=business_id, collaboration_id=str(_dict(row)["id"])) for row in cursor.fetchall()]


def add_deliverable(cursor: Any, *, business_id: str, collaboration_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    collaboration = load_collaboration(cursor, business_id=business_id, collaboration_id=collaboration_id)
    deliverable_id = str(uuid.uuid4())
    publication_url = str(payload.get("publication_url") or "").strip() or None
    verification = "submitted" if publication_url else "expected"
    platform = str(payload.get("platform") or "other")
    tracking = build_tracking_plan(
        payload.get("tracking") if isinstance(payload.get("tracking"), dict) else {},
        platform=platform,
        campaign_id=str(collaboration.get("campaign_id") or ""),
        creator_profile_id=str(collaboration.get("creator_profile_id") or ""),
    )
    cursor.execute(
        """
        INSERT INTO creator_deliverables (
            id, collaboration_id, platform, deliverable_type, due_at,
            required_elements_json, publication_url, proof_json, verification_status,
            usage_rights_json, published_at, tracking_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            deliverable_id, collaboration_id, platform,
            str(payload.get("deliverable_type") or "post"), payload.get("due_at"),
            Json(_text_list(payload.get("required_elements"))), publication_url,
            Json(_json(payload.get("proof"), {})), verification,
            Json(_json(payload.get("usage_rights"), {})), payload.get("published_at"), Json(tracking),
        ),
    )
    return load_collaboration(cursor, business_id=business_id, collaboration_id=collaboration_id)


def verify_deliverable(cursor: Any, *, business_id: str, deliverable_id: str, status: str, proof: dict[str, Any] | None = None) -> dict[str, Any]:
    if status not in DELIVERABLE_VERIFICATION_STATUSES:
        raise ValueError("Недопустимый статус проверки материала")
    cursor.execute(
        """
        UPDATE creator_deliverables deliverable SET
            verification_status = %s,
            proof_json = CASE WHEN %s::jsonb = '{}'::jsonb THEN proof_json ELSE proof_json || %s::jsonb END,
            published_at = CASE WHEN %s = 'verified' THEN COALESCE(published_at, NOW()) ELSE published_at END,
            updated_at = NOW()
        FROM creator_collaborations collaboration
        WHERE deliverable.id = %s AND deliverable.collaboration_id = collaboration.id
          AND collaboration.business_id = %s
        RETURNING collaboration.id, deliverable.published_at
        """,
        (status, Json(proof or {}), Json(proof or {}), status, deliverable_id, business_id),
    )
    row = _dict(cursor.fetchone())
    if not row:
        raise LookupError("Материал не найден")
    if status == "verified":
        published_at = row.get("published_at")
        if not isinstance(published_at, datetime):
            published_at = datetime.now(timezone.utc)
        _ensure_measurement_checkpoints(cursor, deliverable_id=deliverable_id, published_at=published_at)
    return load_collaboration(cursor, business_id=business_id, collaboration_id=str(row["id"]))


def add_metric_snapshot(cursor: Any, *, business_id: str, deliverable_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT deliverable.id FROM creator_deliverables deliverable
        JOIN creator_collaborations collaboration ON collaboration.id = deliverable.collaboration_id
        WHERE deliverable.id = %s AND collaboration.business_id = %s
        """,
        (deliverable_id, business_id),
    )
    if not cursor.fetchone():
        raise LookupError("Материал не найден")
    metric_date = str(payload.get("metric_date") or date.today().isoformat())
    source_type = str(payload.get("source_type") or "manual")
    allowed_sources = {"public", "creator_reported", "business_reported", "utm", "promo_code", "website_tracker", "crm_import", "manual"}
    if source_type not in allowed_sources:
        raise ValueError("Недопустимый источник метрик")
    count_fields = ("views", "reach", "reactions", "comments", "saves", "clicks", "promo_uses", "inquiries", "bookings")
    counts = {field: int(payload.get(field) or 0) for field in count_fields}
    if any(value < 0 for value in counts.values()):
        raise ValueError("Метрики не могут быть отрицательными")
    confidence = Decimal(str(payload.get("confidence") or 0))
    if confidence < 0 or confidence > 1:
        raise ValueError("Confidence должен быть от 0 до 1")
    if payload.get("confirmed_revenue") is not None and source_type not in {"business_reported", "crm_import"}:
        raise ValueError("Подтверждённую выручку можно добавить только из данных бизнеса или CRM")
    checkpoint = str(payload.get("checkpoint") or "").strip()
    if checkpoint and checkpoint not in MEASUREMENT_CHECKPOINTS:
        raise ValueError("Недопустимая контрольная точка")
    cursor.execute(
        """
        INSERT INTO creator_placement_metrics (
            id, deliverable_id, business_id, metric_date, views, reach, reactions,
            comments, saves, clicks, promo_uses, inquiries, bookings,
            confirmed_revenue, placement_cost, source_type, confidence, raw_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (deliverable_id, metric_date, source_type) DO UPDATE SET
            views = EXCLUDED.views, reach = EXCLUDED.reach, reactions = EXCLUDED.reactions,
            comments = EXCLUDED.comments, saves = EXCLUDED.saves, clicks = EXCLUDED.clicks,
            promo_uses = EXCLUDED.promo_uses, inquiries = EXCLUDED.inquiries,
            bookings = EXCLUDED.bookings, confirmed_revenue = EXCLUDED.confirmed_revenue,
            placement_cost = EXCLUDED.placement_cost, confidence = EXCLUDED.confidence,
            raw_json = EXCLUDED.raw_json, updated_at = NOW()
        RETURNING id
        """,
        (
            str(uuid.uuid4()), deliverable_id, business_id, metric_date,
            counts["views"], counts["reach"], counts["reactions"],
            counts["comments"], counts["saves"], counts["clicks"],
            counts["promo_uses"], counts["inquiries"], counts["bookings"],
            payload.get("confirmed_revenue"), payload.get("placement_cost"), source_type,
            confidence, Json(_json(payload.get("raw"), {})),
        ),
    )
    metric_row = _dict(cursor.fetchone())
    if checkpoint:
        cursor.execute(
            """
            UPDATE creator_measurement_checkpoints checkpoint_row
            SET status = 'completed', completed_metric_id = %s, completed_at = NOW(), updated_at = NOW()
            FROM creator_deliverables deliverable
            WHERE checkpoint_row.deliverable_id = deliverable.id
              AND checkpoint_row.deliverable_id = %s
              AND checkpoint_row.checkpoint = %s
              AND deliverable.id IN (
                  SELECT owned_deliverable.id
                  FROM creator_deliverables owned_deliverable
                  JOIN creator_collaborations collaboration ON collaboration.id = owned_deliverable.collaboration_id
                  WHERE collaboration.business_id = %s
              )
            """,
            (metric_row.get("id"), deliverable_id, checkpoint, business_id),
        )
    return metrics_summary(cursor, business_id)


def metrics_summary(cursor: Any, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT COUNT(DISTINCT collaboration.id)::INT AS collaborations,
               COUNT(DISTINCT deliverable.id)::INT AS deliverables,
               COUNT(DISTINCT deliverable.id) FILTER (WHERE deliverable.verification_status = 'verified')::INT AS verified_deliverables,
               COALESCE(SUM(metric.reach), 0)::BIGINT AS reach,
               COALESCE(SUM(metric.views), 0)::BIGINT AS views,
               COALESCE(SUM(metric.reactions), 0)::BIGINT AS reactions,
               COALESCE(SUM(metric.clicks), 0)::BIGINT AS clicks,
               COALESCE(SUM(metric.inquiries), 0)::BIGINT AS inquiries,
               COALESCE(SUM(metric.bookings), 0)::BIGINT AS bookings,
               COALESCE(SUM(metric.placement_cost), 0) AS placement_cost,
               COALESCE(SUM(metric.confirmed_revenue), 0) AS confirmed_revenue
        FROM creator_collaborations collaboration
        LEFT JOIN creator_deliverables deliverable ON deliverable.collaboration_id = collaboration.id
        LEFT JOIN LATERAL (
            SELECT snapshot.* FROM creator_placement_metrics snapshot
            WHERE snapshot.deliverable_id = deliverable.id
            ORDER BY snapshot.metric_date DESC, snapshot.updated_at DESC
            LIMIT 1
        ) metric ON TRUE
        WHERE collaboration.business_id = %s
        """,
        (business_id,),
    )
    summary = _dict(cursor.fetchone())
    cursor.execute(
        """
        SELECT COUNT(*) FILTER (WHERE checkpoint.status = 'pending')::INT AS pending,
               COUNT(*) FILTER (WHERE checkpoint.status = 'pending' AND checkpoint.due_at <= NOW())::INT AS due,
               COUNT(*) FILTER (WHERE checkpoint.status = 'completed')::INT AS completed,
               MIN(checkpoint.due_at) FILTER (WHERE checkpoint.status = 'pending') AS next_due_at
        FROM creator_measurement_checkpoints checkpoint
        JOIN creator_deliverables deliverable ON deliverable.id = checkpoint.deliverable_id
        JOIN creator_collaborations collaboration ON collaboration.id = deliverable.collaboration_id
        WHERE collaboration.business_id = %s
        """,
        (business_id,),
    )
    checkpoint_summary = _dict(cursor.fetchone())
    reach = int(summary.get("reach") or 0)
    cost = float(summary.get("placement_cost") or 0)
    inquiries = int(summary.get("inquiries") or 0)
    bookings = int(summary.get("bookings") or 0)
    summary["calculated"] = {
        "cpm": round(cost / reach * 1000, 2) if reach else None,
        "cpe": round(cost / int(summary.get("reactions") or 0), 2) if int(summary.get("reactions") or 0) else None,
        "cost_per_click": round(cost / int(summary.get("clicks") or 0), 2) if int(summary.get("clicks") or 0) else None,
        "cost_per_inquiry": round(cost / inquiries, 2) if inquiries else None,
        "cost_per_booking": round(cost / bookings, 2) if bookings else None,
    }
    summary["disclaimer"] = "Выручка учитывается только из подтверждённых данных бизнеса или CRM; остальные показатели остаются наблюдаемыми или расчётными."
    summary["measurement_checkpoints"] = _json_ready(checkpoint_summary)
    return _json_ready(summary)


def promotion_overview(cursor: Any, business_id: str) -> dict[str, Any]:
    jobs = list_search_jobs(cursor, business_id)
    campaigns = list_campaigns(cursor, business_id)
    collaborations = list_collaborations(cursor, business_id)
    return {
        "feature_state": creator_feature_state(business_id),
        "latest_search": jobs[0] if jobs else None,
        "campaigns": campaigns,
        "collaborations": collaborations,
        "metrics": metrics_summary(cursor, business_id),
        "next_action": (
            "Проверить найденных авторов"
            if jobs and int(jobs[0].get("results_count") or 0) > 0
            else "Запустить первый поиск локальных авторов"
        ),
    }
