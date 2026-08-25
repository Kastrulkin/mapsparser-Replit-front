#!/usr/bin/env python3
"""Add public cross-platform routes from shortlisted YouTube About pages."""

from __future__ import annotations

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


REPORT = Path("outputs/influencer-spb-client-shortlists-20260823.json")
CSV_REPORT = Path("outputs/influencer-spb-client-shortlists-20260823.csv")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127 Safari/537.36"


def fetch_routes(url: str) -> dict[str, Any] | None:
    about_url = f"{url.rstrip('/')}/about?hl=en"
    document = urlopen(Request(about_url, headers={"User-Agent": USER_AGENT}), timeout=15).read().decode("utf-8", errors="replace")
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", document, flags=re.IGNORECASE)
    same_as: list[str] = []
    for raw in re.findall(r'"sameAs":\[(.*?)\]', document, flags=re.DOTALL):
        same_as.extend(re.findall(r'"(https?://[^"\\]+)"', raw))
    same_as = list(dict.fromkeys(value.replace("\\u0026", "&") for value in same_as))
    ignored = ("youtube.com", "youtu.be", "donationalerts.com", "boosty.to", "patreon.com")
    routes = [value for value in same_as if not any(marker in value.lower() for marker in ignored)]
    if emails:
        return {"type": "email", "value": emails[0], "status": "cross_platform_needs_confirmation", "source_url": about_url, "confidence": 0.8, "alternatives": routes[:5]}
    priorities = ("t.me/", "instagram.com/", "vk.com/", "dzen.ru/")
    for marker in priorities:
        match = next((value for value in routes if marker in value.lower()), None)
        if match:
            return {"type": "cross_platform", "value": match, "status": "cross_platform_needs_confirmation", "source_url": about_url, "confidence": 0.75, "alternatives": [value for value in routes if value != match][:5]}
    if routes:
        return {"type": "website", "value": routes[0], "status": "cross_platform_needs_confirmation", "source_url": about_url, "confidence": 0.7, "alternatives": routes[1:6]}
    return None


def write_csv(candidates: list[dict[str, Any]]) -> None:
    fields = ["segment_key", "segment", "candidate_id", "entity_id", "name", "profile_type", "primary_handle", "platforms", "score", "stage", "matched_topics", "contact_type", "contact_value", "contact_status", "contact_source_url", "contact_alternatives", "source_url", "observation", "draft", "quality_total", "quality_verdict", "reason_codes", "approval_state", "campaign_state"]
    with CSV_REPORT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in candidates:
            contact = item["public_contact"]
            writer.writerow({
                "segment_key": item["segment_key"], "segment": item["segment"], "candidate_id": item["candidate_id"],
                "entity_id": item["entity_id"], "name": item["name"], "profile_type": item["profile_type"],
                "primary_handle": item.get("primary_handle"), "platforms": ", ".join(item["platforms"]),
                "score": item["score"], "stage": item["stage"], "matched_topics": ", ".join(item["matched_topics"]),
                "contact_type": contact["type"], "contact_value": contact["value"], "contact_status": contact["status"],
                "contact_source_url": contact["source_url"], "contact_alternatives": " | ".join(contact.get("alternatives", [])),
                "source_url": item["opener_source_url"], "observation": item["why_now"], "draft": item["suggested_opener"],
                "quality_total": item["quality"]["total"], "quality_verdict": item["quality"]["verdict"],
                "reason_codes": ", ".join(item["quality"]["reason_codes"]), "approval_state": item["approval_state"],
                "campaign_state": item["campaign_state"],
            })


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    targets: dict[str, list[dict[str, Any]]] = {}
    for candidate in report["candidates"]:
        if candidate["public_contact"]["status"] != "manual_route_needs_contact_check":
            continue
        youtube_url = next((value for value in candidate.get("canonical_urls", []) if "youtube.com/" in value), None)
        if youtube_url:
            targets.setdefault(youtube_url, []).append(candidate)
    found: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_routes, url): url for url in targets}
        for future in as_completed(futures):
            try:
                route = future.result()
            except Exception:
                route = None
            if route:
                found[futures[future]] = route
    updated = 0
    for url, candidates in targets.items():
        route = found.get(url)
        if not route:
            continue
        for candidate in candidates:
            candidate["public_contact"] = route
            candidate["missing_inputs"] = [value for value in candidate["missing_inputs"] if value != "проверенный публичный рекламный контакт"]
            candidate["missing_inputs"].append("подтвердить, что кросс-платформенный контакт принимает рекламные запросы")
            updated += 1
    report["contact_enrichment"] = {"youtube_profiles_checked": len(targets), "candidates_updated": updated, "unique_routes_found": len(found)}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(report["candidates"])
    print(json.dumps(report["contact_enrichment"], ensure_ascii=False))


if __name__ == "__main__":
    main()
