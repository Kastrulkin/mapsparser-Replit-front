from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from core.map_url_normalizer import normalize_map_url


MAP_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def extract_urls(text: Any) -> list[str]:
    raw_text = str(text or "").strip()
    if not raw_text:
        return []
    seen: list[str] = []
    for match in MAP_URL_RE.findall(raw_text):
        candidate = str(match or "").strip().rstrip(".,);]")
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen


def classify_map_url(raw_url: Any) -> dict[str, Any]:
    original_url = str(raw_url or "").strip()
    normalized_url = normalize_map_url(original_url)
    if not normalized_url:
        return {
            "ok": False,
            "kind": "empty",
            "normalized_url": "",
            "source": None,
            "message": "Пришлите ссылку на карточку бизнеса.",
        }

    parsed = urlparse(normalized_url)
    host = str(parsed.netloc or "").lower()
    path = str(parsed.path or "").lower()
    query = str(parsed.query or "").lower()

    if "yandex." in host:
        if "/maps/org/" in path:
            return {
                "ok": True,
                "kind": "business_card",
                "normalized_url": normalized_url,
                "source": "yandex",
                "message": "",
            }
        return {
            "ok": False,
            "kind": "unsupported_yandex",
            "normalized_url": normalized_url,
            "source": "yandex",
            "message": "Похоже, это ссылка не на карточку организации Яндекс. Пришлите ссылку вида yandex.ru/maps/org/...",
        }

    if "2gis." in host:
        if "/firm/" in path or "/geo/" in path:
            return {
                "ok": True,
                "kind": "business_card",
                "normalized_url": normalized_url,
                "source": "2gis",
                "message": "",
            }
        return {
            "ok": False,
            "kind": "unsupported_2gis",
            "normalized_url": normalized_url,
            "source": "2gis",
            "message": "Похоже, это ссылка не на карточку 2ГИС. Пришлите ссылку на конкретную организацию.",
        }

    if "google." in host and "/maps" in path:
        if "/maps/place/" in path or "place_id=" in query or "cid=" in query:
            return {
                "ok": True,
                "kind": "business_card",
                "normalized_url": normalized_url,
                "source": "google",
                "message": "",
            }
        return {
            "ok": False,
            "kind": "unsupported_google",
            "normalized_url": normalized_url,
            "source": "google",
            "message": "Похоже, это ссылка не на карточку Google Maps. Пришлите ссылку на конкретное место.",
        }

    return {
        "ok": False,
        "kind": "unsupported_source",
        "normalized_url": normalized_url,
        "source": None,
        "message": "Сейчас поддерживаются ссылки на Яндекс Карты, 2ГИС и Google Maps.",
    }


def parse_map_links_from_text(text: Any) -> dict[str, Any]:
    urls = extract_urls(text)
    if not urls:
        return {
            "ok": False,
            "items": [],
            "valid_items": [],
            "message": "Не вижу ссылки. Пришлите ссылку на карточку бизнеса целиком.",
        }

    items = [classify_map_url(url) for url in urls]
    valid_items = [item for item in items if item.get("ok")]
    if valid_items:
        return {
            "ok": True,
            "items": items,
            "valid_items": valid_items,
            "message": "",
        }

    first_error = next((str(item.get("message") or "").strip() for item in items if str(item.get("message") or "").strip()), "")
    return {
        "ok": False,
        "items": items,
        "valid_items": [],
        "message": first_error or "Не удалось распознать ссылку на карточку бизнеса.",
    }
