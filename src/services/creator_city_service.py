from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any


CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "Санкт-Петербург": (
        "санкт-петербург", "санкт петербург", "с.-петербург", "петербург",
        "петербурге", "питер", "питере", "спб", "saint petersburg", "st petersburg", "st. petersburg",
    ),
    "Москва": ("москва", "москве", "мск", "moscow"),
    "Таллинн": ("таллинн", "таллин", "tallinn"),
    "Нижний Новгород": ("нижний новгород", "нижнем новгороде", "nizhny novgorod"),
    "Великий Новгород": ("великий новгород", "новгород", "veliky novgorod"),
    "Екатеринбург": ("екатеринбург", "екб", "yekaterinburg", "ekaterinburg"),
    "Новосибирск": ("новосибирск", "нск", "novosibirsk"),
    "Казань": ("казань", "kazan"),
    "Краснодар": ("краснодар", "krd", "krasnodar"),
    "Ростов-на-Дону": ("ростов-на-дону", "ростов на дону", "ростове-на-дону", "rostov-on-don"),
    "Сочи": ("сочи", "sochi"),
    "Батуми": ("батуми", "batumi"),
}


def normalize_city_key(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"^(?:г(?:ород)?[.\s,:-]+)", "", text)
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return " ".join(text.split())


def _alias_index() -> dict[str, str]:
    result: dict[str, str] = {}
    for canonical, aliases in CITY_ALIASES.items():
        for value in (canonical, *aliases):
            result[normalize_city_key(value)] = canonical
    return result


ALIAS_INDEX = _alias_index()


def _typo_threshold(value: str) -> float:
    if len(value) >= 10:
        return 0.82
    if len(value) >= 6:
        return 0.87
    return 0.92


def _edit_distance(left: str, right: str) -> int:
    distances = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for left_index in range(len(left) + 1):
        distances[left_index][0] = left_index
    for right_index in range(len(right) + 1):
        distances[0][right_index] = right_index
    for left_index in range(1, len(left) + 1):
        for right_index in range(1, len(right) + 1):
            cost = 0 if left[left_index - 1] == right[right_index - 1] else 1
            distances[left_index][right_index] = min(
                distances[left_index - 1][right_index] + 1,
                distances[left_index][right_index - 1] + 1,
                distances[left_index - 1][right_index - 1] + cost,
            )
            if (
                left_index > 1
                and right_index > 1
                and left[left_index - 1] == right[right_index - 2]
                and left[left_index - 2] == right[right_index - 1]
            ):
                distances[left_index][right_index] = min(
                    distances[left_index][right_index],
                    distances[left_index - 2][right_index - 2] + 1,
                )
    return distances[-1][-1]


def _looks_like_typo(value: str, candidate: str) -> bool:
    maximum_distance = 2 if max(len(value), len(candidate)) >= 9 else 1
    return (
        min(len(value), len(candidate)) >= 4
        and _edit_distance(value, candidate) <= maximum_distance
    ) or SequenceMatcher(None, value, candidate).ratio() >= _typo_threshold(value)


def canonicalize_city(value: Any, available: list[str] | None = None) -> str:
    raw = str(value or "").strip()
    key = normalize_city_key(raw)
    if not key:
        return ""
    if key in ALIAS_INDEX:
        return ALIAS_INDEX[key]
    known_match = max(
        ALIAS_INDEX,
        key=lambda candidate: SequenceMatcher(None, key, candidate).ratio(),
        default="",
    )
    if known_match and _looks_like_typo(key, known_match):
        return ALIAS_INDEX[known_match]
    choices = [item for item in (available or []) if normalize_city_key(item)]
    exact = next((item for item in choices if normalize_city_key(item) == key), None)
    if exact:
        return exact
    if choices:
        closest = max(choices, key=lambda item: SequenceMatcher(None, key, normalize_city_key(item)).ratio())
        if _looks_like_typo(key, normalize_city_key(closest)):
            return closest
    cleaned = re.sub(r"\s*[-–—]\s*", "-", raw)
    return cleaned[:1].upper() + cleaned[1:]


def city_search_terms(value: Any) -> list[str]:
    canonical = canonicalize_city(value)
    aliases = CITY_ALIASES.get(canonical, ())
    return sorted({normalize_city_key(item) for item in (canonical, *aliases) if normalize_city_key(item)})


def city_matches(value: Any, expected: Any) -> bool:
    haystack = normalize_city_key(value)
    if not haystack:
        return False
    canonical_expected = canonicalize_city(expected)
    return any(term == haystack or f" {term} " in f" {haystack} " for term in city_search_terms(canonical_expected))


def available_creator_cities(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT city, COUNT(*)::INT AS profiles
        FROM (
            SELECT COALESCE(NULLIF(taxonomy.home_city, ''), NULLIF(profile.primary_city, '')) AS city
            FROM creator_profiles profile
            LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
            WHERE profile.verification_status <> 'rejected'
        ) source
        WHERE city IS NOT NULL
        GROUP BY city
        ORDER BY COUNT(*) DESC, city
        """
    )
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "aliases": set()})
    rows = [(str(row["city"]), int(row["profiles"] or 0)) for row in cursor.fetchall()]
    common = [canonicalize_city(city) for city, count in rows if count >= 2]
    for raw_city, count in rows:
        canonical = canonicalize_city(raw_city, common)
        grouped[canonical]["count"] += count
        grouped[canonical]["aliases"].add(raw_city)
    return [
        {"name": name, "count": item["count"], "aliases": sorted(item["aliases"])}
        for name, item in sorted(grouped.items(), key=lambda pair: (-pair[1]["count"], pair[0]))
        if name
    ]


def canonicalize_geography(value: Any, available: list[str] | None = None) -> dict[str, Any]:
    geography = dict(value) if isinstance(value, dict) else {}
    if geography.get("city"):
        geography["city"] = canonicalize_city(geography["city"], available)
    if isinstance(geography.get("cities"), list):
        cities = [canonicalize_city(item, available) for item in geography["cities"]]
        geography["cities"] = list(dict.fromkeys(city for city in cities if city))
    return geography
