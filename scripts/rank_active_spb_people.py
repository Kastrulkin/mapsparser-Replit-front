#!/usr/bin/env python3
"""Rank SPb creator research toward active personal authors."""

from __future__ import annotations

import argparse
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from discover_active_spb_creators import fetch, initial_data, is_recent, text_value, walk


ORGANIZATION_MARKERS = (
    "медиа", "новости", "телеканал", "радио", "журнал", "издание", "official", "официальный", "компания", "агентство",
    "магазин", "салон", "клиника", "центр", "школа", "университет", "музей", "театр", "ресторан", "отель", "студия", "фитнес клуб",
    "застройщик", "жилой комплекс", "администрация", "комитет", "федерация", "ассоциация", "команда", "сеть ", "торговый центр",
)
PERSON_MARKERS = ("я ", "мой блог", "моя жизнь", "меня зовут", "личный блог", "мама", "папа", "автор", "фотог", "гид", "travel blogger", "lifestyle")
PROFESSIONAL_MARKERS = ("блогер", "influencer", "реклама", "рекламе", "сотрудничество", "collab", "ugc", "прайс")


def normalized_url(value: Any) -> str:
    return str(value or "").strip().casefold().rstrip("/")


def visible_recent_uploads(entity: dict[str, Any]) -> dict[str, Any]:
    youtube = next((item for item in entity.get("channels", []) if item.get("platform") == "youtube"), None)
    if not youtube:
        return {"visible_uploads": 0, "recent_visible_uploads": 0, "activity_checked_at": None}
    profile_url = str(youtube["canonical_url"]).rstrip("/")
    document = fetch(f"{profile_url}/videos?view=0&sort=dd&flow=grid&hl=ru")
    data = initial_data(document)
    labels: list[str] = []
    video_ids: set[str] = set()
    for node in walk(data):
        renderer = node.get("videoRenderer") or node.get("gridVideoRenderer")
        lockup = (node.get("richItemRenderer") or {}).get("content", {}).get("lockupViewModel")
        if isinstance(renderer, dict):
            video_id = str(renderer.get("videoId") or "")
            published_label = text_value(renderer.get("publishedTimeText"))
        elif isinstance(lockup, dict) and lockup.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO":
            video_id = str(lockup.get("contentId") or "")
            published_label = next((
                str(value.get("content") or "")
                for value in walk(lockup)
                if isinstance(value.get("content"), str) and any(marker in str(value["content"]).casefold() for marker in ("назад", "ago", "эфир"))
            ), "")
        else:
            continue
        if not video_id or video_id in video_ids:
            continue
        video_ids.add(video_id)
        labels.append(published_label)
    known_labels = [label for label in labels if label.strip()]
    recent = sum(is_recent(label) for label in known_labels)
    observed_local = int((entity.get("research") or {}).get("recent_publication_evidence_count") or 0)
    return {
        "visible_uploads": len(video_ids),
        "recent_visible_uploads": max(recent, observed_local),
        "activity_checked_at": datetime.now(timezone.utc).isoformat(),
    }


def person_profile(entity: dict[str, Any], activity: dict[str, Any]) -> dict[str, Any]:
    name = str(entity.get("display_name") or "").strip()
    description = str(entity.get("description") or "").strip()
    combined = f"{name} {description}".casefold()
    words = re.findall(r"[A-Za-zА-Яа-яЁё-]+", name)
    organization_hits = sorted({marker for marker in ORGANIZATION_MARKERS if marker in combined})
    person_hits = sorted({marker for marker in PERSON_MARKERS if marker in combined})
    professional_hits = sorted({marker for marker in PROFESSIONAL_MARKERS if marker in combined})
    score = 0
    if 2 <= len(words) <= 4 and not organization_hits:
        score += 3
    if person_hits:
        score += 2
    if any(item.get("platform") in {"instagram", "threads", "tiktok", "vk", "telegram"} for item in entity.get("channels", [])):
        score += 1
    if name and sum(character.isupper() for character in name) / max(1, sum(character.isalpha() for character in name)) > 0.7:
        score -= 1
    score -= min(5, len(organization_hits) * 2)
    if score >= 2 and professional_hits:
        kind = "professional_creator"
    elif score >= 2:
        kind = "personal_author"
    elif score <= -2:
        kind = "organization_or_media"
    else:
        kind = "uncertain_person_or_channel"
    recent = int(activity["recent_visible_uploads"])
    level = "frequent" if recent >= 5 else "regular" if recent >= 2 else "observed_once"
    return {
        "profile_kind": kind,
        "person_likelihood_score": score,
        "person_markers": person_hits,
        "professional_markers": professional_hits,
        "organization_markers": organization_hits,
        "activity_level": level,
        **activity,
    }


def rank_key(entity: dict[str, Any]) -> tuple[int, int, int, int, int, str]:
    focus = (entity.get("research") or {}).get("people_focus") or {}
    kind_rank = {
        "personal_author": 0,
        "uncertain_person_or_channel": 1,
        "professional_creator": 2,
        "organization_or_media": 3,
    }.get(str(focus.get("profile_kind")), 4)
    activity_rank = {"frequent": 0, "regular": 1, "observed_once": 2}.get(str(focus.get("activity_level")), 3)
    return (
        1 if str(focus.get("profile_kind")) == "organization_or_media" else 0,
        activity_rank,
        kind_rank,
        -int(focus.get("recent_visible_uploads") or 0),
        -int(focus.get("person_likelihood_score") or 0),
        str(entity.get("display_name") or "").casefold(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=32)
    arguments = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in arguments.inputs]
    entities_by_youtube: dict[str, dict[str, Any]] = {}
    for report in reports:
        for entity in report.get("entities", []):
            youtube = next((item for item in entity.get("channels", []) if item.get("platform") == "youtube"), None)
            if not youtube:
                continue
            key = normalized_url(youtube.get("canonical_url"))
            existing = entities_by_youtube.get(key)
            if existing is None or len(entity.get("evidence", [])) > len(existing.get("evidence", [])):
                entities_by_youtube[key] = entity
    entities = list(entities_by_youtube.values())
    activity_by_id: dict[str, dict[str, Any]] = {}
    executor = ThreadPoolExecutor(max_workers=max(1, min(arguments.workers, 48)))
    try:
        futures = {executor.submit(visible_recent_uploads, entity): str(entity["entity_id"]) for entity in entities}
        for completed, future in enumerate(as_completed(futures), start=1):
            activity_by_id[futures[future]] = future.result()
            if completed % 250 == 0:
                print(json.dumps({"phase": "people_activity_ranking", "completed": completed, "total": len(futures)}, ensure_ascii=False), flush=True)
    finally:
        executor.shutdown(wait=True)
    for entity in entities:
        research = dict(entity.get("research") or {})
        research["people_focus"] = person_profile(entity, activity_by_id[str(entity["entity_id"])])
        entity["research"] = research
    entities.sort(key=rank_key)
    kind_counts: dict[str, int] = {}
    activity_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    for entity in entities:
        focus = entity["research"]["people_focus"]
        kind = str(focus["profile_kind"])
        level = str(focus["activity_level"])
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        activity_counts[level] = activity_counts.get(level, 0) + 1
        for channel in entity["channels"]:
            platform = str(channel["platform"])
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
    output = {
        "schema_version": "1.0",
        "title": "Активные авторы Петербурга: фокус на людях, которые регулярно постят",
        "status": "ranked_public_research_people_first_no_messages_sent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(entities),
        "channel_count": sum(platform_counts.values()),
        "platform_counts": platform_counts,
        "people_focus_counts": kind_counts,
        "activity_counts": activity_counts,
        "entities": entities,
        "limitations": sorted({str(item) for report in reports for item in report.get("limitations", [])}),
    }
    arguments.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    stream = arguments.output_csv.open("w", newline="", encoding="utf-8")
    try:
        fields = ["entity_id", "display_name", "profile_kind", "activity_level", "recent_visible_uploads", "person_likelihood_score", "platforms", "primary_city", "districts", "evidence_url"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entity in entities:
            focus = entity["research"]["people_focus"]
            writer.writerow({
                "entity_id": entity["entity_id"],
                "display_name": entity["display_name"],
                "profile_kind": focus["profile_kind"],
                "activity_level": focus["activity_level"],
                "recent_visible_uploads": focus["recent_visible_uploads"],
                "person_likelihood_score": focus["person_likelihood_score"],
                "platforms": ", ".join(item["platform"] for item in entity["channels"]),
                "primary_city": entity["primary_city"],
                "districts": ", ".join(entity.get("districts") or []),
                "evidence_url": entity["evidence"][0]["source_url"],
            })
    finally:
        stream.close()
    print(json.dumps({"entity_count": len(entities), "people_focus_counts": kind_counts, "activity_counts": activity_counts, "platform_counts": platform_counts}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
