#!/usr/bin/env python3
"""Build a reviewed SPb-only import wave from current public discovery outputs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from merge_influencer_pilot_base import qualify


CITY = "\u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433"
SOCIAL = Path("outputs/influencer-social-spb-wave2-20260825.json")
TELEMETR = Path("outputs/influencer-telegram-spb-wave2-20260825.json")
LOCAL_CATALOGS = Path("outputs/influencer-telegram-telegrator-spb-20260825.json")
OUTPUT = Path("outputs/influencer-spb-wave2-reviewed-20260825.json")
EXCLUDED_HANDLES = {
    "chaekshop",
    "msimonyan_literature",
    "nlobooks",
    "optica_prisma",
    "vka_spb",
}


def normalized_handle(value: Any) -> str:
    return re.sub(r"[^a-z0-9_.]", "", str(value or "").lower().lstrip("@"))


def entity_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    handle = candidate.get("primary_handle") or candidate.get("username")
    source_channels = candidate.get("channels")
    if source_channels:
        channels = [{
            "platform": channel["platform"],
            "canonical_url": channel["canonical_url"],
            "username": handle,
            "follower_count": channel.get("follower_count"),
            "audience_band": candidate.get("audience_band", "unknown"),
            "verification_status": channel.get("verification_status"),
            "source_url": channel.get("source_url"),
            "discovery_source_url": (candidate.get("discovery_sources") or [None])[0],
            "researched_at": candidate.get("researched_at"),
        } for channel in source_channels]
    else:
        channels = [{
            "platform": candidate["platform"],
            "canonical_url": candidate["canonical_url"],
            "username": candidate.get("username"),
            "follower_count": candidate.get("subscriber_count"),
            "audience_band": candidate.get("audience_band", "unknown"),
            "verification_status": candidate.get("verification_status"),
            "source_url": candidate.get("source_url"),
            "discovery_source_url": candidate.get("discovery_source_url"),
            "secondary_source_url": candidate.get("secondary_source_url"),
            "researched_at": candidate.get("researched_at"),
        }]
    entity_key = normalized_handle(handle) or str(candidate["candidate_id"])
    entity = {
        "entity_id": hashlib.sha256(f"spb-wave2:{entity_key}".encode()).hexdigest()[:20],
        "display_name": candidate["display_name"],
        "profile_type": candidate.get("profile_type", "channel"),
        "primary_handle": handle,
        "cities": [CITY],
        "districts": candidate.get("districts", []),
        "description": candidate.get("description", ""),
        "topics": candidate.get("topics", []),
        "contactability": candidate.get("contactability", "manual_only"),
        "preferred_contact": (candidate.get("public_contacts") or [None])[0],
        "channels": channels,
        "evidence": [{
            "observed": candidate.get("evidence_summary") or "\u041e\u0440\u0438\u0433\u0438\u043d\u0430\u043b\u044c\u043d\u044b\u0439 \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u044b\u0439 \u043f\u0440\u043e\u0444\u0438\u043b\u044c \u0438\u043b\u0438 \u0430\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u044b\u0439 \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u044b\u0439 \u043a\u0430\u0442\u0430\u043b\u043e\u0433 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d.",
            "source_url": candidate.get("discovery_source_url") or candidate.get("source_url") or (candidate.get("discovery_sources") or [None])[0],
            "source_type": "public_profile_or_catalog",
            "researched_at": candidate.get("researched_at"),
            "confidence": 0.85,
        }],
        "research": {
            "researched_at": candidate.get("researched_at"),
            "district_status": candidate.get("district_status", "ask_creator"),
            "outreach_status": "not_contacted",
        },
        "limitations": candidate.get("limitations", []),
    }
    qualify(entity)
    return entity


def merge_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    urls: set[tuple[str, str]] = set()
    for entity in entities:
        key = normalized_handle(entity.get("primary_handle")) or str(entity["entity_id"])
        target = result.get(key)
        if target is None:
            target = dict(entity)
            target["channels"] = []
            result[key] = target
        for channel in entity["channels"]:
            url_key = (str(channel["platform"]), str(channel["canonical_url"]).lower().rstrip("/"))
            if url_key in urls:
                continue
            urls.add(url_key)
            target["channels"].append(channel)
        target["districts"] = sorted(set(target.get("districts", []) + entity.get("districts", [])))
        target["topics"] = sorted(set(target.get("topics", []) + entity.get("topics", [])))
        target["evidence"] = target.get("evidence", []) + entity.get("evidence", [])
        if not target.get("preferred_contact") and entity.get("preferred_contact"):
            target["preferred_contact"] = entity["preferred_contact"]
        if target.get("contactability") == "manual_only" and entity.get("contactability") != "manual_only":
            target["contactability"] = entity["contactability"]
        qualify(target)
    return sorted(result.values(), key=lambda item: str(item["display_name"]).lower())


def main() -> None:
    entities: list[dict[str, Any]] = []
    for path in (SOCIAL, TELEMETR):
        report = json.loads(path.read_text(encoding="utf-8"))
        for candidate in report["candidates"]:
            if candidate.get("city") != CITY:
                continue
            handle = normalized_handle(candidate.get("primary_handle") or candidate.get("username"))
            if handle in EXCLUDED_HANDLES:
                continue
            entities.append(entity_from_candidate(candidate))
    local_report = json.loads(LOCAL_CATALOGS.read_text(encoding="utf-8"))
    for entity in local_report["entities"]:
        if normalized_handle(entity.get("primary_handle")) in EXCLUDED_HANDLES:
            continue
        qualify(entity)
        entities.append(entity)
    merged = merge_entities(entities)
    platform_counts: dict[str, int] = {}
    for entity in merged:
        for channel in entity["channels"]:
            platform = str(channel["platform"])
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
    payload = {
        "schema_version": "1.0",
        "title": "\u0412\u0442\u043e\u0440\u0430\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043d\u0430\u044f \u0432\u043e\u043b\u043d\u0430 \u0438\u043d\u0444\u043b\u044e\u0435\u043d\u0441\u0435\u0440\u043e\u0432 \u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433\u0430",
        "status": "reviewed_public_research",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(merged),
        "channel_count": sum(platform_counts.values()),
        "platform_counts": platform_counts,
        "city_counts": {CITY: len(merged)},
        "entities": merged,
        "limitations": [
            "\u041d\u0438\u043a\u0430\u043a\u0438\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u043d\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u043b\u0438\u0441\u044c.",
            "\u0414\u043b\u044f \u043f\u0440\u043e\u0444\u0438\u043b\u0435\u0439 \u0431\u0435\u0437 \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u043e\u0433\u043e \u0440\u0430\u0439\u043e\u043d\u0430 district_status=ask_creator; \u0440\u0430\u0439\u043e\u043d \u043d\u0435 \u0432\u044b\u0434\u0443\u043c\u044b\u0432\u0430\u0435\u0442\u0441\u044f.",
            "\u041f\u0435\u0440\u0435\u0434 \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u0435\u0439 \u043d\u0443\u0436\u043d\u044b \u0440\u0443\u0447\u043d\u043e\u0439 brand-safety review \u0438 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435 \u0434\u043e\u043b\u0438 \u0430\u0443\u0434\u0438\u0442\u043e\u0440\u0438\u0438 \u0432 \u043d\u0443\u0436\u043d\u043e\u043c \u0440\u0430\u0439\u043e\u043d\u0435.",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"entity_count": len(merged), "channel_count": payload["channel_count"], "platform_counts": platform_counts, "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
