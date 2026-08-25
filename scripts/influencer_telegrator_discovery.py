#!/usr/bin/env python3
"""Collect and verify public Saint Petersburg Telegram channels from Telegrator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_URL = "https://telegrator.ru/channels/spb/"
TELNO_SOURCE_URL = "https://telno.ru/city/Saint-Petersburg"
USER_AGENT = "Mozilla/5.0"
EXCLUDED = ("\u0432\u0430\u043a\u0430\u043d\u0441", "\u043f\u043e\u043b\u0438\u0442\u0438\u043a", "\u043b\u0438\u0431\u0435\u0440\u0442\u0430\u0440", "\u043a\u0440\u0438\u043f\u0442", "\u0441\u0442\u0430\u0432\u043a\u0438", "\u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c")
EXCLUDED_HANDLES = {"a_beglov", "dtp_spb78", "megapolisonline", "rabota_piter", "spb_gde"}
DISTRICT_MARKERS = {
    "\u0410\u0434\u043c\u0438\u0440\u0430\u043b\u0442\u0435\u0439\u0441\u043a\u0438\u0439": ("\u0430\u0434\u043c\u0438\u0440\u0430\u043b\u0442\u0435\u0439\u0441\u043a",),
    "\u0412\u0430\u0441\u0438\u043b\u0435\u043e\u0441\u0442\u0440\u043e\u0432\u0441\u043a\u0438\u0439": ("\u0432\u0430\u0441\u0438\u043b\u0435\u043e\u0441\u0442\u0440\u043e\u0432", "\u0432\u0430\u0441\u044c\u043a\u0430"),
    "\u0412\u044b\u0431\u043e\u0440\u0433\u0441\u043a\u0438\u0439": ("\u0432\u044b\u0431\u043e\u0440\u0433\u0441\u043a",),
    "\u041a\u0430\u043b\u0438\u043d\u0438\u043d\u0441\u043a\u0438\u0439": ("\u043a\u0430\u043b\u0438\u043d\u0438\u043d\u0441\u043a",),
    "\u041a\u0440\u043e\u043d\u0448\u0442\u0430\u0434\u0442\u0441\u043a\u0438\u0439": ("\u043a\u0440\u043e\u043d\u0448\u0442\u0430\u0434",),
    "\u041a\u0443\u0440\u043e\u0440\u0442\u043d\u044b\u0439": ("\u043a\u0443\u0440\u043e\u0440\u0442\u043d",),
    "\u041f\u0435\u0442\u0440\u043e\u0433\u0440\u0430\u0434\u0441\u043a\u0438\u0439": ("\u043f\u0435\u0442\u0440\u043e\u0433\u0440\u0430\u0434",),
    "\u041f\u0440\u0438\u043c\u043e\u0440\u0441\u043a\u0438\u0439": ("\u043f\u0440\u0438\u043c\u043e\u0440\u0441\u043a",),
    "\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u044b\u0439": ("\u0446\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d",),
}


def fetch(url: str) -> str:
    result = subprocess.run(
        ["curl", "-L", "--max-time", "25", "-A", USER_AGENT, "-s", url],
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"Unable to fetch {url}")
    return result.stdout.decode("utf-8", errors="replace")


def clean(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_count(value: str) -> int | None:
    match = re.search(r"([\d.,]+)\s*([KMB\u041a\u041c]?)", value, flags=re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    suffix = match.group(2).upper()
    if suffix in {"K", "\u041a"}:
        number *= 1_000
    elif suffix in {"M", "\u041c"}:
        number *= 1_000_000
    elif suffix == "B":
        number *= 1_000_000_000
    return round(number)


def topics_for(text: str) -> list[str]:
    lowered = text.lower()
    topics = ["\u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433"]
    mapping = {
        "\u0435\u0434\u0430 \u0438 \u0440\u0435\u0441\u0442\u043e\u0440\u0430\u043d\u044b": ("\u0435\u0434", "\u043a\u0430\u0444\u0435", "\u0440\u0435\u0441\u0442\u043e\u0440\u0430\u043d", "\u0433\u0430\u0441\u0442\u0440\u043e\u043d\u043e\u043c"),
        "\u0441\u043e\u0431\u044b\u0442\u0438\u044f \u0438 \u0434\u043e\u0441\u0443\u0433": ("\u0430\u0444\u0438\u0448", "\u0441\u043e\u0431\u044b\u0442", "\u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442", "\u043a\u0443\u0434\u0430 \u0441\u0445\u043e\u0434\u0438\u0442\u044c", "\u0431\u0438\u043b\u0435\u0442"),
        "\u043c\u0435\u0441\u0442\u0430 \u0438 \u043f\u0443\u0442\u0435\u0448\u0435\u0441\u0442\u0432\u0438\u044f": ("\u043c\u0435\u0441\u0442", "\u0433\u0438\u0434", "\u043f\u0443\u0442\u0435\u0448", "\u0433\u0443\u043b\u044f"),
        "\u043a\u043d\u0438\u0433\u0438 \u0438 \u043a\u0443\u043b\u044c\u0442\u0443\u0440\u0430": ("\u043a\u043d\u0438\u0433", "\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440", "\u043a\u0443\u043b\u044c\u0442\u0443\u0440", "\u0438\u0441\u043a\u0443\u0441\u0441\u0442\u0432"),
        "\u0440\u0430\u0439\u043e\u043d\u043d\u044b\u0435 \u043d\u043e\u0432\u043e\u0441\u0442\u0438": ("\u0440\u0430\u0439\u043e\u043d", "\u043c\u0435\u0442\u0440\u043e", "\u043f\u0440\u043e\u0441\u043f\u0435\u043a\u0442"),
    }
    for topic, markers in mapping.items():
        if any(marker in lowered for marker in markers):
            topics.append(topic)
    return topics


def collect() -> list[dict[str, Any]]:
    document = fetch(SOURCE_URL)
    cards = re.findall(r'<a class="card"[^>]+href="/channels/[^/]+/".*?</a>', document, flags=re.DOTALL)
    candidates: list[dict[str, Any]] = []
    seen_handles: set[str] = set()
    checked_at = datetime.now(timezone.utc).isoformat()
    for card in cards:
        handle_match = re.search(r'href="/channels/([A-Za-z0-9_]+)/"', card)
        title_match = re.search(r'aria-label="([^"]+)"', card)
        description_match = re.search(r'<p class="card-desc">(.*?)</p>', card, flags=re.DOTALL)
        members_match = re.search(r'title="\u041f\u043e\u0434\u043f\u0438\u0441\u0447\u0438\u043a\u043e\u0432".*?</svg>([^<]+)</span>', card, flags=re.DOTALL)
        if not handle_match or not title_match:
            continue
        handle = handle_match.group(1)
        if handle.lower() in seen_handles:
            continue
        seen_handles.add(handle.lower())
        title = html.unescape(title_match.group(1)).strip()
        description = clean(description_match.group(1)) if description_match else ""
        combined = f"{title} {description}".lower()
        if any(marker in combined for marker in EXCLUDED):
            continue
        follower_count = parse_count(members_match.group(1)) if members_match else None
        if follower_count and follower_count > 200_000:
            continue
        canonical_url = f"https://t.me/{handle}"
        try:
            original = fetch(canonical_url)
        except RuntimeError:
            continue
        if not re.search(r'<meta property="og:title" content="[^"]+"', original, flags=re.IGNORECASE):
            continue
        districts = [district for district, markers in DISTRICT_MARKERS.items() if any(marker in combined for marker in markers)]
        contact_handles = sorted(set(re.findall(r"@([A-Za-z0-9_]{5,})", description)))
        contactability = "advertising_contact" if re.search(r"(\u0440\u0435\u043a\u043b\u0430\u043c|\u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u0447|\u0441\u0432\u044f\u0437|\u043f\u0440\u0430\u0439\u0441|\u0444\u0438\u0434\u0431\u044d\u043a)", description, flags=re.IGNORECASE) else "manual_only"
        candidate_id = hashlib.sha256(f"telegram:{handle.lower()}".encode()).hexdigest()[:20]
        candidates.append({
            "candidate_id": candidate_id,
            "display_name": title,
            "profile_type": "channel",
            "platform": "telegram",
            "canonical_url": canonical_url,
            "username": handle,
            "city": "\u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433",
            "districts": districts,
            "district_status": "publicly_confirmed" if districts else "ask_creator",
            "description": description,
            "topics": topics_for(combined),
            "subscriber_count": follower_count,
            "audience_band": "nano" if follower_count is not None and follower_count < 10_000 else "micro" if follower_count is not None and follower_count < 100_000 else "mid" if follower_count is not None else "unknown",
            "contactability": contactability,
            "public_contacts": [f"https://t.me/{value}" for value in contact_handles],
            "verification_status": "original_profile_opened",
            "source_url": canonical_url,
            "discovery_source_url": SOURCE_URL,
            "evidence_summary": "Telegrator \u043e\u0442\u043d\u0451\u0441 \u043a\u0430\u043d\u0430\u043b \u043a \u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433\u0443; \u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b\u044c\u043d\u044b\u0439 t.me-\u043f\u0440\u043e\u0444\u0438\u043b\u044c \u043e\u0442\u043a\u0440\u044b\u0442.",
            "researched_at": checked_at,
            "limitations": ["\u0420\u0430\u0439\u043e\u043d \u0438 \u0434\u043e\u043b\u044e \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e\u0439 \u0430\u0443\u0434\u0438\u0442\u043e\u0440\u0438\u0438 \u043d\u0443\u0436\u043d\u043e \u0443\u0442\u043e\u0447\u043d\u0438\u0442\u044c \u043f\u0435\u0440\u0435\u0434 \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u0435\u0439."],
        })
    telno_document = fetch(TELNO_SOURCE_URL)
    telno_cards = re.findall(
        r'<div class="channel card.*?(?=<div class="channel card|</main>|$)',
        telno_document,
        flags=re.DOTALL,
    )
    for card in telno_cards:
        handle_match = re.search(r'/channel/@([A-Za-z0-9_]{5,})', card)
        title_match = re.search(r'title="\u0422\u0435\u043b\u0435\u0433\u0440\u0430\u043c \u043a\u0430\u043d\u0430\u043b ([^"]+)"', card)
        description_match = re.search(r'<blockquote>\s*<blockquote>(.*?)</blockquote>', card, flags=re.DOTALL)
        members_match = re.search(r'<sup title="\u041f\u043e\u0434\u043f\u0438\u0441\u0447\u0438\u043a\u043e\u0432">([^<]+)</sup>', card)
        if not handle_match or not title_match:
            continue
        handle = handle_match.group(1)
        if handle.lower() in seen_handles or handle.lower() in EXCLUDED_HANDLES:
            continue
        title = html.unescape(title_match.group(1)).strip()
        description = clean(description_match.group(1)) if description_match else ""
        combined = f"{title} {description}".lower()
        if any(marker in combined for marker in EXCLUDED):
            continue
        follower_count = parse_count(members_match.group(1)) if members_match else None
        if follower_count and follower_count > 200_000:
            continue
        canonical_url = f"https://t.me/{handle}"
        try:
            original = fetch(canonical_url)
        except RuntimeError:
            continue
        if not re.search(r'<meta property="og:title" content="[^"]+"', original, flags=re.IGNORECASE):
            continue
        seen_handles.add(handle.lower())
        districts = [district for district, markers in DISTRICT_MARKERS.items() if any(marker in combined for marker in markers)]
        contact_handles = sorted(set(re.findall(r"@([A-Za-z0-9_]{5,})", description)))
        contactability = "advertising_contact" if re.search(r"(\u0440\u0435\u043a\u043b\u0430\u043c|\u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u0447|\u0441\u0432\u044f\u0437|\u043f\u0440\u0430\u0439\u0441|\u0444\u0438\u0434\u0431\u044d\u043a|\u0432\u043e\u043f\u0440\u043e\u0441)", description, flags=re.IGNORECASE) else "manual_only"
        candidates.append({
            "candidate_id": hashlib.sha256(f"telegram:{handle.lower()}".encode()).hexdigest()[:20],
            "display_name": title,
            "profile_type": "channel",
            "platform": "telegram",
            "canonical_url": canonical_url,
            "username": handle,
            "city": "\u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433",
            "districts": districts,
            "district_status": "publicly_confirmed" if districts else "ask_creator",
            "description": description,
            "topics": topics_for(combined),
            "subscriber_count": follower_count,
            "audience_band": "nano" if follower_count is not None and follower_count < 10_000 else "micro" if follower_count is not None and follower_count < 100_000 else "mid" if follower_count is not None else "unknown",
            "contactability": contactability,
            "public_contacts": [f"https://t.me/{value}" for value in contact_handles],
            "verification_status": "original_profile_opened",
            "source_url": canonical_url,
            "discovery_source_url": TELNO_SOURCE_URL,
            "evidence_summary": "TelNo \u043e\u0442\u043d\u0451\u0441 \u043a\u0430\u043d\u0430\u043b \u043a \u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433\u0443; \u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b\u044c\u043d\u044b\u0439 t.me-\u043f\u0440\u043e\u0444\u0438\u043b\u044c \u043e\u0442\u043a\u0440\u044b\u0442.",
            "researched_at": checked_at,
            "limitations": ["\u0420\u0430\u0439\u043e\u043d \u0438 \u0434\u043e\u043b\u044e \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e\u0439 \u0430\u0443\u0434\u0438\u0442\u043e\u0440\u0438\u0438 \u043d\u0443\u0436\u043d\u043e \u0443\u0442\u043e\u0447\u043d\u0438\u0442\u044c \u043f\u0435\u0440\u0435\u0434 \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u0435\u0439."],
        })
    return candidates


def write(candidates: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    entities = [{
        "entity_id": candidate["candidate_id"],
        "display_name": candidate["display_name"],
        "profile_type": candidate["profile_type"],
        "primary_handle": candidate["username"],
        "cities": [candidate["city"]],
        "districts": candidate["districts"],
        "description": candidate["description"],
        "topics": candidate["topics"],
        "contactability": candidate["contactability"],
        "preferred_contact": candidate["public_contacts"][0] if candidate["public_contacts"] else None,
        "channels": [{
            "platform": candidate["platform"],
            "canonical_url": candidate["canonical_url"],
            "username": candidate["username"],
            "follower_count": candidate["subscriber_count"],
            "audience_band": candidate["audience_band"],
            "verification_status": candidate["verification_status"],
            "source_url": candidate["source_url"],
            "discovery_source_url": candidate["discovery_source_url"],
            "researched_at": candidate["researched_at"],
        }],
        "evidence": [{
            "observed": candidate["evidence_summary"],
            "source_url": candidate["discovery_source_url"],
            "source_type": "public_catalog_and_original_profile",
            "researched_at": candidate["researched_at"],
            "confidence": 0.85,
        }],
        "research": {
            "researched_at": candidate["researched_at"],
            "district_status": candidate["district_status"],
            "public_contacts": candidate["public_contacts"],
        },
        "limitations": candidate["limitations"],
    } for candidate in candidates]
    report = {
        "schema_version": "1.0",
        "title": "Telegrator: \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043d\u044b\u0435 \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u044b\u0435 Telegram-\u043a\u0430\u043d\u0430\u043b\u044b \u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433\u0430",
        "status": "public_research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "platform_counts": {"telegram": len(candidates)},
        "city_counts": {"\u0421\u0430\u043d\u043a\u0442-\u041f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433": len(candidates)},
        "candidates": candidates,
        "entities": entities,
        "limitations": ["\u041d\u0438\u043a\u0430\u043a\u0438\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u043d\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u043b\u0438\u0441\u044c; \u044d\u0442\u043e discovery-\u0431\u0430\u0437\u0430, \u0430 \u043d\u0435 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d\u043d\u044b\u0439 shortlist."],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["candidate_id", "display_name", "platform", "canonical_url", "username", "city", "districts", "district_status", "topics", "subscriber_count", "audience_band", "contactability", "public_contacts", "verification_status", "source_url", "discovery_source_url", "researched_at"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for candidate in candidates:
            row = dict(candidate)
            row["districts"] = ", ".join(candidate["districts"])
            row["topics"] = ", ".join(candidate["topics"])
            row["public_contacts"] = ", ".join(candidate["public_contacts"])
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="outputs/influencer-telegram-telegrator-spb-20260825.json")
    parser.add_argument("--output-csv", default="outputs/influencer-telegram-telegrator-spb-20260825.csv")
    arguments = parser.parse_args()
    candidates = collect()
    write(candidates, Path(arguments.output_json), Path(arguments.output_csv))
    print(json.dumps({"candidate_count": len(candidates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
