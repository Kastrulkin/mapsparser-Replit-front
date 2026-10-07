from __future__ import annotations

import json
import os
import re
import argparse
import math
from datetime import datetime, timezone
from statistics import median
from typing import Any

from psycopg2.extras import Json, RealDictCursor


ENRICHMENT_VERSION = "creator-source-v2"

CITY_PATTERNS = {
    "Санкт-Петербург": (
        r"\bсанкт[ -]?петербург(?:е|а|у|ом)?\b",
        r"\bпетербург(?:е|а|у|ом)?\b",
        r"(?<![a-zа-я0-9])спб(?![a-zа-я0-9])",
        r"\bsaint[ -]?petersburg\b",
        r"\bst\.?[ -]?petersburg\b",
    ),
    "Tallinn": (
        r"\btallinn(?:a|as|ast|ale|asse|lane|linn)?\b",
        r"\bталлин(?:н|на|не|ном|нец|ский|ская|ские)?\b",
    ),
}

AREA_PATTERNS = {
    "Санкт-Петербург": {
        "Приморский район": (r"\bприморск(?:ий|ого|ом) район", r"\bприморск(?:ий|ого|ом)\b"),
        "Выборгский район": (r"\bвыборгск(?:ий|ого|ом) район", r"\bпарнас\b", r"\bозерки\b"),
        "Калининский район": (r"\bкалининск(?:ий|ого|ом) район", r"\bгражданк[аи]\b"),
        "Петроградский район": (r"\bпетроградск(?:ий|ого|ом) район", r"\bпетроградк[аи]\b"),
        "Центральный район": (r"\bцентральн(?:ый|ого|ом) район",),
        "Московский район": (r"\bмосковск(?:ий|ого|ом) район", r"\bмосковск(?:ая|ие) ворот"),
        "Невский район": (r"\bневск(?:ий|ого|ом) район",),
        "Фрунзенский район": (r"\bфрунзенск(?:ий|ого|ом) район", r"\bкупчино\b"),
        "Красносельский район": (r"\bкрасносельск(?:ий|ого|ом) район",),
        "Василеостровский район": (r"\bвасилеостровск(?:ий|ого|ом) район", r"\bвасильевск(?:ий|ого) остров"),
        "Адмиралтейский район": (r"\bадмиралтейск(?:ий|ого|ом) район",),
        "Курортный район": (r"\bкурортн(?:ый|ого|ом) район", r"\bсестрорецк\b", r"\bзеленогорск\b"),
    },
    "Tallinn": {
        "Kesklinn": (r"\bkesklinn(?:a|as|ast)?\b", r"\bцентр(?:е|а)? таллин"),
        "Lasnamäe": (r"\blasnam[aä]e\b", r"\bласнамяэ\b"),
        "Mustamäe": (r"\bmustam[aä]e\b", r"\bмустамяэ\b"),
        "Kristiine": (r"\bkristiine\b", r"\bкристийне\b"),
        "Haabersti": (r"\bhaabersti\b", r"\bхааберсти\b"),
        "Põhja-Tallinn": (r"\bp[oõ]hja[ -]tallinn\b", r"\bпыхья[ -]таллинн\b", r"\bkalamaja\b"),
        "Pirita": (r"\bpirita\b", r"\bпирита\b"),
        "Nõmme": (r"\bn[oõ]mme\b", r"\bнымме\b"),
    },
}

TOPIC_PATTERNS = {
    "семья и дети": (r"\bмам(?:а|ы|ам|ами)?\b", r"\bродител", r"\bдет(?:и|ей|ям|ский|ская|ское)", r"\bfamil", r"\bkids?\b"),
    "красота": (r"\bкрасот", r"\bbeauty\b", r"\bсалон", r"\bволос", r"\bманикюр", r"\bмакияж"),
    "косметология": (r"\bкосметолог", r"\bинъекц", r"\bлазерн", r"\bпилинг", r"\bботокс", r"\bэстетическ"),
    "wellness": (r"\bwellness\b", r"\bspa\b", r"\bспа\b", r"\bмассаж", r"\bздоров", r"\bфитнес"),
    "путешествия": (r"\bпутешеств", r"\bтуризм", r"\btravel\b", r"\btrip\b", r"\bэкскурс", r"\bотел"),
    "трансферы и транспорт": (r"\bтрансфер", r"\btransfer\b", r"\bаэропорт", r"\bтакси\b", r"\bводител", r"\btransport"),
    "местный бизнес": (r"\bбизнес", r"\bпредпринимател", r"\bстартап", r"\bfounder", r"\bettev[oõ]t"),
    "экспаты": (r"\bэкспат", r"\bexpat", r"\bэмигран", r"\brelocation", r"\brelok"),
    "городская жизнь": (r"\bафиша", r"\bкуда сходить", r"\bсобыти", r"\bмероприяти", r"\bновост", r"\bгородск"),
    "еда и места": (r"\bресторан", r"\bкафе\b", r"\bеда\b", r"\bfood\b", r"\bместа\b"),
}

FORMAT_PATTERNS = {
    "обзор": (r"\bобзор", r"\breview\b"),
    "пост": (r"\bпост(?:ы|ов|е)?\b", r"\bпубликац"),
    "видео": (r"\bвидео\b", r"\bvideo\b", r"\byoutube\b"),
    "короткое видео": (r"\breels?\b", r"\bshorts?\b", r"\btiktok\b", r"\bтикток\b"),
    "подборка": (r"\bподборк", r"\bтоп[- ]?\d+"),
    "интервью": (r"\bинтервью\b", r"\binterview\b"),
}

CONTACT_CONTEXT_PATTERN = re.compile(
    r"(?:по вопросам рекламы|реклам[аыеу]|сотрудничеств|размещени[ея]|партн[её]рств|advertis|collab|media[ -]?kit)",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"(?<![\w.+-])([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})(?![\w.-])", re.IGNORECASE)
TELEGRAM_HANDLE_PATTERN = re.compile(r"(?<![\w@])@([a-zA-Z][a-zA-Z0-9_]{4,31})(?![\w])")


def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("ё", "е").split())


def _matches(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, re.IGNORECASE)]


def _supported_documents(documents: list[dict[str, Any]], patterns: tuple[str, ...]) -> int:
    return sum(
        1
        for document in documents
        if _matches(_normalized(document.get("content")), patterns)
    )


def _sufficient_support(documents: list[dict[str, Any]], patterns: tuple[str, ...], ratio: float) -> bool:
    if not documents:
        return False
    required = 1 if len(documents) < 3 else max(2, math.ceil(len(documents) * ratio))
    return _supported_documents(documents, patterns) >= required


def _numeric_values(documents: list[dict[str, Any]], key: str) -> list[int]:
    values: list[int] = []
    for document in documents:
        metadata = _json(document.get("metadata"), {})
        raw = metadata.get(key)
        if isinstance(raw, bool):
            continue
        try:
            number = int(float(str(raw)))
        except (TypeError, ValueError):
            continue
        if number >= 0:
            values.append(number)
    return values


def _public_contacts(text: str) -> list[str]:
    contacts: list[str] = []
    for match in CONTACT_CONTEXT_PATTERN.finditer(text):
        window = text[max(0, match.start() - 160): min(len(text), match.end() + 240)]
        contacts.extend(item.lower() for item in EMAIL_PATTERN.findall(window))
        contacts.extend(f"@{item}" for item in TELEGRAM_HANDLE_PATTERN.findall(window))
    return list(dict.fromkeys(contacts))[:5]


def infer_creator_source_metadata(source: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(_json(source.get("metadata_json"), {}))
    previous_enrichment = _json(metadata.get("creator_enrichment"), {})
    previous_evidence = _json(previous_enrichment.get("evidence"), {})
    documents = [item for item in _json(source.get("documents_json"), []) if isinstance(item, dict)]
    title = str(source.get("title") or "")
    body = " ".join(str(item.get("content") or "") for item in documents)
    title_text = _normalized(title)
    combined = _normalized(f"{title} {body}")
    evidence: dict[str, Any] = {}

    city_matches: dict[str, list[str]] = {}
    for city, patterns in CITY_PATTERNS.items():
        found = _matches(combined, patterns)
        if found and (_matches(title_text, patterns) or _sufficient_support(documents, patterns, 0.2)):
            city_matches[city] = found
    city = "" if previous_evidence.get("city") else str(metadata.get("city") or metadata.get("location_city") or "").strip()
    if not city and len(city_matches) == 1:
        city = next(iter(city_matches))
        evidence["city"] = {
            "value": city,
            "confidence": 0.9 if _matches(title_text, CITY_PATTERNS[city]) else 0.76,
            "basis": "public_title_or_documents",
            "matched_patterns": city_matches[city],
        }

    area = "" if previous_evidence.get("area") else str(metadata.get("area") or metadata.get("district") or "").strip()
    if not area and city in AREA_PATTERNS:
        candidates: list[tuple[str, list[str]]] = []
        for name, patterns in AREA_PATTERNS[city].items():
            found = _matches(combined, patterns)
            if found and (_matches(title_text, patterns) or _sufficient_support(documents, patterns, 0.1)):
                candidates.append((name, found))
        if len(candidates) == 1:
            area, found = candidates[0]
            evidence["area"] = {
                "value": area,
                "confidence": 0.84 if _matches(title_text, AREA_PATTERNS[city][area]) else 0.7,
                "basis": "public_title_or_documents",
                "matched_patterns": found,
            }

    previous_inferred_topics = set(_json(_json(previous_evidence.get("topics"), {}).get("value"), []))
    topics = [
        str(item).strip()
        for item in _json(metadata.get("topics") or metadata.get("categories"), [])
        if str(item).strip() and str(item).strip() not in previous_inferred_topics
    ]
    inferred_topics: list[str] = []
    topic_evidence: dict[str, list[str]] = {}
    for topic, patterns in TOPIC_PATTERNS.items():
        found = _matches(combined, patterns)
        if found and (_matches(title_text, patterns) or _sufficient_support(documents, patterns, 0.12)):
            inferred_topics.append(topic)
            topic_evidence[topic] = found
    topics = list(dict.fromkeys([*topics, *inferred_topics]))[:12]
    if inferred_topics:
        evidence["topics"] = {
            "value": inferred_topics,
            "confidence": 0.72,
            "basis": "public_title_or_documents",
            "matched_patterns": topic_evidence,
        }

    formats: list[str] = []
    for name, patterns in FORMAT_PATTERNS.items():
        if _matches(combined, patterns):
            formats.append(name)
    if not formats and int(source.get("document_count") or 0) > 0:
        formats = ["пост"]

    audience = str(metadata.get("audience") or metadata.get("audience_type") or "").strip()
    if not audience:
        if "семья и дети" in topics:
            audience = "семьи с детьми"
        elif "экспаты" in topics:
            audience = "экспаты и переезжающие"
        elif "местный бизнес" in topics:
            audience = "владельцы и сотрудники местного бизнеса"
        elif city:
            audience = f"жители и посетители города {city}"

    source_role = str(source.get("source_role") or "unknown").strip().lower()
    owner_role = str(metadata.get("source_owner_role") or "").strip().lower()
    title_and_role = f"{title_text} {owner_role}"
    if source_role == "expert" or owner_role in {"expert", "author", "creator", "blogger"}:
        profile_type = "author"
    elif re.search(r"\b(новост|медиа|журнал|газет|редакц|news|media)\b", title_and_role):
        profile_type = "media"
    elif re.search(r"\b(афиша|куда сходить|скидки|акции|каталог|агрегатор|топ мест)\b", title_and_role):
        profile_type = "aggregator"
    elif source_role == "community" or re.search(r"\b(мамы|родители|соседи|район|community|сообщество|чат)\b", title_and_role):
        profile_type = "community"
    else:
        profile_type = "channel"

    creator_eligible = source_role not in {"salon", "service", "vendor", "competitor"}
    if metadata.get("official_brand_source") is True or metadata.get("source_owner_type") in {"business", "company", "brand"}:
        creator_eligible = False
    if profile_type in {"author", "media", "aggregator", "community"} and source_role not in {"salon", "service", "vendor", "competitor"}:
        creator_eligible = True

    contacts = _public_contacts(combined)
    preferred_contact = contacts[0] if contacts else ""
    if contacts:
        contactability = "advertising_contact"
    elif metadata.get("recipient_eligible") is True and str(metadata.get("telegram_entity_type") or "") in {"user", "bot"}:
        contactability = "public_contact"
    elif source.get("canonical_url"):
        contactability = "manual_only"
    else:
        contactability = "not_contactable"

    views = _numeric_values(documents, "views")
    reactions = _numeric_values(documents, "reactions_total") or _numeric_values(documents, "reactions")
    forwards = _numeric_values(documents, "forwards")
    public_metrics: dict[str, Any] = {}
    if views:
        public_metrics["median_views"] = int(median(views))
        public_metrics["sample_size"] = len(views)
    if reactions:
        public_metrics["median_reactions"] = int(median(reactions))
    if forwards:
        public_metrics["median_forwards"] = int(median(forwards))
    if public_metrics:
        public_metrics["source"] = "public_telegram_documents"
        public_metrics["observed_at"] = source.get("latest_document_at").isoformat() if isinstance(source.get("latest_document_at"), datetime) else None

    enrichment = {
        "version": ENRICHMENT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "basis": "public_metadata_and_documents",
        "document_count": int(source.get("document_count") or 0),
        "sampled_documents": len(documents),
        "evidence": evidence,
    }
    patch: dict[str, Any] = {
        "creator_enrichment": enrichment,
        "creator_profile_type": profile_type,
        "creator_eligible": creator_eligible,
        "creator_public_contacts": contacts,
        "contactability": contactability,
    }
    if city:
        patch["city"] = city
    if area:
        patch["area"] = area
    if topics:
        patch["topics"] = topics
    if audience:
        patch["audience"] = audience
    if formats:
        patch["formats"] = formats
    if preferred_contact:
        patch["preferred_contact"] = preferred_contact
    if public_metrics:
        patch["public_metrics"] = public_metrics
    return patch


def enrich_creator_sources(
    cursor: Any,
    *,
    limit: int = 500,
    source_ids: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    filters = [
        "source.visibility = 'public'",
        "source.sensitivity_class = 'public'",
        "source.status IN ('candidate', 'active')",
        "source.source_type IN ('telegram', 'website', 'vk')",
    ]
    params: list[Any] = []
    if source_ids:
        filters.append("source.id = ANY(%s::uuid[])")
        params.append(source_ids)
    else:
        filters.append("COALESCE(source.metadata_json->'creator_enrichment'->>'version', '') <> %s")
        params.append(ENRICHMENT_VERSION)
    params.append(max(1, min(limit, 2000)))
    cursor.execute(
        f"""
        SELECT source.id, source.title, source.canonical_url, source.source_type,
               source.source_role, source.metadata_json, source.last_collected_at,
               stats.document_count, stats.latest_document_at, samples.documents_json
        FROM knowledge_sources source
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::INT AS document_count, MAX(document.published_at) AS latest_document_at
            FROM knowledge_documents document
            WHERE document.source_id = source.id AND document.invalidated_at IS NULL
              AND document.sensitivity_class = 'public'
        ) stats ON TRUE
        LEFT JOIN LATERAL (
            SELECT COALESCE(
                JSONB_AGG(JSONB_BUILD_OBJECT(
                    'content', sample.content_text,
                    'metadata', sample.metadata_json,
                    'published_at', sample.published_at
                ) ORDER BY sample.published_at DESC NULLS LAST),
                '[]'::jsonb
            ) AS documents_json
            FROM (
                SELECT document.content_text, document.metadata_json, document.published_at
                FROM knowledge_documents document
                WHERE document.source_id = source.id AND document.invalidated_at IS NULL
                  AND document.sensitivity_class = 'public'
                ORDER BY document.published_at DESC NULLS LAST, document.created_at DESC
                LIMIT 50
            ) sample
        ) samples ON TRUE
        WHERE {' AND '.join(filters)}
        ORDER BY source.last_collected_at DESC NULLS LAST, source.updated_at DESC
        LIMIT %s
        """,
        params,
    )
    rows = [dict(row) for row in cursor.fetchall()]
    coverage = {
        "city": 0,
        "area": 0,
        "topics": 0,
        "metrics": 0,
        "contacts": 0,
        "eligible": 0,
    }
    updated = 0
    for source in rows:
        existing = dict(_json(source.get("metadata_json"), {}))
        patch = infer_creator_source_metadata(source)
        merged = {**existing, **patch}
        for key, field in (
            ("city", "city"),
            ("area", "area"),
            ("topics", "topics"),
            ("public_metrics", "metrics"),
            ("creator_public_contacts", "contacts"),
        ):
            if merged.get(key):
                coverage[field] += 1
        if merged.get("creator_eligible") is True:
            coverage["eligible"] += 1
        if not dry_run:
            cursor.execute(
                "UPDATE knowledge_sources SET metadata_json = %s, updated_at = NOW() WHERE id = %s",
                (Json(merged), source["id"]),
            )
        updated += 1
    return {
        "version": ENRICHMENT_VERSION,
        "dry_run": dry_run,
        "selected": len(rows),
        "updated": updated if not dry_run else 0,
        "coverage": coverage,
    }


def process_creator_source_enrichment_batch() -> dict[str, Any] | None:
    if str(os.getenv("INFLUENCER_SOURCE_ENRICHMENT_ENABLED") or "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    from database_manager import DatabaseManager

    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        result = enrich_creator_sources(
            cursor,
            limit=max(1, min(int(os.getenv("INFLUENCER_SOURCE_ENRICHMENT_BATCH_SIZE") or "100"), 2000)),
        )
        database.conn.commit()
        return result
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


def _main() -> int:
    parser = argparse.ArgumentParser(description="Enrich public creator sources with deterministic metadata")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    from database_manager import DatabaseManager

    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        result = enrich_creator_sources(
            cursor,
            limit=max(1, min(arguments.limit, 2000)),
            dry_run=arguments.dry_run,
        )
        if arguments.dry_run:
            database.conn.rollback()
        else:
            database.conn.commit()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(_main())
