from __future__ import annotations

import re
from typing import Any


UNSAFE_PATTERNS = [
    "порно",
    "эрот",
    "секс",
    "интим",
    "эскорт",
    "escort",
    "xxx",
    "наркот",
    "закладк",
    "казино",
    "ставк",
    "букмекер",
]


CATEGORY_RULES: dict[str, dict[str, list[str]]] = {
    "biozavivka": {
        "triggers": ["афро", "афрокуд", "биозавив", "завив", "кудр"],
        "anchors": ["волос", "кудр", "завив", "биозавив", "афрокудр"],
        "safe_seeds": ["афрокудри", "биозавивка афрокудри", "завивка афрокудри"],
    },
    "brows_lashes": {
        "triggers": ["бров", "ресниц", "ламинирование ресниц"],
        "anchors": ["бров", "ресниц", "ламинирован", "коррекц"],
        "safe_seeds": ["коррекция бровей", "ламинирование ресниц"],
    },
    "makeup": {
        "triggers": ["макияж", "визаж", "мейк"],
        "anchors": ["макияж", "визаж", "мейк"],
        "safe_seeds": ["макияж", "визаж"],
    },
    "kids": {
        "triggers": ["детск", "ребен", "дети", "12 15", "подрост"],
        "anchors": ["детск", "ребен", "дети", "подрост", "стриж"],
        "safe_seeds": ["детская стрижка", "детская укладка"],
    },
    "injection_cosmetology": {
        "triggers": ["биоревитал", "ботул", "инъекц", "belarti", "ml", "мл"],
        "anchors": ["биоревитал", "ботул", "инъекц", "косметолог", "препарат", "ml", "мл"],
        "safe_seeds": ["биоревитализация", "инъекционная косметология"],
    },
}


def normalize_query_text(value: Any) -> str:
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


def detect_service_keyword_category(service: dict[str, Any]) -> str:
    text = normalize_query_text(" ".join([
        str(service.get("category") or ""),
        str(service.get("name") or ""),
        str(service.get("description") or ""),
    ]))
    for category_key, rules in CATEGORY_RULES.items():
        for trigger in rules.get("triggers") or []:
            if normalize_query_text(trigger) in text:
                return category_key
    return "generic"


def extract_service_attributes(service: dict[str, Any]) -> dict[str, Any]:
    text = normalize_query_text(" ".join([
        str(service.get("category") or ""),
        str(service.get("name") or ""),
        str(service.get("description") or ""),
    ]))
    attributes: dict[str, Any] = {
        "category": detect_service_keyword_category(service),
        "hair_length": None,
        "gender": None,
        "age": None,
        "brand_or_drug": None,
        "volume": None,
        "zones": None,
    }
    if "экстра длин" in text:
        attributes["hair_length"] = "экстра длинные волосы"
    elif "длин" in text:
        attributes["hair_length"] = "длинные волосы"
    if "муж" in text:
        attributes["gender"] = "мужская"
    age_match = re.search(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b", text)
    if age_match:
        attributes["age"] = f"{age_match.group(1)}-{age_match.group(2)} лет"
    volume_match = re.search(r"\b\d+(?:[,.]\d+)?\s*(?:ml|мл)\b", text)
    if volume_match:
        attributes["volume"] = volume_match.group(0)
    zone_match = re.search(r"\b\d+\s*зон", text)
    if zone_match:
        attributes["zones"] = zone_match.group(0)
    brand_match = re.search(r"\bbelarti\s+[a-zа-я0-9]+\b", text)
    if brand_match:
        attributes["brand_or_drug"] = brand_match.group(0)
    return attributes


def build_safe_seed_queries(service: dict[str, Any], limit: int = 8) -> list[str]:
    attributes = extract_service_attributes(service)
    category_key = str(attributes.get("category") or "generic")
    rules = CATEGORY_RULES.get(category_key) or {}
    seeds: list[str] = []
    for seed in rules.get("safe_seeds") or []:
        seeds.append(seed)
    name = normalize_query_text(service.get("name"))
    category = normalize_query_text(service.get("category"))
    if category_key == "biozavivka" and "афро" in name:
        seeds.extend(["афрокудри", "биозавивка афрокудри", "завивка афрокудри"])
        if attributes.get("hair_length"):
            seeds.append(f"афрокудри на {attributes['hair_length']}")
    elif name:
        safe_name = name
        if len(safe_name) >= 5:
            seeds.append(safe_name)
    if category and len(category) >= 5:
        seeds.append(category)

    unique: list[str] = []
    for seed in seeds:
        normalized = normalize_query_text(seed)
        if not normalized or normalized in unique:
            continue
        if len(normalized) < 5:
            continue
        unique.append(normalized)
    return unique[:limit]


def is_unsafe_query(query: str) -> tuple[bool, str | None]:
    normalized = normalize_query_text(query)
    for pattern in UNSAFE_PATTERNS:
        if pattern in normalized:
            return True, "unsafe_blacklist"
    return False, None


def filter_wordstat_candidates(
    candidates: list[dict[str, Any]],
    category_key: str,
    limit: int = 12,
) -> dict[str, Any]:
    rules = CATEGORY_RULES.get(category_key) or {}
    anchors = [normalize_query_text(anchor) for anchor in rules.get("anchors") or []]
    allowed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        keyword = str(candidate.get("keyword") or candidate.get("query") or "").strip()
        normalized = normalize_query_text(keyword)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unsafe, reason = is_unsafe_query(normalized)
        if unsafe:
            blocked.append({**candidate, "keyword": keyword, "reason": reason})
            continue
        if anchors and not any(anchor in normalized for anchor in anchors):
            blocked.append({**candidate, "keyword": keyword, "reason": "missing_category_anchor"})
            continue
        allowed.append({**candidate, "keyword": keyword})
        if len(allowed) >= limit:
            break
    return {
        "allowed": allowed,
        "blocked": blocked,
        "anchors": anchors,
        "category": category_key,
    }
