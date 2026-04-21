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

_KEEP_GOOGLE_KEYS = {"cid", "q", "query", "place_id"}


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
    if "google." in netloc and "/maps" in path:
        path = _normalize_google_path(path)
        filtered_pairs = []
        for key, val in query_pairs:
            lowered_key = str(key or "").lower()
            if lowered_key in _KEEP_GOOGLE_KEYS:
                filtered_pairs.append((key, val))
        query_pairs = filtered_pairs
    else:
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
