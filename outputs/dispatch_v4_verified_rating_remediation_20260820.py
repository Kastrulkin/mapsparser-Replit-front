#!/usr/bin/env python3
"""Targeted wrapper for exact v4 touches with verified rating observations."""

from __future__ import annotations

import re

import dispatch_v4_email_queue_20260820 as dispatch


TARGET_TOUCH_IDS = {
    "69cc45a0-51e8-450e-9aac-e9764a0ad4d0",  # Mezocosma
    "85febecc-4044-4365-8bd6-2ccf75d0348e",  # Best Clinique
}

original_manifest_rows = dispatch.manifest_rows
original_fact_check = dispatch.fact_check


def targeted_manifest_rows():
    rows, blocked_touch_ids = original_manifest_rows()
    return [row for row in rows if row.get("touch_id") in TARGET_TOUCH_IDS], blocked_touch_ids


def verified_rating_fact_check(item, recipient):
    reasons, evidence = original_fact_check(item, recipient)
    observation = str(evidence.get("observation") or "")
    rating_match = re.search(
        r"рейтинг\s*[-:]\s*([0-9]+(?:[,.][0-9]+)?)",
        observation,
        flags=re.IGNORECASE,
    )
    review_match = re.search(
        r"публичных\s+отзыв\w*\s*[-:]\s*(\d+)",
        observation,
        flags=re.IGNORECASE,
    )
    if rating_match and review_match:
        expected_rating = float(rating_match.group(1).replace(",", "."))
        expected_reviews = int(review_match.group(1))
        current_rating = float(evidence.get("current_rating") or 0)
        current_reviews = int(evidence.get("current_review_count") or 0)
        if (
            abs(expected_rating - current_rating) <= 0.01
            and expected_reviews == current_reviews
            and evidence.get("contact_visible") is True
        ):
            reasons = [reason for reason in reasons if reason != "unsupported_observation_fact"]
    return reasons, evidence


dispatch.manifest_rows = targeted_manifest_rows
dispatch.fact_check = verified_rating_fact_check


if __name__ == "__main__":
    raise SystemExit(dispatch.main())
