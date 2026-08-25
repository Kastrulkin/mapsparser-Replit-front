#!/usr/bin/env python3
"""Discover and verify public local VK communities from editorial directories."""

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
from typing import Any
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
SOURCES = [
    ("Краснодар", "https://krasnodar.mediaohvat.ru/public_blogger"),
    ("Краснодар", "https://www.yapokupayu.ru/blogs/post/luchshie-pabliki-goroda-na-kotorye-stoit-podpisatsya"),
    ("Санкт-Петербург", "https://www.yapokupayu.ru/blogs/post/interesnye-pabliki-o-sankt-peterburge"),
    ("Санкт-Петербург", "https://gorod-plus.tv/news/103042"),
]
MANUAL = [
    ("Батуми", "forum_georgia", "https://emigrants.online/"),
]
EXCLUDED = {"mediaohvat", "yapokru", "yapokru_spb", "yapokupayu_yug", "video_ext.php", "js"}


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def discover() -> list[dict[str, str]]:
    candidates: dict[tuple[str, str], dict[str, str]] = {}
    for city, source_url in SOURCES:
        try:
            document = fetch(source_url)
        except Exception:
            continue
        handles = re.findall(r'https?://(?:www\.)?vk\.com/([A-Za-z0-9_.-]+)', document, flags=re.IGNORECASE)
        for handle in handles:
            normalized = handle.lower().rstrip("./")
            if normalized in EXCLUDED or normalized.startswith("id"):
                continue
            candidates[(city, normalized)] = {"city": city, "handle": handle.rstrip("./"), "discovery_source_url": source_url}
    for city, handle, source_url in MANUAL:
        candidates[(city, handle.lower())] = {"city": city, "handle": handle, "discovery_source_url": source_url}
    return list(candidates.values())


def verify(item: dict[str, str]) -> dict[str, Any] | None:
    handle = item["handle"]
    canonical_url = f"https://vk.com/{handle}"
    document = fetch(canonical_url)
    title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', document, flags=re.IGNORECASE)
    if not title_match:
        return None
    display_name = html.unescape(title_match.group(1)).strip()
    description_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]*)"', document, flags=re.IGNORECASE)
    description = html.unescape(description_match.group(1)).strip() if description_match else ""
    if not display_name or display_name.lower() == "вконтакте":
        return None
    candidate_id = hashlib.sha256(f"vk:{handle.lower()}".encode()).hexdigest()[:20]
    contactability = "community_messages" if re.search(r'(сообщения сообщества|написать сообщение)', document, flags=re.IGNORECASE) else "manual_only"
    return {
        "candidate_id": candidate_id,
        "display_name": display_name,
        "profile_type": "community",
        "platform": "vk",
        "canonical_url": canonical_url,
        "username": handle,
        "city": item["city"],
        "description": description,
        "contactability": contactability,
        "verification_status": "original_profile_opened",
        "source_url": canonical_url,
        "discovery_source_url": item["discovery_source_url"],
        "evidence_summary": "Публичная городская подборка ссылается на сообщество; оригинальная VK-страница открыта.",
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Нужно вручную проверить тематический fit, активность, аудиторию и условия размещения."],
    }


def collect(workers: int) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(verify, item) for item in discover()]
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
    report = {"schema_version": "1.0", "title": "Публичные локальные VK-сообщества", "status": "public_research_only", "generated_at": datetime.now(timezone.utc).isoformat(), "candidate_count": len(candidates), "platform_counts": {"vk": len(candidates)}, "city_counts": city_counts, "candidates": candidates, "limitations": ["База собрана из публичных городских подборок; сообщения не отправлялись."]}
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["candidate_id", "display_name", "profile_type", "platform", "canonical_url", "username", "city", "description", "contactability", "verification_status", "source_url", "discovery_source_url", "evidence_summary", "researched_at"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(candidates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="outputs/influencer-vk-base-20260823.json")
    parser.add_argument("--output-csv", default="outputs/influencer-vk-base-20260823.csv")
    parser.add_argument("--workers", default=12, type=int)
    args = parser.parse_args()
    candidates = collect(args.workers)
    write_outputs(candidates, Path(args.output_json), Path(args.output_csv))
    print(json.dumps({"candidate_count": len(candidates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
