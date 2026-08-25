#!/usr/bin/env python3
"""Discover public YouTube creators with observable coverage of pilot cities."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127 Safari/537.36"
QUERIES = {
    "Санкт-Петербург": (
        "Санкт-Петербург блог", "Питер куда сходить", "СПб мама блог", "СПб бьюти блогер",
        "Санкт-Петербург shorts", "Петербург с детьми", "локальный блогер СПб",
        "СПб рестораны обзор", "СПб красота салон блог", "Питер детские места обзор", "Петербург история авторский канал",
        "СПб локальный гид", "Питер lifestyle vlog", "СПб афиша видео", "Петербург районный блог",
        "Питер обзор мест", "СПб культура события", "Saint Petersburg local vlog", "Saint Petersburg family vlog",
        "Питер прогулки блог", "СПб кафе обзор", "Санкт-Петербург семейный канал", "Питер достопримечательности vlog", "СПб детские кружки обзор",
    ),
    "Краснодар": (
        "Краснодар блог", "Краснодар куда сходить", "Краснодар мама блог", "Краснодар бьюти блогер",
        "Краснодар shorts", "Краснодар с детьми", "локальный блогер Краснодар",
        "Краснодар рестораны обзор", "Краснодар салоны красоты блог", "Краснодар детские места", "Краснодар культура афиша",
        "Краснодар локальный гид", "Краснодар lifestyle vlog", "Краснодар афиша видео", "Краснодар обзор мест",
        "Краснодар семейный блог", "Кубань путешествия блог", "Krasnodar local vlog", "Krasnodar family vlog",
        "Краснодар прогулка vlog", "Краснодар кафе обзор", "Краснодар семейный канал", "Краснодар достопримечательности vlog", "Краснодар детские развлечения",
    ),
    "Батуми": (
        "Батуми блог", "Батуми куда сходить", "Батуми с детьми", "Batumi vlog",
        "Batumi shorts", "Батуми жизнь блог", "локальный блогер Батуми",
        "Batumi restaurants vlog", "Batumi family vlog", "Batumi expat vlog", "Batumi school review", "Batumi beauty vlog", "Batumi events vlog",
        "Batumi local guide", "Batumi places review", "Батуми русский блогер", "Батуми детские места", "Batumi travel shorts", "Batumi food review",
        "Батуми прогулка vlog", "Batumi cafe review", "Batumi kids activities", "Batumi lifestyle blogger", "Batumi Russian expat",
    ),
}
CITY_MARKERS = {
    "Санкт-Петербург": ("санкт-петербург", "петербург", "питер", "спб"),
    "Краснодар": ("краснодар",),
    "Батуми": ("батуми", "batumi"),
}


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"})
    with urlopen(request, timeout=12) as response:
        return response.read().decode("utf-8", errors="replace")


def walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def text_value(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    if value.get("simpleText"):
        return str(value["simpleText"])
    return "".join(str(run.get("text", "")) for run in value.get("runs", []))


def initial_data(document: str) -> dict[str, Any]:
    marker = "var ytInitialData = "
    start = document.find(marker)
    if start < 0:
        marker = "ytInitialData = "
        start = document.find(marker)
    if start < 0:
        return {}
    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(document[start + len(marker):])
    return data


def discover_query(city: str, query: str) -> list[dict[str, Any]]:
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&hl=ru"
    data = initial_data(fetch(search_url))
    found: list[dict[str, Any]] = []
    for node in walk(data):
        renderer = node.get("videoRenderer")
        if not isinstance(renderer, dict):
            continue
        title = text_value(renderer.get("title"))
        description = " ".join(text_value(item.get("snippetText")) for item in renderer.get("detailedMetadataSnippets", []))
        evidence_text = f"{title} {description}".lower()
        if not any(marker in evidence_text for marker in CITY_MARKERS[city]):
            continue
        owner_runs = (renderer.get("ownerText") or {}).get("runs", [])
        if not owner_runs:
            continue
        endpoint = owner_runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {})
        channel_id = endpoint.get("browseId")
        canonical_path = endpoint.get("canonicalBaseUrl")
        if not channel_id:
            continue
        video_id = renderer.get("videoId")
        found.append({
            "city": city,
            "query": query,
            "search_url": search_url,
            "channel_id": channel_id,
            "canonical_path": canonical_path,
            "channel_title": str(owner_runs[0].get("text", "")),
            "evidence_title": title,
            "evidence_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else search_url,
        })
    return found


def verify(item: dict[str, Any]) -> dict[str, Any] | None:
    canonical_path = item.get("canonical_path")
    profile_url = f"https://www.youtube.com{canonical_path}" if canonical_path else f"https://www.youtube.com/channel/{item['channel_id']}"
    document = fetch(f"{profile_url}/about?hl=en")
    title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', document, flags=re.IGNORECASE)
    if not title_match:
        return None
    display_name = html.unescape(title_match.group(1)).strip()
    subscriber_match = re.search(r'"subscriberCountText":"([^"]+)"', document, flags=re.IGNORECASE)
    subscriber_count: int | None = None
    if subscriber_match:
        subscriber_label = html.unescape(subscriber_match.group(1)).replace("\u00a0", " ")
        number_match = re.search(r"([\d.,]+)\s*([KMB]|тыс|млн|млрд)?", subscriber_label, flags=re.IGNORECASE)
        if number_match:
            raw_number = number_match.group(1)
            if "," in raw_number and "." not in raw_number:
                raw_number = raw_number.replace(",", ".")
            else:
                raw_number = raw_number.replace(",", "")
            number = float(raw_number)
            suffix = (number_match.group(2) or "").lower()
        else:
            number = 0
            suffix = ""
        if suffix in {"k", "тыс"}:
            number *= 1_000
        elif suffix in {"m", "млн"}:
            number *= 1_000_000
        elif suffix in {"b", "млрд"}:
            number *= 1_000_000_000
        subscriber_count = round(number) if number else None
    if subscriber_count is not None and subscriber_count > 200_000:
        return None
    handle = str(canonical_path).removeprefix("/@") if str(canonical_path).startswith("/@") else str(item["channel_id"])
    candidate_id = hashlib.sha256(f"youtube:{item['channel_id']}".encode()).hexdigest()[:20]
    return {
        "candidate_id": candidate_id,
        "display_name": display_name,
        "profile_type": "author_or_channel",
        "platform": "youtube",
        "canonical_url": profile_url,
        "username": handle,
        "city": item["city"],
        "subscriber_count": subscriber_count,
        "audience_band": "nano" if subscriber_count is not None and subscriber_count < 10_000 else "micro" if subscriber_count is not None and subscriber_count < 100_000 else "mid" if subscriber_count is not None else "unknown",
        "contactability": "manual_only",
        "verification_status": "original_profile_opened",
        "source_url": profile_url,
        "discovery_source_url": item["search_url"],
        "evidence_url": item["evidence_url"],
        "evidence_summary": f"Видео «{item['evidence_title']}» содержит явную привязку к городу.",
        "directory_queries": [item["query"]],
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Город подтверждён конкретным видео, но не обязательно местом жительства автора.",
            "Перед кампанией нужно вручную проверить аудиторию, активность и brand safety.",
        ],
    }


def collect(workers: int) -> list[dict[str, Any]]:
    discovered: dict[tuple[str, str], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(discover_query, city, query) for city, queries in QUERIES.items() for query in queries]
        for future in as_completed(futures):
            try:
                items = future.result()
            except Exception:
                continue
            for item in items:
                key = (str(item["city"]), str(item["channel_id"]))
                existing = discovered.get(key)
                if existing:
                    continue
                discovered[key] = item
    verified: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(verify, item) for item in discovered.values()]
        for future in as_completed(futures):
            try:
                candidate = future.result()
            except Exception:
                continue
            if candidate:
                verified.append(candidate)
    return sorted(verified, key=lambda item: (str(item["city"]), str(item["display_name"]).lower()))


def write_outputs(candidates: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    city_counts: dict[str, int] = {}
    for candidate in candidates:
        city_counts[str(candidate["city"])] = city_counts.get(str(candidate["city"]), 0) + 1
    report = {
        "schema_version": "1.0",
        "title": "YouTube и Shorts: авторы с публичным контентом о пилотных городах",
        "status": "public_research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "platform_counts": {"youtube": len(candidates)},
        "city_counts": city_counts,
        "candidates": candidates,
        "limitations": ["Выдача YouTube не равна географии аудитории; нужен ручной shortlist."],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["candidate_id", "display_name", "platform", "canonical_url", "username", "city", "subscriber_count", "audience_band", "contactability", "verification_status", "source_url", "discovery_source_url", "evidence_url", "evidence_summary", "researched_at"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(candidates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="outputs/influencer-youtube-base-20260823.json")
    parser.add_argument("--output-csv", default="outputs/influencer-youtube-base-20260823.csv")
    parser.add_argument("--workers", default=12, type=int)
    args = parser.parse_args()
    candidates = collect(args.workers)
    write_outputs(candidates, Path(args.output_json), Path(args.output_csv))
    print(json.dumps({"candidate_count": len(candidates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
