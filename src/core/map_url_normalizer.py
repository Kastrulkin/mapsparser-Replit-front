from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


_DROP_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "entry",
    "g_ep",
    "ved",
    "z",
    "ll",
    "sll",
    "rtext",
    "rtt",
    "si",
}

_KEEP_GOOGLE_KEYS = {"cid", "kgmid", "ludocid", "q", "query", "place_id", "stick"}

_DROP_TRAILING_MAP_SECTIONS = {
    "reviews",
    "photos",
    "photo",
    "gallery",
    "menu",
    "prices",
    "price",
    "services",
    "features",
    "inside",
    "panorama",
}


def _normalize_google_path(path: str) -> str:
    clean_path = str(path or "")
    place_marker = "/maps/place/"
    marker_pos = clean_path.find(place_marker)
    if marker_pos < 0:
        return clean_path.rstrip("/") or "/"
    suffix = clean_path[marker_pos + len(place_marker) :]
    parts = [part for part in suffix.split("/") if part]
    if not parts:
        return "/maps/place"
    # Keep only slug and optional @coords. Drop heavy /data/... tails.
    kept = parts[:2]
    return "/maps/place/" + "/".join(kept)


def is_google_map_url(raw_url: Any) -> bool:
    value = str(raw_url or "").strip().lower()
    if not value:
        return False
    if "maps.app.goo.gl" in value or "share.google" in value:
        return True
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=False)}
    if "google." not in host:
        return False
    if "/maps" in path:
        return True
    if path == "/search" and query_keys.intersection({"cid", "kgmid", "ludocid", "stick"}):
        return True
    return False


def _drop_trailing_map_section(path: str) -> str:
    parts = [part for part in str(path or "").split("/") if part]
    if not parts:
        return "/"
    while parts and parts[-1].lower() in _DROP_TRAILING_MAP_SECTIONS:
        parts.pop()
    return "/" + "/".join(parts) if parts else "/"


def normalize_map_url(raw_url: Any) -> str:
    value = str(raw_url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value.rstrip("/")

    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    query_pairs = parse_qsl(parsed.query, keep_blank_values=False)

    # Normalize Google Maps URLs to a stable place format.
    if is_google_map_url(value):
        if "google." in netloc and "/maps" in path:
            path = _normalize_google_path(path)
        filtered_pairs = []
        for key, val in query_pairs:
            lowered_key = str(key or "").lower()
            if lowered_key in _KEEP_GOOGLE_KEYS:
                filtered_pairs.append((key, val))
        query_pairs = filtered_pairs
    else:
        if "yandex." in netloc or "2gis." in netloc or "maps.apple." in netloc or "maps.apple.com" in netloc:
            path = _drop_trailing_map_section(path)
        filtered_pairs = []
        for key, val in query_pairs:
            lowered_key = str(key or "").lower()
            if lowered_key in _DROP_QUERY_KEYS:
                continue
            filtered_pairs.append((key, val))
        query_pairs = filtered_pairs

    normalized_query = urlencode(query_pairs, doseq=True)
    normalized = urlunparse((scheme, netloc, path.rstrip("/") or "/", "", normalized_query, ""))
    return normalized.rstrip("/")
