#!/usr/bin/env python3
"""Validate SPb client shortlists, evidence, drafts and safe states."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path


REPORT = Path("outputs/influencer-spb-client-shortlists-20260823.json")
CSV_REPORT = Path("outputs/influencer-spb-client-shortlists-20260823.csv")
REQUIRED_SEGMENTS = {"organika", "oliver", "children", "riderra"}


def main() -> int:
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    candidates = data["candidates"]
    errors: list[str] = []
    counts = Counter(str(item["segment_key"]) for item in candidates)
    if set(counts) != REQUIRED_SEGMENTS:
        errors.append(f"segment mismatch: {sorted(set(counts) ^ REQUIRED_SEGMENTS)}")
    for segment in REQUIRED_SEGMENTS:
        if counts[segment] != 40:
            errors.append(f"{segment} has {counts[segment]} candidates; 40 required")
        segment_items = [item for item in candidates if item["segment_key"] == segment]
        seen: set[str] = set()
        for item in segment_items:
            urls = set(item.get("canonical_urls", []))
            if seen.intersection(urls):
                errors.append(f"duplicate canonical URL inside {segment}: {sorted(seen.intersection(urls))}")
            seen.update(urls)
    if "threads" not in {platform for item in candidates for platform in item.get("platforms", [])}:
        errors.append("Threads is missing")
    for item in candidates:
        if not item.get("sources") or not item.get("signals"):
            errors.append(f"missing source/evidence: {item['candidate_id']}")
        if not str(item.get("opener_source_url", "")).startswith("https://"):
            errors.append(f"invalid opener source: {item['candidate_id']}")
        if not str(item.get("public_contact", {}).get("value", "")):
            errors.append(f"missing public route: {item['candidate_id']}")
        words = len(str(item.get("suggested_opener", "")).split())
        if not words or words > 90:
            errors.append(f"draft length {words}: {item['candidate_id']}")
        quality = item.get("quality", {})
        if sum(quality.get("scores", {}).values()) != quality.get("total"):
            errors.append(f"quality total mismatch: {item['candidate_id']}")
        if quality.get("verdict") not in {"approve", "revise", "reject"}:
            errors.append(f"invalid quality verdict: {item['candidate_id']}")
        if item.get("approval_state") != "draft_not_approved" or item.get("campaign_state") != "research_only":
            errors.append(f"unsafe state: {item['candidate_id']}")
    if any("semejnyjspb" in url for item in candidates for url in item.get("canonical_urls", [])):
        errors.append("stale identity-drift channel semejnyjspb is still selected")
    with CSV_REPORT.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(candidates):
        errors.append(f"CSV rows {len(rows)} != JSON candidates {len(candidates)}")
    contact_statuses = Counter(item["public_contact"]["status"] for item in candidates)
    result = {
        "valid": not errors,
        "candidate_count": len(candidates),
        "segment_counts": counts,
        "quality_verdicts": Counter(item["quality"]["verdict"] for item in candidates),
        "contact_statuses": contact_statuses,
        "max_draft_words": max(len(item["suggested_opener"].split()) for item in candidates),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
