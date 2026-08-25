#!/usr/bin/env python3
"""Discover and verify public Instagram, Threads and TikTok creator profiles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0"
SOURCES = [
    ("Краснодар", "https://www.modash.io/find-influencers/russia/krasnodar", "instagram_link"),
    ("Санкт-Петербург", "https://www.modash.io/find-influencers/russia/saint-petersburg", "instagram_link"),
    ("Краснодар", "https://infludata.com/rankings/top-20-influencer-russia-krasnodar-instagram", "instagram_link"),
    ("Краснодар", "https://adinblog.ru/топ/города/краснодар/", "adinblog"),
    ("Санкт-Петербург", "https://adinblog.ru/топ/города/санкт-петербург/", "adinblog"),
    ("Краснодар", "https://www.yapokupayu.ru/blogs/post/luchshie-blogery-krasnodara", "instagram_link"),
    ("Санкт-Петербург", "https://www.sobaka.ru/city/urbanistics/145052", "instagram_link"),
]
BATUMI_HANDLES = [
    "mari.gabaidze",
    "its.chabik",
    "morgana_news",
    "dariamakes8",
    "_rozochka.life_",
    "miron.megalodon",
    "olga.rouge",
    "alinagulayeva_",
]
BATUMI_SOURCE = "https://collabstr.com/top-influencers/instagram/in/georgia/batumi"
IGNORED_HANDLES = {
    "infludata", "modash", "modash.io", "modash.official", "sobaka.ru",
    "yapokupayu.ru", "yapokupayu_ru", "instagram", "facebook", "youtube", "tiktok",
}


def fetch(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            encoded_url = quote(url, safe=":/?&=#%")
            request = Request(encoded_url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("request failed")


def meta(document: str, property_name: str) -> str:
    patterns = [
        rf'<meta[^>]+property="{re.escape(property_name)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="{re.escape(property_name)}"',
    ]
    for pattern in patterns:
        match = re.search(pattern, document, flags=re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def parse_followers(value: str) -> int | None:
    match = re.search(r"([\d.,]+)\s*([KMКМ]?)\s+Followers", value, flags=re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    suffix = match.group(2).upper()
    if suffix in {"K", "К"}:
        number *= 1_000
    elif suffix in {"M", "М"}:
        number *= 1_000_000
    return round(number)


def discover() -> dict[str, dict[str, object]]:
    discovered: dict[str, dict[str, object]] = {}
    for city, source_url, source_type in SOURCES:
        try:
            document = fetch(source_url)
        except (HTTPError, URLError, TimeoutError):
            continue
        if source_type == "adinblog":
            handles = re.findall(r'/(?:блогер|%D0%B1%D0%BB%D0%BE%D0%B3%D0%B5%D1%80)/([A-Za-z0-9_.]{3,})', document, flags=re.IGNORECASE)
        else:
            handles = re.findall(r'href=["\']https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]{3,})', document, flags=re.IGNORECASE)
        for handle in handles:
            normalized = handle.lower().strip("./")
            if normalized in IGNORED_HANDLES:
                continue
            item = discovered.setdefault(normalized, {"handle": handle, "city": city, "discovery_sources": []})
            item["discovery_sources"].append(source_url)
    for handle in BATUMI_HANDLES:
        discovered[handle.lower()] = {
            "handle": handle,
            "city": "Батуми",
            "discovery_sources": [BATUMI_SOURCE],
        }
    return discovered


def verify(item: dict[str, object]) -> dict[str, object] | None:
    handle = str(item["handle"])
    instagram_url = f"https://www.instagram.com/{handle}"
    try:
        instagram_document = fetch(instagram_url)
    except (HTTPError, URLError, TimeoutError):
        return None
    instagram_title = meta(instagram_document, "og:title")
    instagram_description = meta(instagram_document, "og:description")
    if f"@{handle.lower()}" not in instagram_title.lower():
        return None
    followers = parse_followers(instagram_description)
    if followers and followers > 200_000:
        return None
    channels: list[dict[str, object]] = [{
        "platform": "instagram",
        "canonical_url": instagram_url,
        "verification_status": "original_profile_opened",
        "follower_count": followers,
        "source_url": instagram_url,
    }]
    threads_url = f"https://www.threads.com/@{handle}"
    threads_verified = False
    try:
        threads_document = fetch(threads_url)
        threads_title = meta(threads_document, "og:title")
        threads_description = meta(threads_document, "og:description")
        if f"@{handle.lower()}" in threads_title.lower() and "threads • log in" not in threads_title.lower():
            channels.append({
                "platform": "threads",
                "canonical_url": threads_url,
                "verification_status": "original_profile_opened",
                "follower_count": parse_followers(threads_description),
                "source_url": threads_url,
            })
            threads_verified = True
    except (HTTPError, URLError, TimeoutError):
        pass
    if not threads_verified:
        threads_index_url = f"https://threadlook.com/profile/{handle}"
        try:
            threads_index_document = fetch(threads_index_url)
            title_match = re.search(r"<title>(.*?)</title>", threads_index_document, flags=re.IGNORECASE | re.DOTALL)
            threads_index_title = html.unescape(title_match.group(1)).strip() if title_match else ""
            if f"@{handle.lower()}" in threads_index_title.lower() and "page not found" not in threads_index_title.lower():
                channels.append({
                    "platform": "threads",
                    "canonical_url": threads_url,
                    "verification_status": "public_index_verified",
                    "follower_count": parse_followers(threads_index_document),
                    "source_url": threads_index_url,
                })
        except (HTTPError, URLError, TimeoutError):
            pass
    tiktok_url = f"https://www.tiktok.com/@{handle}"
    tiktok_document = ""
    try:
        tiktok_document = fetch(tiktok_url)
    except (HTTPError, URLError, TimeoutError):
        pass
    unique_ids = re.findall(r'"uniqueId":"([^"]+)"', tiktok_document)
    if not any(value.lower() == handle.lower() for value in unique_ids):
        try:
            curl_result = subprocess.run(
                ["curl", "-L", "--max-time", "15", "-A", "Mozilla/5.0", "-s", tiktok_url],
                capture_output=True,
                check=False,
                timeout=18,
            )
            tiktok_document = curl_result.stdout.decode("utf-8", errors="replace")
            unique_ids = re.findall(r'"uniqueId":"([^"]+)"', tiktok_document)
        except (OSError, subprocess.SubprocessError):
            unique_ids = []
    if any(value.lower() == handle.lower() for value in unique_ids):
        channels.append({
            "platform": "tiktok",
            "canonical_url": tiktok_url,
            "verification_status": "original_profile_opened",
            "follower_count": None,
            "source_url": tiktok_url,
        })
    display_name = instagram_title.split("(@", 1)[0].strip()
    candidate_id = hashlib.sha256(f"instagram:{handle.lower()}".encode("utf-8")).hexdigest()[:20]
    description_text = instagram_description
    contactability = "advertising_contact" if re.search(
        r"(ugc|influencer|collab|cooperation|сотруднич|реклам)",
        f"{instagram_title} {instagram_description}",
        flags=re.IGNORECASE,
    ) else "manual_only"
    return {
        "candidate_id": candidate_id,
        "display_name": display_name or handle,
        "profile_type": "author",
        "primary_handle": handle,
        "city": item["city"],
        "description": description_text,
        "contactability": contactability,
        "audience_band": "nano" if followers is not None and followers < 10_000 else "micro" if followers is not None and followers < 100_000 else "mid" if followers is not None else "unknown",
        "channels": channels,
        "discovery_sources": item["discovery_sources"],
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Город подтверждён публичной городской подборкой; долю аудитории в городе нужно запросить перед кампанией.",
            "Профиль существует, но готовность к конкретной коллаборации не подразумевается.",
        ],
    }


def collect(workers: int) -> list[dict[str, object]]:
    candidates = discover()
    verified: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(verify, item) for item in candidates.values()]
        for future in as_completed(futures):
            try:
                result = future.result()
            except (HTTPError, URLError, TimeoutError):
                continue
            if result:
                verified.append(result)
    return sorted(verified, key=lambda item: (str(item["city"]), str(item["display_name"]).lower()))


def write_outputs(candidates: list[dict[str, object]], json_path: Path, csv_path: Path) -> None:
    platform_counts: dict[str, int] = {}
    city_counts: dict[str, int] = {}
    for candidate in candidates:
        city = str(candidate["city"])
        city_counts[city] = city_counts.get(city, 0) + 1
        for channel in candidate["channels"]:
            platform = str(channel["platform"])
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
    report = {
        "schema_version": "1.0",
        "title": "Публичные Instagram, Threads и TikTok авторы пилотных городов",
        "status": "public_research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "channel_count": sum(platform_counts.values()),
        "platform_counts": platform_counts,
        "city_counts": city_counts,
        "candidates": candidates,
        "limitations": [
            "Это discovery-база, а не утверждённый shortlist.",
            "Никакие сообщения не отправлялись и production LocalOS не изменялся.",
        ],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["candidate_id", "display_name", "primary_handle", "city", "audience_band", "contactability", "platform", "canonical_url", "follower_count", "source_url"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for candidate in candidates:
            for channel in candidate["channels"]:
                writer.writerow({
                    "candidate_id": candidate["candidate_id"],
                    "display_name": candidate["display_name"],
                    "primary_handle": candidate["primary_handle"],
                    "city": candidate["city"],
                    "audience_band": candidate["audience_band"],
                    "contactability": candidate["contactability"],
                    "platform": channel["platform"],
                    "canonical_url": channel["canonical_url"],
                    "follower_count": channel["follower_count"],
                    "source_url": channel["source_url"],
                })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="outputs/influencer-social-base-20260823.json")
    parser.add_argument("--output-csv", default="outputs/influencer-social-base-20260823.csv")
    parser.add_argument("--workers", default=10, type=int)
    arguments = parser.parse_args()
    candidates = collect(arguments.workers)
    write_outputs(candidates, Path(arguments.output_json), Path(arguments.output_csv))
    print(json.dumps({"candidate_count": len(candidates), "outputs": [arguments.output_json, arguments.output_csv]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
