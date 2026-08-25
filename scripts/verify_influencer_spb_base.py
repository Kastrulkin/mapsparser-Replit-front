#!/usr/bin/env python3
"""Validate the 1,000+ Saint Petersburg influencer research artifact."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


BASE = Path("outputs/influencer-spb-1000-base-20260823.json")
CSV_BASE = Path("outputs/influencer-spb-1000-base-20260823.csv")


def main() -> int:
    errors: list[str] = []
    report = json.loads(BASE.read_text(encoding="utf-8"))
    entities = report["entities"]
    channels = [channel for entity in entities for channel in entity["channels"]]
    if len(entities) < 1_000:
        errors.append(f"only {len(entities)} entities; 1000 required")
    if report.get("entity_count") != len(entities):
        errors.append("entity_count does not match entities")
    if report.get("channel_count") != len(channels):
        errors.append("channel_count does not match channels")
    if any("Санкт-Петербург" not in entity.get("cities", []) for entity in entities):
        errors.append("base contains a non-SPb entity")
    entity_ids = [str(entity["entity_id"]) for entity in entities]
    if len(entity_ids) != len(set(entity_ids)):
        errors.append("duplicate entity_id")
    channel_keys = [(str(channel["platform"]), str(channel["canonical_url"]).lower().rstrip("/")) for channel in channels]
    if len(channel_keys) != len(set(channel_keys)):
        errors.append("duplicate platform/canonical_url")
    for entity in entities:
        if not entity.get("evidence"):
            errors.append(f"entity has no evidence: {entity['entity_id']}")
        if not entity.get("qualification"):
            errors.append(f"entity has no qualification: {entity['entity_id']}")
        for channel in entity["channels"]:
            if not str(channel.get("canonical_url", "")).startswith("https://"):
                errors.append(f"invalid canonical URL: {channel.get('canonical_url')}")
            if not channel.get("source_url"):
                errors.append(f"missing source URL: {channel.get('canonical_url')}")
            count = channel.get("follower_count")
            if count is not None and int(count) > 200_000:
                errors.append(f"audience cap exceeded: {channel.get('canonical_url')} ({count})")
    with CSV_BASE.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(channels):
        errors.append(f"CSV has {len(rows)} rows; JSON has {len(channels)} channels")
    stats = report.get("research_stats", {})
    if int(stats.get("final_unique_entities", 0)) != len(entities):
        errors.append("research_stats.final_unique_entities mismatch")
    result = {
        "valid": not errors,
        "entity_count": len(entities),
        "channel_count": len(channels),
        "platform_counts": report.get("platform_counts"),
        "lead_seeded_added": stats.get("lead_seeded_added"),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
