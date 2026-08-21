#!/usr/bin/env python3
"""Targeted exact-v4 dispatcher for a freshly browser-verified Telegram fact."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import dispatch_v4_email_queue_20260820 as dispatch


ALLOWED = {
    "fe680b41-7b49-492a-b101-d4eb97e03d07": {
        "source": "https://t.me/kulturakrd",
        "mode": "fresh",
    },
    "54d0a38c-ec3a-4810-b8f6-92b0d52bd20f": {
        "source": "https://t.me/medclinic_center",
        "mode": "fresh",
    },
    "ba735c02-6c20-48a2-9588-8d847e9d3651": {
        "source": "https://t.me/personaklimentinikitskaya",
        "mode": "exact_two",
    },
}

TARGET_TOUCH_ID = os.environ.get("LOCALOS_TARGET_TOUCH_ID", "").strip()
FACT_SOURCE = os.environ.get("LOCALOS_TELEGRAM_SOURCE", "").strip()
FACT_CHECKED_AT = os.environ.get("LOCALOS_TELEGRAM_CHECKED_AT", "").strip()
FACT_LATEST_AT = os.environ.get("LOCALOS_TELEGRAM_LATEST_AT", "").strip()
FACT_COUNT_30 = int(os.environ.get("LOCALOS_TELEGRAM_COUNT_30", "-1"))

if TARGET_TOUCH_ID not in ALLOWED:
    raise RuntimeError("telegram_target_not_allowed")

original_manifest_rows = dispatch.manifest_rows
original_fact_check = dispatch.fact_check


def targeted_manifest_rows():
    rows, blocked_touch_ids = original_manifest_rows()
    selected = [row for row in rows if row.get("touch_id") == TARGET_TOUCH_ID]
    if len(selected) != 1:
        raise RuntimeError("telegram_target_manifest_row_missing")
    return selected, blocked_touch_ids


def verified_telegram_fact_check(item, recipient):
    reasons, evidence = original_fact_check(item, recipient)
    expected = ALLOWED[TARGET_TOUCH_ID]
    source = str(
        item.get("source_url")
        or (item.get("message_brief_json") or {}).get("source_url")
        or ""
    ).strip()
    now = datetime.now(timezone.utc)
    checked_at = datetime.fromisoformat(FACT_CHECKED_AT.replace("Z", "+00:00"))
    latest_at = datetime.fromisoformat(FACT_LATEST_AT.replace("Z", "+00:00"))
    evidence["telegram_browser_fact"] = {
        "source": FACT_SOURCE,
        "checked_at": checked_at.isoformat(),
        "latest_at": latest_at.isoformat(),
        "count_30": FACT_COUNT_30,
    }
    fact_matches = (
        item.get("touch_id") == TARGET_TOUCH_ID
        and source == expected["source"]
        and FACT_SOURCE == expected["source"]
        and now - checked_at <= timedelta(minutes=10)
        and checked_at <= now + timedelta(minutes=1)
        and FACT_COUNT_30 >= 1
        and now - latest_at <= timedelta(days=30)
    )
    if expected["mode"] == "exact_two":
        fact_matches = fact_matches and FACT_COUNT_30 == 2
    if fact_matches and evidence.get("contact_visible") is True:
        reasons = [reason for reason in reasons if reason != "unsupported_current_observation_source"]
    else:
        reasons.append("telegram_current_fact_mismatch")
    return sorted(set(reasons)), evidence


dispatch.manifest_rows = targeted_manifest_rows
dispatch.fact_check = verified_telegram_fact_check


if __name__ == "__main__":
    raise SystemExit(dispatch.main())
