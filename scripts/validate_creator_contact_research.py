#!/usr/bin/env python3
"""Validate public destinations in a creator contact research report."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127 Safari/537.36"
EMAIL_PATTERN = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", re.IGNORECASE)


def fetch(url: str) -> str:
    result = subprocess.run(
        ["curl", "-L", "--max-time", "8", "-A", USER_AGENT, "-s", url],
        capture_output=True,
        check=False,
        timeout=11,
    )
    if result.returncode != 0 or not result.stdout:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def route_type(value: str) -> str:
    lowered = value.lower().strip()
    if EMAIL_PATTERN.fullmatch(lowered):
        return "email"
    if lowered.startswith("@") or "t.me/" in lowered or "telegram.me/" in lowered:
        return "telegram"
    if "instagram.com/" in lowered:
        return "instagram_dm"
    if "tiktok.com/" in lowered:
        return "tiktok_dm"
    if "threads.net/" in lowered or "threads.com/" in lowered:
        return "threads_dm"
    if "vk.me/" in lowered:
        return "vk_messages"
    if "vk.com/" in lowered:
        return "vk_profile"
    if lowered.startswith(("http://", "https://")):
        return "website_or_other"
    return "unknown"


def validate(contact: dict[str, Any]) -> dict[str, Any]:
    value = str(contact.get("value") or "").strip()
    kind = route_type(value)
    checked_at = datetime.now(timezone.utc).isoformat()
    if kind == "email":
        return {"route_type": kind, "status": "syntax_valid_only", "reachable": True, "checked_at": checked_at}
    if kind == "unknown":
        return {"route_type": kind, "status": "unsupported_format", "reachable": False, "checked_at": checked_at}
    url = value
    if value.startswith("@"):
        url = f"https://t.me/{value[1:]}"
    document = fetch(url)
    if not document:
        return {"route_type": kind, "status": "destination_unavailable", "reachable": False, "checked_at": checked_at}
    if kind == "telegram" and not re.search(r'<meta property="og:title" content="[^"]+"', document, flags=re.IGNORECASE):
        return {"route_type": kind, "status": "telegram_identity_not_confirmed", "reachable": False, "checked_at": checked_at}
    return {
        "route_type": kind,
        "status": "public_destination_opened",
        "reachable": True,
        "checked_at": checked_at,
        "acceptance_unconfirmed": kind in {"instagram_dm", "tiktok_dm", "threads_dm", "vk_profile", "website_or_other"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=48)
    arguments = parser.parse_args()
    report = json.loads(arguments.input.read_text(encoding="utf-8"))
    contacts: dict[tuple[str, str], dict[str, Any]] = {}
    for result in report["results"]:
        for contact in [result.get("preferred_contact"), *result.get("alternatives", [])]:
            if contact:
                contacts[(result["profile_id"], str(contact["value"]))] = contact
    validations: dict[tuple[str, str], dict[str, Any]] = {}
    executor = ThreadPoolExecutor(max_workers=max(1, min(arguments.workers, 64)))
    try:
        futures = {executor.submit(validate, contact): key for key, contact in contacts.items()}
        for future in as_completed(futures):
            validations[futures[future]] = future.result()
    finally:
        executor.shutdown(wait=True)
    preferred_reachable = 0
    preferred_unreachable = 0
    for result in report["results"]:
        for contact in [result.get("preferred_contact"), *result.get("alternatives", [])]:
            if not contact:
                continue
            contact["validation"] = validations[(result["profile_id"], str(contact["value"]))]
        preferred = result.get("preferred_contact")
        if preferred:
            if preferred["validation"]["reachable"]:
                preferred_reachable += 1
            else:
                preferred_unreachable += 1
                result["state"] = "preferred_route_unavailable_needs_review"
    report["validation"] = {
        "version": "creator-contact-validation-v1",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "unique_routes_checked": len(contacts),
        "preferred_reachable": preferred_reachable,
        "preferred_unreachable": preferred_unreachable,
        "email_reachability": "syntax_only_no_smtp_probe",
        "messages_sent": 0,
    }
    output = arguments.output or arguments.input
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["validation"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
