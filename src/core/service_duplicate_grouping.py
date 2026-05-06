from __future__ import annotations

import re
from typing import Any


def normalize_service_canonical_text(value: Any) -> str:
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


def build_service_duplicate_key(service: dict[str, Any]) -> str:
    return "|".join([
        normalize_service_canonical_text(service.get("category")),
        normalize_service_canonical_text(service.get("name")),
        normalize_service_canonical_text(service.get("price")),
    ])


def build_service_duplicate_groups(services: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for service in services:
        service_id = str(service.get("id") or "").strip()
        key = build_service_duplicate_key(service)
        if not key or key == "||":
            continue
        group = groups.setdefault(key, {"key": key, "service_ids": [], "count": 0})
        if service_id:
            group["service_ids"].append(service_id)
        group["count"] = int(group.get("count") or 0) + 1
    return groups


def attach_duplicate_group_metadata(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = build_service_duplicate_groups(services)
    for service in services:
        key = build_service_duplicate_key(service)
        group = groups.get(key) or {"key": key, "service_ids": [], "count": 1}
        service["duplicate_group"] = {
            "key": key,
            "count": int(group.get("count") or 1),
            "service_ids": list(group.get("service_ids") or []),
        }
    return services
