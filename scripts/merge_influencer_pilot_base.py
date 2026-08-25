#!/usr/bin/env python3
"""Merge public influencer discovery outputs into deduplicated entities."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INPUTS = [
    Path("outputs/influencer-social-base-20260823.json"),
    Path("outputs/influencer-telegram-telemetr-base-20260823.json"),
    Path("outputs/influencer-vk-base-20260823.json"),
    Path("outputs/influencer-youtube-base-20260823.json"),
]
OUTPUT_JSON = Path("outputs/influencer-pilot-unified-base-20260823.json")
OUTPUT_CSV = Path("outputs/influencer-pilot-unified-base-20260823.csv")


def normalized_handle(value: str) -> str:
    return re.sub(r"[^a-z0-9_.]", "", value.lower().lstrip("@"))


def channel_from(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": candidate["platform"],
        "canonical_url": candidate["canonical_url"],
        "username": candidate.get("username"),
        "follower_count": candidate.get("subscriber_count"),
        "audience_band": candidate.get("audience_band", "unknown"),
        "verification_status": candidate.get("verification_status"),
        "source_url": candidate.get("source_url"),
        "discovery_source_url": candidate.get("discovery_source_url"),
        "secondary_source_url": candidate.get("secondary_source_url"),
        "evidence_url": candidate.get("evidence_url"),
    }


def qualify(entity: dict[str, Any]) -> None:
    channels = entity["channels"]
    platforms = {str(channel["platform"]) for channel in channels}
    bands = {str(channel.get("audience_band", "unknown")) for channel in channels}
    locality = 4 if platforms - {"youtube"} else 3
    audience = 5 if "nano" in bands else 4 if "micro" in bands else 2
    reachability = 5 if entity["contactability"] == "advertising_contact" else 4 if entity["contactability"] == "community_messages" else 2
    evidence_quality = 5 if all(channel.get("verification_status") == "original_profile_opened" for channel in channels) else 4
    cross_platform = 5 if len(platforms) >= 3 else 4 if len(platforms) == 2 else 2
    score = round(locality * 6 + audience * 5 + reachability * 4 + evidence_quality * 3 + cross_platform * 2)
    text = " ".join([
        str(entity.get("display_name", "")), str(entity.get("description", "")),
        " ".join(str(item.get("observed", "")) for item in entity["evidence"]),
    ]).lower()
    cities = set(entity["cities"])
    business_fit: list[str] = []
    if "Батуми" in cities and re.search(r"(дет|школ|образов|семь|родител|афиш|kids|school|family|education|events)", text):
        business_fit.append("intellectum")
    if "Краснодар" in cities and re.search(r"(афиш|событ|культур|концерт|музык|куда сходить)", text):
        business_fit.append("katok")
    if "Санкт-Петербург" in cities and re.search(r"(дет|мам|семь|родител|красот|стил)", text):
        business_fit.append("veselaya_rascheska")
    if "Санкт-Петербург" in cities and re.search(r"(красот|салон|волос|бьюти|beauty|стил|здоров)", text):
        business_fit.append("organika")
    if re.search(r"(путешеств|туризм|трансфер|транспорт|travel|trip|expat|vlog)", text):
        business_fit.append("riderra")
    entity["qualification"] = {
        "score": score,
        "stage": "worth_checking" if score >= 65 else "needs_manual_review",
        "score_breakdown": {
            "locality_evidence": locality,
            "audience_fit": audience,
            "public_reachability": reachability,
            "evidence_quality": evidence_quality,
            "cross_platform_depth": cross_platform,
        },
        "business_fit_candidates": sorted(set(business_fit)),
        "limitations": ["Тематический fit определён по публичному описанию/контенту и является предварительной гипотезой."],
    }


def merge() -> list[dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}
    channel_keys: set[tuple[str, str]] = set()
    for path in INPUTS:
        report = json.loads(path.read_text(encoding="utf-8"))
        for candidate in report["candidates"]:
            handle = normalized_handle(str(candidate.get("primary_handle") or candidate.get("username") or candidate["candidate_id"]))
            entity_key = handle or str(candidate["candidate_id"])
            entity = entities.get(entity_key)
            cities = [str(candidate["city"])]
            if entity is None:
                entity_id = hashlib.sha256(f"influencer:{entity_key}".encode()).hexdigest()[:20]
                entity = {
                    "entity_id": entity_id,
                    "display_name": candidate["display_name"],
                    "profile_type": candidate.get("profile_type", "author_or_channel"),
                    "primary_handle": candidate.get("primary_handle") or candidate.get("username"),
                    "cities": cities,
                    "description": candidate.get("description", ""),
                    "contactability": candidate.get("contactability", "manual_only"),
                    "channels": [],
                    "evidence": [],
                    "limitations": [],
                }
                entities[entity_key] = entity
            else:
                entity["cities"] = sorted(set(entity["cities"] + cities))
                if entity["contactability"] == "manual_only" and candidate.get("contactability") not in {None, "manual_only"}:
                    entity["contactability"] = candidate["contactability"]
            source_channels = candidate.get("channels")
            if source_channels:
                channels = []
                for source_channel in source_channels:
                    channels.append({
                        "platform": source_channel["platform"],
                        "canonical_url": source_channel["canonical_url"],
                        "username": candidate.get("primary_handle"),
                        "follower_count": source_channel.get("follower_count"),
                        "audience_band": candidate.get("audience_band", "unknown"),
                        "verification_status": source_channel.get("verification_status"),
                        "source_url": source_channel.get("source_url"),
                        "discovery_source_url": (candidate.get("discovery_sources") or [None])[0],
                        "secondary_source_url": None,
                        "evidence_url": None,
                    })
            else:
                channels = [channel_from(candidate)]
            for channel in channels:
                key = (str(channel["platform"]), str(channel["canonical_url"]).rstrip("/").lower())
                if key not in channel_keys:
                    entity["channels"].append(channel)
                    channel_keys.add(key)
            evidence_item = {
                "observed": candidate.get("evidence_summary") or "Оригинальный публичный профиль открыт.",
                "source_url": candidate.get("evidence_url") or candidate.get("source_url") or (candidate.get("discovery_sources") or [None])[0],
                "source_type": "public_profile_or_content",
                "researched_at": candidate.get("researched_at"),
            }
            entity["evidence"].append(evidence_item)
            entity["limitations"] = sorted(set(entity["limitations"] + candidate.get("limitations", [])))
    for entity in entities.values():
        qualify(entity)
    return sorted(entities.values(), key=lambda item: (item["cities"][0], str(item["display_name"]).lower()))


def write(entities: list[dict[str, Any]]) -> None:
    platform_counts: dict[str, int] = {}
    city_counts: dict[str, int] = {}
    channel_count = 0
    for entity in entities:
        for city in entity["cities"]:
            city_counts[city] = city_counts.get(city, 0) + 1
        for channel in entity["channels"]:
            channel_count += 1
            platform = str(channel["platform"])
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
    report = {
        "schema_version": "1.0",
        "title": "Предварительная мультиканальная база локальных инфлюенсеров LocalOS",
        "status": "public_research_only_needs_manual_shortlist",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(entities),
        "channel_count": channel_count,
        "platform_counts": platform_counts,
        "city_counts": city_counts,
        "entities": entities,
        "coverage_notes": {
            "telegram": "Открыты оригинальные t.me-профили; TGStat проверен, но массовый поиск без входа ограничен; для discovery также использован Telemetr.",
            "maps": "Яндекс Карты и 2ГИС пройдены как review-only сегмент; авторы отзывов не добавляются в аутрич без публичного профессионального контакта.",
            "sites_search": "Городские медиа и каталоги использованы как discovery/evidence, но не дублируются как отдельные авторы при ссылке на тот же социальный профиль.",
        },
        "limitations": [
            "База предварительная: перед любой кампанией нужны ручной fit/brand-safety review и запрос географии аудитории.",
            "Публичный профиль не означает согласие на рекламу, бартер или контакт.",
            "Никаких сообщений не отправлялось, production LocalOS не изменялся.",
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["entity_id", "display_name", "cities", "profile_type", "primary_handle", "contactability", "score", "stage", "business_fit_candidates", "platform", "canonical_url", "username", "follower_count", "audience_band", "verification_status", "source_url", "discovery_source_url", "evidence_url"]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for entity in entities:
            for channel in entity["channels"]:
                writer.writerow({
                    "entity_id": entity["entity_id"], "display_name": entity["display_name"], "cities": ", ".join(entity["cities"]),
                    "profile_type": entity["profile_type"], "primary_handle": entity["primary_handle"], "contactability": entity["contactability"],
                    "score": entity["qualification"]["score"], "stage": entity["qualification"]["stage"], "business_fit_candidates": ", ".join(entity["qualification"]["business_fit_candidates"]),
                    "platform": channel["platform"], "canonical_url": channel["canonical_url"], "username": channel.get("username"),
                    "follower_count": channel.get("follower_count"), "audience_band": channel.get("audience_band"), "verification_status": channel.get("verification_status"),
                    "source_url": channel.get("source_url"), "discovery_source_url": channel.get("discovery_source_url"), "evidence_url": channel.get("evidence_url"),
                })


if __name__ == "__main__":
    result = merge()
    write(result)
    print(json.dumps({"entity_count": len(result), "outputs": [str(OUTPUT_JSON), str(OUTPUT_CSV)]}, ensure_ascii=False))
