from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json


CLASSIFICATION_VERSION = "creator-taxonomy-v1"

CITY_ALIASES = {
    "Санкт-Петербург": ("санкт-петербург", "петербург", "спб", "питер", "saint petersburg", "st. petersburg"),
    "Таллинн": ("таллинн", "таллин", "tallinn"),
    "Москва": ("москва", "москв", "moscow"),
    "Краснодар": ("краснодар",),
    "Батуми": ("батуми", "batumi"),
}

SPB_DISTRICTS = {
    "Адмиралтейский": ("адмиралтейск",),
    "Василеостровский": ("василеостровск", "васильевский остров", "васька"),
    "Выборгский": ("выборгск", "парголово", "парнас", "озерки", "шувалово"),
    "Калининский": ("калининск", "гражданка", "академическая"),
    "Кировский": ("кировск", "автово", "нарвская"),
    "Колпинский": ("колпин",),
    "Красногвардейский": ("красногвардейск", "ржевка", "пороховые"),
    "Красносельский": ("красносельск", "юго-запад", "сосновая поляна"),
    "Кронштадтский": ("кронштадт",),
    "Курортный": ("курортн", "сестрорецк", "зеленогорск"),
    "Московский": ("московск район", "звездная", "парк победы"),
    "Невский": ("невск район", "рыбацкое", "обухово", "дыбенко"),
    "Петроградский": ("петроградск", "петроградка", "крестовский остров"),
    "Петродворцовый": ("петродворц", "петергоф", "ломоносов"),
    "Приморский": ("приморск район", "комендантский", "старая деревня", "лахта"),
    "Пушкинский": ("пушкинск", "город пушкин", "шаврово"),
    "Фрунзенский": ("фрунзенск", "купчино", "бухарестская"),
    "Центральный": ("центральн район", "центр петербурга", "лиговский", "чернышевская"),
}

SPB_METROS = {
    "Проспект Просвещения": ("проспект просвещения", "проспекте просвещения", "просвет"),
    "Парнас": ("метро парнас", "м. парнас", "парнас"),
    "Озерки": ("метро озерки", "м. озерки", "озерки"),
    "Удельная": ("метро удельная", "м. удельная", "удельная"),
    "Комендантский проспект": ("комендантский проспект", "коменда"),
    "Пионерская": ("метро пионерская", "м. пионерская"),
    "Старая Деревня": ("старая деревня",),
    "Петроградская": ("метро петроградская", "м. петроградская", "петроградка"),
    "Василеостровская": ("василеостровская",),
    "Чернышевская": ("чернышевская",),
    "Площадь Восстания": ("площадь восстания",),
    "Невский проспект": ("невский проспект",),
    "Парк Победы": ("парк победы",),
    "Московская": ("метро московская", "м. московская"),
    "Звёздная": ("звездная", "звёздная"),
    "Купчино": ("метро купчино", "м. купчино", "купчино"),
    "Автово": ("метро автово", "м. автово", "автово"),
    "Проспект Ветеранов": ("проспект ветеранов",),
    "Улица Дыбенко": ("улица дыбенко", "дыбенко"),
    "Рыбацкое": ("метро рыбацкое", "м. рыбацкое", "рыбацкое"),
}

TOPIC_RULES = {
    "family_parenting": ("мама", "папа", "родител", "детск", "ребен", "ребён", "семейн", "школ", "садик"),
    "food_cafes": ("кафе", "ресторан", "еда", "кофе", "кофейн", "завтрак", "гастроном", "food"),
    "local_places": ("куда пойти", "места", "афиша", "прогул", "район", "петербург", "спб", "питер", "город"),
    "events_entertainment": ("событ", "мероприят", "концерт", "театр", "выстав", "фестивал", "развлеч"),
    "beauty_wellness": ("beauty", "бьюти", "космет", "уход", "красот", "макияж", "крем", "салон", "wellness", "spa"),
    "travel": ("путешеств", "поездк", "туризм", "travel", "отел", "аэропорт", "трансфер"),
    "fashion": ("мода", "fashion", "стиль", "одежд", "образ"),
    "sports_fitness": ("спорт", "фитнес", "трениров", "бег", "йога"),
    "education": ("образован", "обучен", "курс", "урок", "школа", "репетитор"),
    "auto_transport": ("авто", "машин", "дорог", "такси", "трансфер", "водител"),
    "business": ("бизнес", "маркетинг", "предприним", "продаж", "стартап"),
    "home_design": ("дом", "интерьер", "ремонт", "дизайн", "недвижим"),
    "pets": ("животн", "собак", "кошк", "питом"),
}

STYLE_RULES = {
    "reviews": ("обзор", "тестир", "отзыв", "проверил", "рекоменд"),
    "guides_and_selections": ("куда пойти", "подборк", "афиша", "топ ", "маршрут", "гид"),
    "expert": ("эксперт", "совет", "разбира", "объясня", "инструкц", "визажист", "специалист"),
    "personal_lifestyle": ("мой блог", "моя жизнь", "личный блог", "lifestyle", "лайфстайл", "будни"),
    "news_and_information": ("новост", "информац", "анонс", "события города"),
    "deals_and_promotions": ("скидк", "акци", "промокод", "выгод"),
    "visual_ugc": ("ugc", "reels", "рилс", "shorts", "видеообзор", "распаков"),
}

AUDIENCE_BY_TOPIC = {
    "family_parenting": "parents_and_families",
    "food_cafes": "food_and_cafe_visitors",
    "local_places": "local_residents",
    "events_entertainment": "city_leisure_audience",
    "beauty_wellness": "beauty_and_wellness_audience",
    "travel": "travelers",
    "fashion": "fashion_audience",
    "sports_fitness": "fitness_audience",
    "education": "students_and_parents",
    "auto_transport": "drivers_and_travelers",
    "business": "entrepreneurs",
    "home_design": "homeowners",
    "pets": "pet_owners",
}

SEGMENT_TOPICS = {
    "riderra": {"travel", "auto_transport", "local_places"},
    "veselaya_rascheska": {"family_parenting", "local_places", "events_entertainment"},
    "organika": {"beauty_wellness", "fashion", "local_places"},
}

PLATFORM_FORMATS = {
    "telegram": "telegram_post",
    "youtube": "video",
    "instagram": "visual_post",
    "threads": "short_text_post",
    "tiktok": "short_video",
    "vk": "social_post",
    "website": "article",
}


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
    return re.sub(r"\s+", " ", str(value or "").casefold().replace("ё", "е")).strip()


def _contains(text: str, aliases: tuple[str, ...]) -> bool:
    return any(_normalized(alias) in text for alias in aliases)


def _names_in_text(text: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
    return [name for name, aliases in rules.items() if _contains(text, aliases)]


def _audience_band(followers: int) -> str:
    if followers <= 0:
        return "unknown"
    if followers < 10_000:
        return "nano"
    if followers < 100_000:
        return "micro"
    if followers < 500_000:
        return "mid"
    return "macro"


def _strong_home_city(text: str) -> tuple[str | None, float]:
    patterns = {
        "Санкт-Петербург": (
            r"(?:живу|живем|живём|нахожусь|автор|блогер|канал|сообщество).{0,35}(?:санкт-петербург|петербург|спб|питер)",
            r"(?:петербургский|петербургская|петербургское|spb-based).{0,25}(?:блог|автор|блогер|канал|сообщество|мама|папа)",
            r"(?:из|from)\s+(?:санкт-петербурга|петербурга|спб|питера|saint petersburg)",
        ),
        "Таллинн": (
            r"(?:живу|нахожусь|автор|блогер|канал).{0,35}(?:таллинн|tallinn)",
            r"(?:из|from|based in)\s+(?:таллинна|таллинн|tallinn)",
        ),
        "Москва": (
            r"(?:живу|нахожусь|автор|блогер|канал).{0,35}(?:москва|москве|moscow)",
            r"(?:из|from|based in)\s+(?:москвы|москва|moscow)",
        ),
    }
    matches = [
        city
        for city, city_patterns in patterns.items()
        if any(re.search(pattern, text) for pattern in city_patterns)
    ]
    mentioned_cities = _names_in_text(text, CITY_ALIASES)
    if len(matches) == 1 and len(mentioned_cities) == 1:
        return matches[0], 0.9
    return None, 0.0


def _evidence_sources(profile: dict[str, Any]) -> list[dict[str, Any]]:
    channels = [item for item in _json(profile.get("channels"), []) if isinstance(item, dict)]
    default_url = str(channels[0].get("canonical_url") or "") if channels else ""
    result: list[dict[str, Any]] = []
    description = str(profile.get("description") or "").strip()
    if description:
        result.append({"text": description, "source_url": default_url, "source_type": "public_profile", "confidence": 0.85})
    display_name = str(profile.get("display_name") or "").strip()
    if display_name:
        result.append({"text": display_name, "source_url": default_url, "source_type": "public_identity", "confidence": 0.7})
    for item in _json(profile.get("evidence"), []):
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary_text") or item.get("summary") or item.get("observed") or "").strip()
        if not summary:
            continue
        result.append({
            "text": summary,
            "source_url": str(item.get("source_url") or default_url),
            "source_type": str(item.get("evidence_type") or item.get("source_type") or "public_evidence"),
            "confidence": float(item.get("confidence") or 0.75),
        })
    return result


def _ledger_entry(source: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {
        "fields": sorted(set(fields)),
        "observed": str(source.get("text") or "")[:500],
        "source_url": str(source.get("source_url") or "") or None,
        "source_type": str(source.get("source_type") or "public_evidence"),
        "confidence": round(float(source.get("confidence") or 0), 2),
        "researched_at": datetime.now(timezone.utc).isoformat(),
    }


def classify_creator_profile(profile: dict[str, Any]) -> dict[str, Any]:
    sources = _evidence_sources(profile)
    metadata = _json(profile.get("metadata_json") or profile.get("metadata"), {})
    research = _json(metadata.get("research"), {})
    qualification = _json(metadata.get("qualification"), {})
    discovery_queries = [str(item) for item in _json(research.get("spb_expansion_queries"), []) if str(item).strip()]
    source_text = _normalized(" ".join(str(item.get("text") or "") for item in sources))
    discovery_text = _normalized(" ".join(discovery_queries))

    topic_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    evidence_ledger: list[dict[str, Any]] = []
    city_scores: dict[str, float] = {}
    content_districts: dict[str, float] = {}
    metros: dict[str, float] = {}
    explicit_audience_cities: dict[str, float] = {}
    home_city: str | None = None
    home_city_confidence = 0.0

    for source in sources:
        text = _normalized(source.get("text"))
        source_fields: list[str] = []
        for topic, aliases in TOPIC_RULES.items():
            if _contains(text, aliases):
                topic_counts[topic] += 1
                source_fields.append(f"topic:{topic}")
        for style, aliases in STYLE_RULES.items():
            if _contains(text, aliases):
                style_counts[style] += 1
                source_fields.append(f"style:{style}")
        for city in _names_in_text(text, CITY_ALIASES):
            city_scores[city] = max(city_scores.get(city, 0), min(0.85, float(source.get("confidence") or 0.75)))
            source_fields.append(f"content_city:{city}")
            audience_pattern = rf"(?:аудитори|подписчик|читател).{{0,45}}{re.escape(_normalized(city))}"
            if re.search(audience_pattern, text):
                explicit_audience_cities[city] = max(explicit_audience_cities.get(city, 0), 0.85)
                source_fields.append(f"audience_city:{city}")
        for district in _names_in_text(text, SPB_DISTRICTS):
            content_districts[district] = max(content_districts.get(district, 0), min(0.85, float(source.get("confidence") or 0.75)))
            source_fields.append(f"content_district:{district}")
        for metro in _names_in_text(text, SPB_METROS):
            metros[metro] = max(metros.get(metro, 0), min(0.85, float(source.get("confidence") or 0.75)))
            source_fields.append(f"metro:{metro}")
        candidate_home_city, candidate_confidence = _strong_home_city(text)
        if candidate_home_city and candidate_confidence > home_city_confidence:
            home_city = candidate_home_city
            home_city_confidence = candidate_confidence
            source_fields.append(f"home_city:{candidate_home_city}")
        if source_fields:
            evidence_ledger.append(_ledger_entry(source, source_fields))

    topics = [name for name, _count in topic_counts.most_common()]
    primary_topic = topics[0] if topics else None
    styles = [name for name, _count in style_counts.most_common()]
    home_district = None
    home_district_confidence = 0.0
    if home_city == "Санкт-Петербург":
        for district, aliases in SPB_DISTRICTS.items():
            strong_area_pattern = rf"(?:живу|из|нахожусь|мой район).{{0,35}}(?:{'|'.join(re.escape(_normalized(alias)) for alias in aliases)})"
            if re.search(strong_area_pattern, source_text):
                home_district = district
                home_district_confidence = 0.85
                break

    discovery_geography: list[dict[str, Any]] = []
    for city in _names_in_text(discovery_text, CITY_ALIASES):
        discovery_geography.append({"kind": "city", "name": city, "confidence": 0.25, "basis": "discovery_query"})
    for district in _names_in_text(discovery_text, SPB_DISTRICTS):
        discovery_geography.append({"kind": "district", "name": district, "confidence": 0.25, "basis": "discovery_query"})
    for metro in _names_in_text(discovery_text, SPB_METROS):
        discovery_geography.append({"kind": "metro", "name": metro, "confidence": 0.25, "basis": "discovery_query"})

    content_geographies = [
        *({"kind": "city", "name": city, "confidence": round(confidence, 2), "basis": "public_evidence"} for city, confidence in city_scores.items()),
        *({"kind": "district", "name": district, "confidence": round(confidence, 2), "basis": "public_evidence"} for district, confidence in content_districts.items()),
    ]
    audience_geography = [
        {"kind": "city", "name": city, "confidence": round(confidence, 2), "basis": "explicit_audience_statement"}
        for city, confidence in explicit_audience_cities.items()
    ]

    channels = [item for item in _json(profile.get("channels"), []) if isinstance(item, dict)]
    observed_formats = sorted({
        PLATFORM_FORMATS[str(channel.get("platform") or "")]
        for channel in channels
        if str(channel.get("platform") or "") in PLATFORM_FORMATS
    })
    commercial = _json(profile.get("commercial"), {})
    confirmed_formats = [str(item) for item in _json(commercial.get("formats_json") or commercial.get("formats"), []) if str(item).strip()]
    follower_values = []
    for channel in channels:
        metrics = _json(channel.get("public_metrics_json") or channel.get("public_metrics"), {})
        metadata_values = _json(channel.get("metadata_json") or channel.get("metadata"), {})
        raw_followers = metrics.get("followers") or channel.get("follower_count") or metadata_values.get("follower_count") or 0
        try:
            follower_values.append(int(raw_followers))
        except (TypeError, ValueError):
            continue
    audience_size_band = _audience_band(max(follower_values, default=0))
    audience_types = sorted({AUDIENCE_BY_TOPIC[topic] for topic in topics if topic in AUDIENCE_BY_TOPIC})

    prior_segment_fit = {str(item) for item in _json(qualification.get("business_fit_candidates"), []) if str(item)}
    segment_fit: dict[str, Any] = {}
    topic_set = set(topics)
    evidence_urls = sorted({str(item.get("source_url")) for item in evidence_ledger if item.get("source_url")})
    for segment, segment_topics in SEGMENT_TOPICS.items():
        matches = sorted(topic_set.intersection(segment_topics))
        score = min(100, len(matches) * 28 + (15 if segment in prior_segment_fit else 0))
        confidence = min(0.95, 0.45 + len(matches) * 0.15) if matches else 0.3 if segment in prior_segment_fit else 0.0
        segment_fit[segment] = {
            "score": score,
            "confidence": round(confidence, 2),
            "matched_topics": matches,
            "prior_shortlist_signal": segment in prior_segment_fit,
            "evidence_urls": evidence_urls[:8],
        }

    topic_confidence = min(0.95, 0.55 + 0.1 * topic_counts.get(primary_topic, 0)) if primary_topic else 0.0
    style_confidence = min(0.9, 0.5 + 0.1 * max(style_counts.values(), default=0)) if styles else 0.0
    classification_status = "automated" if primary_topic and (city_scores or content_districts) and evidence_urls else "needs_review"
    return {
        "primary_topic": primary_topic,
        "secondary_topics": topics[1:],
        "content_styles": styles,
        "observed_formats": observed_formats,
        "confirmed_formats": confirmed_formats,
        "home_city": home_city,
        "home_district": home_district,
        "metro_stations": sorted(metros),
        "discovery_geography": discovery_geography,
        "content_geographies": content_geographies,
        "audience_geography": audience_geography,
        "audience_types": audience_types,
        "audience_size_band": audience_size_band,
        "segment_fit": segment_fit,
        "confidence": {
            "home_city": round(home_city_confidence, 2),
            "home_district": round(home_district_confidence, 2),
            "topics": round(topic_confidence, 2),
            "content_style": round(style_confidence, 2),
            "audience_geography": max(explicit_audience_cities.values(), default=0.0),
            "classification": round(min(0.95, 0.35 + 0.08 * len(evidence_ledger)), 2),
        },
        "evidence": evidence_ledger,
        "classification_status": classification_status,
        "classification_version": CLASSIFICATION_VERSION,
    }


def upsert_creator_taxonomy(cursor: Any, *, profile_id: str, taxonomy: dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO creator_profile_taxonomy (
            creator_profile_id, primary_topic, secondary_topics_json,
            content_styles_json, observed_formats_json, confirmed_formats_json,
            home_city, home_district, metro_stations_json,
            discovery_geography_json, content_geographies_json,
            audience_geography_json, audience_types_json, audience_size_band,
            segment_fit_json, confidence_json, evidence_json,
            classification_status, classification_version, classified_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (creator_profile_id) DO UPDATE SET
            primary_topic = EXCLUDED.primary_topic,
            secondary_topics_json = EXCLUDED.secondary_topics_json,
            content_styles_json = EXCLUDED.content_styles_json,
            observed_formats_json = EXCLUDED.observed_formats_json,
            confirmed_formats_json = CASE
                WHEN creator_profile_taxonomy.confirmed_formats_json = '[]'::jsonb
                THEN EXCLUDED.confirmed_formats_json
                ELSE creator_profile_taxonomy.confirmed_formats_json
            END,
            home_city = EXCLUDED.home_city,
            home_district = EXCLUDED.home_district,
            metro_stations_json = EXCLUDED.metro_stations_json,
            discovery_geography_json = EXCLUDED.discovery_geography_json,
            content_geographies_json = EXCLUDED.content_geographies_json,
            audience_geography_json = EXCLUDED.audience_geography_json,
            audience_types_json = EXCLUDED.audience_types_json,
            audience_size_band = EXCLUDED.audience_size_band,
            segment_fit_json = EXCLUDED.segment_fit_json,
            confidence_json = EXCLUDED.confidence_json,
            evidence_json = EXCLUDED.evidence_json,
            classification_status = CASE
                WHEN creator_profile_taxonomy.classification_status = 'reviewed' THEN 'reviewed'
                ELSE EXCLUDED.classification_status
            END,
            classification_version = EXCLUDED.classification_version,
            classified_at = NOW(), updated_at = NOW()
        """,
        (
            profile_id, taxonomy["primary_topic"], Json(taxonomy["secondary_topics"]),
            Json(taxonomy["content_styles"]), Json(taxonomy["observed_formats"]), Json(taxonomy["confirmed_formats"]),
            taxonomy["home_city"], taxonomy["home_district"], Json(taxonomy["metro_stations"]),
            Json(taxonomy["discovery_geography"]), Json(taxonomy["content_geographies"]),
            Json(taxonomy["audience_geography"]), Json(taxonomy["audience_types"]), taxonomy["audience_size_band"],
            Json(taxonomy["segment_fit"]), Json(taxonomy["confidence"]), Json(taxonomy["evidence"]),
            taxonomy["classification_status"], taxonomy["classification_version"],
        ),
    )


def _catalog_profiles(cursor: Any, *, import_source: str, limit: int | None = None) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT profile.*,
               COALESCE(channel.items_json, '[]'::jsonb) AS channels,
               COALESCE(evidence.items_json, '[]'::jsonb) AS evidence,
               COALESCE(commercial.item_json, '{}'::jsonb) AS commercial
        FROM creator_profiles profile
        LEFT JOIN LATERAL (
            SELECT JSONB_AGG(JSONB_BUILD_OBJECT(
                'platform', item.platform,
                'canonical_url', item.canonical_url,
                'public_metrics_json', item.public_metrics_json,
                'metadata_json', item.metadata_json,
                'verification_status', item.verification_status
            )) AS items_json
            FROM creator_channels item WHERE item.creator_profile_id = profile.id
        ) channel ON TRUE
        LEFT JOIN LATERAL (
            SELECT JSONB_AGG(JSONB_BUILD_OBJECT(
                'evidence_type', item.evidence_type,
                'summary_text', item.summary_text,
                'source_url', item.source_url,
                'confidence', item.confidence,
                'observed_at', item.observed_at
            )) AS items_json
            FROM creator_evidence item WHERE item.creator_profile_id = profile.id
        ) evidence ON TRUE
        LEFT JOIN LATERAL (
            SELECT TO_JSONB(item) AS item_json
            FROM creator_commercial_profiles item WHERE item.creator_profile_id = profile.id
        ) commercial ON TRUE
        WHERE profile.metadata_json->>'import_source' = %s
        ORDER BY profile.id
        LIMIT %s
        """,
        (import_source, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def classify_creator_catalog(
    cursor: Any,
    *,
    import_source: str = "spb_catalog_20260823",
    limit: int | None = None,
    normalize_profile_geography: bool = True,
) -> dict[str, Any]:
    profiles = _catalog_profiles(cursor, import_source=import_source, limit=limit)
    summary: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    for profile in profiles:
        taxonomy = classify_creator_profile(profile)
        upsert_creator_taxonomy(cursor, profile_id=str(profile["id"]), taxonomy=taxonomy)
        if normalize_profile_geography:
            cursor.execute(
                """
                UPDATE creator_profiles SET primary_city = %s, primary_area = %s,
                    topics_json = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (
                    taxonomy["home_city"], taxonomy["home_district"],
                    Json([item for item in [taxonomy["primary_topic"], *taxonomy["secondary_topics"]] if item]),
                    profile["id"],
                ),
            )
        summary["classified"] += 1
        summary[taxonomy["classification_status"]] += 1
        if taxonomy["home_city"]:
            summary["home_city"] += 1
        if taxonomy["home_district"]:
            summary["home_district"] += 1
        if taxonomy["metro_stations"]:
            summary["metro"] += 1
        if taxonomy["audience_geography"]:
            summary["audience_geography"] += 1
        if taxonomy["primary_topic"]:
            topics[taxonomy["primary_topic"]] += 1
    return {
        **dict(summary),
        "topics": dict(topics.most_common()),
        "import_source": import_source,
        "classification_version": CLASSIFICATION_VERSION,
    }
