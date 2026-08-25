#!/usr/bin/env python3
"""Verify the 500+ influencer pilot base and mention-audit coverage."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


BASE = Path("outputs/influencer-pilot-unified-base-20260823.json")
CSV_BASE = Path("outputs/influencer-pilot-unified-base-20260823.csv")
AUDIT = Path("docs/INFLUENCER_PILOT_MENTION_AUDIT_2026-08-23.md")
REQUIRED_PLATFORMS = {"telegram", "vk", "instagram", "tiktok", "youtube", "threads"}
REQUIRED_CITIES = {"Санкт-Петербург", "Краснодар", "Батуми"}
REQUIRED_BUSINESSES = {"Intellectum", "КАТОК", "Riderra", "Весёлая расчёска", "Органика"}
REQUIRED_AUDIT_COVERAGE = {"Telegram", "VK", "Instagram / Reels", "TikTok", "YouTube / Shorts", "Яндекс Карты / 2ГИС", "Сайты и поиск", "Threads"}


def main() -> int:
    errors: list[str] = []
    report = json.loads(BASE.read_text(encoding="utf-8"))
    entities = report["entities"]
    channels = [channel for entity in entities for channel in entity["channels"]]
    if report["entity_count"] != len(entities):
        errors.append("entity_count does not match entities")
    if len(entities) < 500:
        errors.append(f"only {len(entities)} entities; 500 required")
    if report["channel_count"] != len(channels):
        errors.append("channel_count does not match channels")
    platforms = {str(channel["platform"]) for channel in channels}
    if not REQUIRED_PLATFORMS.issubset(platforms):
        errors.append(f"missing platforms: {sorted(REQUIRED_PLATFORMS - platforms)}")
    cities = {city for entity in entities for city in entity["cities"]}
    if not REQUIRED_CITIES.issubset(cities):
        errors.append(f"missing cities: {sorted(REQUIRED_CITIES - cities)}")
    keys = [(str(channel["platform"]), str(channel["canonical_url"]).rstrip("/").lower()) for channel in channels]
    if len(keys) != len(set(keys)):
        errors.append("duplicate platform/canonical_url channels")
    for entity in entities:
        if not entity["evidence"]:
            errors.append(f"entity {entity['entity_id']} has no evidence")
        for channel in entity["channels"]:
            if not str(channel.get("canonical_url", "")).startswith("https://"):
                errors.append(f"channel has invalid canonical URL: {channel}")
            if not channel.get("source_url"):
                errors.append(f"channel has no source URL: {channel.get('canonical_url')}")
            count = channel.get("follower_count")
            if count is not None and int(count) > 200_000:
                errors.append(f"channel over pilot cap: {channel.get('canonical_url')} ({count})")
    with CSV_BASE.open(newline="", encoding="utf-8-sig") as stream:
        csv_rows = list(csv.DictReader(stream))
    if len(csv_rows) != len(channels):
        errors.append(f"CSV has {len(csv_rows)} rows but JSON has {len(channels)} channels")
    audit = AUDIT.read_text(encoding="utf-8")
    for business in REQUIRED_BUSINESSES:
        if business.lower() not in audit.lower():
            errors.append(f"business missing from audit: {business}")
    for coverage in REQUIRED_AUDIT_COVERAGE:
        if coverage.lower() not in audit.lower():
            errors.append(f"coverage missing from audit: {coverage}")
    result = {
        "valid": not errors,
        "entity_count": len(entities),
        "channel_count": len(channels),
        "platform_counts": report["platform_counts"],
        "city_counts": report["city_counts"],
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
