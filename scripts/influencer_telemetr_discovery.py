#!/usr/bin/env python3
"""Collect and verify public local Telegram channels from Telemetr city tags."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
SOURCES = {
    "Санкт-Петербург": "https://telemetr.me/catalog/tag/spb",
    "Краснодар": "https://telemetr.me/catalog/tag/krasnodar",
}
EXCLUDED = ("авто и мото", "недвижимость", "вакансии", "даркнет", "для взрослых", "криптовалюты", "объявления")


def fetch(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"})
            with urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as error:
            last_error = error
            time.sleep(0.5 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("request failed")


def clean(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_catalog(city: str, source_url: str) -> list[dict[str, Any]]:
    document = fetch(source_url)
    rows = re.findall(r'<tr data-id="(\d+)".*?</tr>', document, flags=re.IGNORECASE | re.DOTALL)
    result: list[dict[str, Any]] = []
    for channel_id in rows:
        row_match = re.search(rf'<tr data-id="{channel_id}".*?</tr>', document, flags=re.IGNORECASE | re.DOTALL)
        if not row_match:
            continue
        row = row_match.group(0)
        title_match = re.search(rf'<a href="/analytics/\?name={channel_id}"[^>]*>(.*?)</a>', row, flags=re.IGNORECASE | re.DOTALL)
        title = clean(title_match.group(1)) if title_match else ""
        subscribers_match = re.search(r'Подписчиков\s+([\d ]+)', row)
        subscribers = int(subscribers_match.group(1).replace(" ", "")) if subscribers_match else None
        categories = [clean(value) for value in re.findall(r'<a href="/catalog/[^/]+/"[^>]*>(.*?)</a>', row, flags=re.IGNORECASE | re.DOTALL)]
        lowered = " ".join(categories).lower()
        if any(marker in lowered for marker in EXCLUDED):
            continue
        if subscribers and subscribers > 200_000:
            continue
        result.append({
            "telemetr_id": channel_id,
            "city": city,
            "title": title,
            "subscriber_count": subscribers,
            "categories": categories,
            "discovery_source_url": source_url,
            "telemetr_url": f"https://telemetr.me/analytics/?name={channel_id}",
        })
    return result


def verify(item: dict[str, Any]) -> dict[str, Any] | None:
    analytics = fetch(str(item["telemetr_url"]))
    handle_match = re.search(r'канал\s+@([A-Za-z0-9_]{5,})', analytics, flags=re.IGNORECASE)
    if not handle_match:
        title_match = re.search(r'<title>.*?—\s*([A-Za-z0-9_]{5,})\s*—', analytics, flags=re.IGNORECASE | re.DOTALL)
        handle_match = title_match
    if not handle_match:
        return None
    handle = handle_match.group(1)
    canonical_url = f"https://t.me/{handle}"
    original = fetch(canonical_url)
    title_match = re.search(r'<meta property="og:title" content="([^"]+)"', original, flags=re.IGNORECASE)
    if not title_match:
        return None
    display_name = html.unescape(title_match.group(1)).strip()
    description_match = re.search(r'<meta property="og:description" content="([^"]*)"', original, flags=re.IGNORECASE)
    description = html.unescape(description_match.group(1)).strip() if description_match else ""
    subscribers = item["subscriber_count"]
    candidate_id = hashlib.sha256(f"telegram:{handle.lower()}".encode()).hexdigest()[:20]
    contactability = "advertising_contact" if re.search(r"(реклам|сотруднич|коллаборац|партн[\u0435ё]р)", description, flags=re.IGNORECASE) else "manual_only"
    return {
        "candidate_id": candidate_id,
        "display_name": display_name,
        "profile_type": "channel",
        "platform": "telegram",
        "canonical_url": canonical_url,
        "username": handle,
        "city": item["city"],
        "description": description,
        "topics": item["categories"],
        "subscriber_count": subscribers,
        "audience_band": "nano" if subscribers is not None and subscribers < 10_000 else "micro" if subscribers is not None and subscribers < 100_000 else "mid" if subscribers is not None else "unknown",
        "contactability": contactability,
        "verification_status": "original_profile_opened",
        "source_url": canonical_url,
        "discovery_source_url": item["discovery_source_url"],
        "secondary_source_url": item["telemetr_url"],
        "evidence_summary": f"Telemetr отнёс канал к городскому тегу; оригинальный t.me-профиль открыт.",
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Перед кампанией нужно вручную проверить долю локальной аудитории и условия размещения."],
    }


def collect(workers: int) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for city, source_url in SOURCES.items():
        discovered.extend(parse_catalog(city, source_url))
    verified: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(verify, item) for item in discovered]
        for future in as_completed(futures):
            try:
                candidate = future.result()
            except Exception:
                continue
            if candidate:
                verified.append(candidate)
    deduped = {str(item["candidate_id"]): item for item in verified}
    return sorted(deduped.values(), key=lambda item: (str(item["city"]), str(item["display_name"]).lower()))


def write_outputs(candidates: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    city_counts: dict[str, int] = {}
    for item in candidates:
        city_counts[str(item["city"])] = city_counts.get(str(item["city"]), 0) + 1
    report = {"schema_version": "1.0", "title": "Telemetr: проверенные локальные Telegram-каналы", "status": "public_research_only", "generated_at": datetime.now(timezone.utc).isoformat(), "candidate_count": len(candidates), "platform_counts": {"telegram": len(candidates)}, "city_counts": city_counts, "candidates": candidates, "limitations": ["Это discovery-база, а не утверждённый shortlist; никаких сообщений не отправлялось."]}
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["candidate_id", "display_name", "profile_type", "platform", "canonical_url", "username", "city", "description", "topics", "subscriber_count", "audience_band", "contactability", "verification_status", "source_url", "discovery_source_url", "secondary_source_url", "evidence_summary", "researched_at"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for candidate in candidates:
            row = dict(candidate)
            row["topics"] = ", ".join(candidate["topics"])
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="outputs/influencer-telegram-telemetr-base-20260823.json")
    parser.add_argument("--output-csv", default="outputs/influencer-telegram-telemetr-base-20260823.csv")
    parser.add_argument("--workers", default=24, type=int)
    args = parser.parse_args()
    candidates = collect(args.workers)
    write_outputs(candidates, Path(args.output_json), Path(args.output_csv))
    print(json.dumps({"candidate_count": len(candidates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
