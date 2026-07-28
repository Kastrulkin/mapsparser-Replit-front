"""Conservative geocoding helpers for canonical company locations."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

import requests


NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "LocalOS-company-registry/1.0 (+https://localos.pro; support@localos.pro)"
NOMINATIM_ATTRIBUTION = "© OpenStreetMap contributors, ODbL"

_PRECISE_ADDRESS_TYPES = {
    "house",
    "building",
    "amenity",
    "shop",
    "office",
    "commercial",
    "retail",
    "restaurant",
    "cafe",
    "clinic",
    "school",
    "kindergarten",
    "yes",
}
_BROAD_ADDRESS_TYPES = {
    "country",
    "state",
    "region",
    "province",
    "county",
    "city",
    "town",
    "village",
    "municipality",
    "administrative",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _fold(value: Any) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", " ", _clean(value).lower()).strip()


def _append_country(parts: list[str]) -> str:
    query = ", ".join(dict.fromkeys(part for part in parts if part))
    lowered = query.lower()
    if re.search(r"[а-яё]", lowered) and not any(
        marker in lowered for marker in ("россия", "russia", "russian federation")
    ):
        query = f"{query}, Россия"
    return query


def _compact_building(value: str) -> str:
    compacted = re.sub(r"\bкорп(?:ус)?\.?\s*(\d+)", r"к\1", value, flags=re.IGNORECASE)
    compacted = re.sub(r"\bлит(?:ера)?\.?\s*([a-zа-яё])", r"лит\1", compacted, flags=re.IGNORECASE)
    return _clean(compacted)


def _simplify_locality(value: str) -> str:
    return re.sub(
        r"^(?:пос[её]лок\s+городского\s+типа|пос[её]лок|город)\s+",
        "",
        _clean(value),
        flags=re.IGNORECASE,
    )


def build_geocoding_queries(location: dict[str, Any]) -> list[str]:
    """Build ordered address variants; all contain public location data only."""
    address = _clean(location.get("address"))
    if not address:
        return []
    raw_parts = [_clean(part) for part in address.split(",") if _clean(part)]
    numeric_indexes = [
        index for index, part in enumerate(raw_parts) if re.search(r"\d", part)
    ]
    parts: list[str]
    if numeric_indexes:
        house_index = numeric_indexes[0]
        if house_index > 0:
            house_parts = raw_parts[house_index:]
            street = raw_parts[house_index - 1]
            locality = raw_parts[: house_index - 1]
            parts = [" ".join(house_parts), street, *reversed(locality)]
        else:
            parts = list(raw_parts)
    else:
        parts = list(raw_parts)
    folded_address = _fold(" ".join(parts))
    extra_parts: list[str] = []
    for field in ("city", "region", "country"):
        value = _clean(location.get(field))
        if value and _fold(value) not in folded_address:
            extra_parts.append(value)

    queries = [_append_country([*parts, *extra_parts])]
    compact_parts = [_compact_building(part) for part in parts]
    compact_query = _append_country([*compact_parts, *extra_parts])
    queries.append(compact_query)

    if len(parts) >= 2:
        city = _clean(location.get("city"))
        concise_parts = [compact_parts[0], compact_parts[1]]
        nearest_locality = compact_parts[2] if len(compact_parts) > 2 else ""
        if nearest_locality:
            concise_parts.append(nearest_locality)
        if city:
            concise_parts.append(city)
        concise_query = _append_country(concise_parts)
        queries.append(concise_query)
        if nearest_locality:
            queries.append(_append_country([
                compact_parts[0],
                compact_parts[1],
                _simplify_locality(nearest_locality),
            ]))

        main_house = re.match(r"\d+(?:[/-]\d+)*", compact_parts[0], flags=re.IGNORECASE)
        if main_house:
            queries.append(_append_country([
                main_house.group(0),
                compact_parts[1],
                _simplify_locality(nearest_locality),
                city,
            ]))

    abbreviation_replacements = {
        "Васильевского острова": "В.О.",
        "васильевского острова": "В.О.",
    }
    for query in list(queries):
        abbreviated = query
        for source, target in abbreviation_replacements.items():
            abbreviated = abbreviated.replace(source, target)
        queries.append(abbreviated)
    return list(dict.fromkeys(query for query in queries if query))


def build_geocoding_query(location: dict[str, Any]) -> str:
    queries = build_geocoding_queries(location)
    return queries[0] if queries else ""


def cache_key(query: str) -> str:
    return hashlib.sha256(_fold(query).encode("utf-8")).hexdigest()


def _query_house_token(query: str) -> str:
    first_part = query.split(",", 1)[0]
    candidates = re.findall(r"\b\d+[0-9a-zа-яё/\-]*", first_part.lower())
    return candidates[0] if candidates else ""


def _compact_house(value: Any) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", _clean(value).lower())


def score_candidate(
    query: str,
    expected_city: str,
    candidate: dict[str, Any],
) -> tuple[float, list[str]]:
    """Score a Nominatim result; broad administrative matches are rejected."""
    reasons: list[str] = []
    try:
        latitude = candidate.get("lat")
        longitude = candidate.get("lon")
        if latitude is None or longitude is None:
            return 0.0, ["missing_coordinates"]
        latitude_value = float(latitude)
        longitude_value = float(longitude)
        if not (-90 <= latitude_value <= 90 and -180 <= longitude_value <= 180):
            return 0.0, ["invalid_coordinates"]
    except (TypeError, ValueError):
        return 0.0, ["invalid_coordinates"]

    result_type = _fold(candidate.get("addresstype") or candidate.get("type"))
    if result_type in _BROAD_ADDRESS_TYPES:
        return 0.0, ["administrative_result"]

    display_name = _fold(candidate.get("display_name"))
    address = candidate.get("address") if isinstance(candidate.get("address"), dict) else {}
    score = 0.25
    reasons.append("valid_coordinates")

    city = _fold(expected_city)
    if city:
        city_values = {
            _fold(address.get(key))
            for key in ("city", "town", "village", "municipality", "county")
            if address.get(key)
        }
        if city in display_name or city in city_values:
            score += 0.25
            reasons.append("city_match")
        else:
            reasons.append("city_mismatch")
    else:
        score += 0.10
        reasons.append("city_not_provided")

    house_token = _query_house_token(query)
    result_house = _compact_house(address.get("house_number"))
    if house_token:
        compact_query_house = _compact_house(house_token)
        if result_house and (
            compact_query_house == result_house
            or result_house.startswith(compact_query_house)
            or compact_query_house.startswith(result_house)
        ):
            score += 0.35
            reasons.append("house_match")
        else:
            reasons.append("house_mismatch")
    else:
        score += 0.15
        reasons.append("house_not_provided")

    if result_type in _PRECISE_ADDRESS_TYPES or result_house:
        score += 0.20
        reasons.append("precise_result")
    else:
        reasons.append("imprecise_result")

    return min(score, 1.0), reasons


def choose_candidate(
    query: str,
    expected_city: str,
    candidates: list[dict[str, Any]],
    minimum_confidence: float = 0.75,
) -> dict[str, Any] | None:
    scored: list[tuple[float, list[str], dict[str, Any]]] = []
    for candidate in candidates:
        score, reasons = score_candidate(query, expected_city, candidate)
        scored.append((score, reasons, candidate))
    if not scored:
        return None
    score, reasons, candidate = max(scored, key=lambda item: item[0])
    if score < minimum_confidence:
        return None
    return {
        "latitude": float(candidate["lat"]),
        "longitude": float(candidate["lon"]),
        "confidence": round(score, 2),
        "confidence_reasons": reasons,
        "formatted_address": _clean(candidate.get("display_name")),
        "osm_type": _clean(candidate.get("osm_type")),
        "osm_id": candidate.get("osm_id"),
        "address_type": _clean(candidate.get("addresstype") or candidate.get("type")),
    }


class NominatimGeocoder:
    """Single-threaded, cached client compliant with the public usage policy."""

    def __init__(self, cache_path: Path, minimum_interval_seconds: float = 1.05):
        self.cache_path = cache_path
        self.minimum_interval_seconds = max(1.0, minimum_interval_seconds)
        self.session = requests.Session()
        self.last_request_at = 0.0
        self.cache = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.cache_path.with_suffix(f"{self.cache_path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.cache_path)

    def lookup(self, query: str) -> tuple[list[dict[str, Any]], bool]:
        key = cache_key(query)
        cached = self.cache.get(key)
        if isinstance(cached, dict) and isinstance(cached.get("items"), list):
            return cached["items"], True

        elapsed = time.monotonic() - self.last_request_at
        if elapsed < self.minimum_interval_seconds:
            time.sleep(self.minimum_interval_seconds - elapsed)
        response = self.session.get(
            NOMINATIM_ENDPOINT,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 3,
                "addressdetails": 1,
            },
            headers={
                "User-Agent": NOMINATIM_USER_AGENT,
                "Accept-Language": "ru,en;q=0.7",
            },
            timeout=20,
        )
        self.last_request_at = time.monotonic()
        response.raise_for_status()
        payload = response.json()
        items = payload if isinstance(payload, list) else []
        self.cache[key] = {
            "query": query,
            "items": items,
            "provider": "nominatim_openstreetmap",
            "attribution": NOMINATIM_ATTRIBUTION,
        }
        self._save_cache()
        return items, False
