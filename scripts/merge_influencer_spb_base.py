#!/usr/bin/env python3
"""Merge the existing multi-platform base with the SPb lead-seeded expansion."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from merge_influencer_pilot_base import qualify


CITY = "Санкт-Петербург"
EXISTING = Path("outputs/influencer-pilot-unified-base-20260823.json")
EXPANSION = Path("outputs/influencer-spb-youtube-expansion-20260823.json")
OUTPUT_JSON = Path("outputs/influencer-spb-1000-base-20260823.json")
OUTPUT_CSV = Path("outputs/influencer-spb-1000-base-20260823.csv")


def canonical(value: str) -> str:
    return value.lower().rstrip("/")


def merge() -> tuple[list[dict[str, Any]], dict[str, int]]:
    existing_report = json.loads(EXISTING.read_text(encoding="utf-8"))
    expansion_report = json.loads(EXPANSION.read_text(encoding="utf-8"))
    entities = [entity for entity in existing_report["entities"] if CITY in entity.get("cities", [])]
    url_index: dict[str, dict[str, Any]] = {}
    for entity in entities:
        entity.setdefault("research", {})
        for channel in entity.get("channels", []):
            url_index[canonical(str(channel["canonical_url"]))] = entity

    added = 0
    overlapped = 0
    lead_seeded_added = 0
    for candidate in expansion_report["candidates"]:
        url = canonical(str(candidate["canonical_url"]))
        queries = candidate.get("directory_queries", [])
        if url in url_index:
            entity = url_index[url]
            entity["research"]["spb_expansion_queries"] = sorted(set(entity["research"].get("spb_expansion_queries", []) + queries))
            entity["research"]["lead_seeded"] = bool(entity["research"].get("lead_seeded") or candidate.get("lead_seeded"))
            overlapped += 1
            continue

        entity = {
            "entity_id": hashlib.sha256(f"spb-influencer:{url}".encode()).hexdigest()[:20],
            "display_name": candidate["display_name"],
            "profile_type": candidate.get("profile_type", "author_or_channel"),
            "primary_handle": candidate.get("username"),
            "cities": [CITY],
            "description": "",
            "contactability": candidate.get("contactability", "manual_only"),
            "channels": [{
                "platform": "youtube",
                "canonical_url": candidate["canonical_url"],
                "username": candidate.get("username"),
                "follower_count": candidate.get("subscriber_count"),
                "audience_band": candidate.get("audience_band", "unknown"),
                "verification_status": candidate.get("verification_status"),
                "source_url": candidate.get("source_url"),
                "discovery_source_url": candidate.get("discovery_source_url"),
                "secondary_source_url": None,
                "evidence_url": candidate.get("evidence_url"),
            }],
            "evidence": [{
                "observed": candidate.get("evidence_summary"),
                "source_url": candidate.get("evidence_url"),
                "source_type": "public_video_and_original_profile",
                "researched_at": candidate.get("researched_at"),
            }],
            "limitations": candidate.get("limitations", []),
            "research": {
                "lead_seeded": bool(candidate.get("lead_seeded")),
                "spb_expansion_queries": queries,
            },
        }
        qualify(entity)
        entities.append(entity)
        url_index[url] = entity
        added += 1
        if candidate.get("lead_seeded"):
            lead_seeded_added += 1

    entities.sort(key=lambda item: str(item["display_name"]).lower())
    return entities, {
        "existing_spb_entities": sum(1 for entity in existing_report["entities"] if CITY in entity.get("cities", [])),
        "expansion_candidates": len(expansion_report["candidates"]),
        "overlaps": overlapped,
        "added_after_deduplication": added,
        "lead_seeded_added": lead_seeded_added,
        "final_unique_entities": len(entities),
    }


def write(entities: list[dict[str, Any]], stats: dict[str, int]) -> None:
    platform_counts: dict[str, int] = {}
    channel_count = 0
    for entity in entities:
        for channel in entity["channels"]:
            platform = str(channel["platform"])
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
            channel_count += 1
    report = {
        "schema_version": "1.0",
        "title": "База локальных инфлюенсеров Санкт-Петербурга",
        "status": "public_research_only_needs_manual_shortlist",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(entities),
        "channel_count": channel_count,
        "city_counts": {CITY: len(entities)},
        "platform_counts": platform_counts,
        "research_stats": stats,
        "entities": entities,
        "limitations": [
            "Локальность части YouTube-авторов подтверждается конкретным видео о Петербурге, но не гарантирует место жительства или долю городской аудитории.",
            "Перед контактом обязательны ручной fit/brand-safety review и проверка актуальной активности.",
            "Публичный профиль не означает согласия на рекламу или бартер; сообщений не отправлялось.",
            "Production LocalOS не изменялся: база лидов использована только как read-only источник поисковых семян.",
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["entity_id", "display_name", "profile_type", "primary_handle", "contactability", "score", "stage", "business_fit_candidates", "lead_seeded", "platform", "canonical_url", "username", "follower_count", "audience_band", "verification_status", "source_url", "discovery_source_url", "evidence_url"]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for entity in entities:
            for channel in entity["channels"]:
                writer.writerow({
                    "entity_id": entity["entity_id"], "display_name": entity["display_name"],
                    "profile_type": entity["profile_type"], "primary_handle": entity.get("primary_handle"),
                    "contactability": entity["contactability"], "score": entity["qualification"]["score"],
                    "stage": entity["qualification"]["stage"],
                    "business_fit_candidates": ", ".join(entity["qualification"]["business_fit_candidates"]),
                    "lead_seeded": entity.get("research", {}).get("lead_seeded", False),
                    "platform": channel["platform"], "canonical_url": channel["canonical_url"],
                    "username": channel.get("username"), "follower_count": channel.get("follower_count"),
                    "audience_band": channel.get("audience_band"), "verification_status": channel.get("verification_status"),
                    "source_url": channel.get("source_url"), "discovery_source_url": channel.get("discovery_source_url"),
                    "evidence_url": channel.get("evidence_url"),
                })


if __name__ == "__main__":
    result, result_stats = merge()
    write(result, result_stats)
    print(json.dumps(result_stats, ensure_ascii=False))
