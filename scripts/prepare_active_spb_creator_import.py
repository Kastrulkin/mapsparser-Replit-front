#!/usr/bin/env python3
"""Validate, deduplicate and cap an active SPb creator discovery report."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CITY = "Санкт-Петербург"
ALLOWED_PLATFORMS = {"youtube", "telegram", "instagram", "threads", "tiktok", "vk"}


def normalized_url(value: Any) -> str:
    return str(value or "").strip().casefold().rstrip("/")


def existing_urls(path: Path) -> set[str]:
    return {normalized_url(line) for line in path.read_text(encoding="utf-8").splitlines() if normalized_url(line)}


def valid_entity(entity: dict[str, Any]) -> tuple[bool, str]:
    if str(entity.get("primary_city") or "") != CITY:
        return False, "city_not_confirmed"
    research = entity.get("research") or {}
    if research.get("activity_status") != "recent_publication_observed":
        return False, "activity_not_confirmed"
    people_focus = research.get("people_focus") or {}
    if people_focus.get("profile_kind") == "organization_or_media":
        return False, "organization_not_person"
    if people_focus.get("activity_level") not in {"frequent", "regular", "observed_once"}:
        return False, "posting_activity_not_classified"
    evidence = entity.get("evidence") or []
    if not evidence or not all(str(item.get("source_url") or "").startswith("https://www.youtube.com/watch?") for item in evidence):
        return False, "missing_original_publication_evidence"
    if not any("date unavailable" not in str(item.get("observed") or "").casefold() for item in evidence):
        return False, "publication_date_unavailable"
    channels = entity.get("channels") or []
    youtube_channels = [item for item in channels if item.get("platform") == "youtube"]
    if len(youtube_channels) != 1:
        return False, "youtube_identity_not_unique"
    if any(item.get("platform") not in ALLOWED_PLATFORMS for item in channels):
        return False, "unsupported_platform"
    if any(not normalized_url(item.get("canonical_url")) for item in channels):
        return False, "missing_channel_url"
    return True, ""


def write_csv(entities: list[dict[str, Any]], path: Path) -> None:
    stream = path.open("w", newline="", encoding="utf-8")
    try:
        fields = ["entity_id", "display_name", "primary_handle", "primary_city", "districts", "platforms", "subscriber_count", "evidence_url", "evidence_count"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entity in entities:
            youtube = next(item for item in entity["channels"] if item["platform"] == "youtube")
            writer.writerow({
                "entity_id": entity["entity_id"],
                "display_name": entity["display_name"],
                "primary_handle": entity["primary_handle"],
                "primary_city": entity["primary_city"],
                "districts": ", ".join(entity.get("districts") or []),
                "platforms": ", ".join(item["platform"] for item in entity["channels"]),
                "subscriber_count": youtube.get("follower_count"),
                "evidence_url": entity["evidence"][0]["source_url"],
                "evidence_count": len(entity["evidence"]),
            })
    finally:
        stream.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--existing-urls", type=Path, required=True)
    parser.add_argument("--existing-profile-count", type=int, required=True)
    parser.add_argument("--target-profile-count", type=int, default=10_000)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    arguments = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in arguments.inputs]
    known_urls = existing_urls(arguments.existing_urls)
    selected: list[dict[str, Any]] = []
    selected_urls: set[str] = set()
    rejected: dict[str, int] = {}
    required = max(0, arguments.target_profile_count - arguments.existing_profile_count)
    for entity in [item for report in reports for item in report.get("entities", [])]:
        valid, reason = valid_entity(entity)
        urls = {normalized_url(item.get("canonical_url")) for item in entity.get("channels", [])}
        if valid and urls.intersection(known_urls):
            valid, reason = False, "overlaps_production"
        if valid and urls.intersection(selected_urls):
            valid, reason = False, "cross_profile_channel_collision"
        if not valid:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        selected.append(entity)
        selected_urls.update(urls)
        if len(selected) == required:
            break
    if len(selected) < required:
        print(json.dumps({"status": "insufficient", "required": required, "selected": len(selected), "rejected": rejected}, ensure_ascii=False, sort_keys=True))
        return 2
    platform_counts: dict[str, int] = {}
    for entity in selected:
        for channel in entity["channels"]:
            platform = str(channel["platform"])
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
    output = {
        "schema_version": "1.0",
        "title": "Пакет активных авторов Санкт-Петербурга до целевого размера каталога",
        "status": "validated_public_research_ready_for_catalog_import",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(selected),
        "channel_count": sum(platform_counts.values()),
        "platform_counts": platform_counts,
        "city_counts": {CITY: len(selected)},
        "selection_stats": {
            "existing_profile_count": arguments.existing_profile_count,
            "target_profile_count": arguments.target_profile_count,
            "required_new_profiles": required,
            "selected_new_profiles": len(selected),
            "rejected_before_cutoff": rejected,
            "messages_sent": 0,
        },
        "entities": selected,
        "limitations": sorted({str(item) for report in reports for item in report.get("limitations", [])}),
    }
    arguments.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(selected, arguments.output_csv)
    print(json.dumps({"status": "ready", **output["selection_stats"], "platform_counts": platform_counts}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
