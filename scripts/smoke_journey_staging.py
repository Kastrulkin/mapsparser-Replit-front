#!/usr/bin/env python3
"""Read-only smoke checks for the five synthetic public journey routes."""

from __future__ import annotations

import json
import os
import urllib.request
import uuid


FIXTURE_NAMESPACE = uuid.UUID("e48b07f6-e923-4d6d-9a70-b1de982d2f11")
FLOWS = ("maps", "influencer", "partnership", "content", "automation")
FORBIDDEN_PUBLIC_KEYS = {"email", "phone", "telegram", "credentials", "prompt", "secret"}


def fixture_id(label: str) -> str:
    return str(uuid.uuid5(FIXTURE_NAMESPACE, label))


def request_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status {response.status} for {url}")
        return json.loads(response.read().decode("utf-8"))


def assert_safe_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(forbidden in normalized for forbidden in FORBIDDEN_PUBLIC_KEYS):
                raise AssertionError(f"Forbidden public key: {key}")
            assert_safe_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_safe_keys(nested)


def main() -> None:
    base_url = os.getenv("STAGING_BASE_URL", "http://127.0.0.1:18000").rstrip("/")
    checked = []
    for flow in FLOWS:
        token = f"localos-e2e-{flow}-{fixture_id(f'token:{flow}').replace('-', '')}"
        payload = request_json(f"{base_url}/api/journeys/public/{token}")
        journey = payload.get("journey")
        if not isinstance(journey, dict):
            raise AssertionError(f"Missing public journey payload for {flow}")
        if journey.get("selected_flow") != flow:
            raise AssertionError(f"Wrong selected flow for {flow}: {journey.get('selected_flow')}")
        assert_safe_keys(payload)
        checked.append(flow)
    print(json.dumps({"ok": True, "checked_flows": checked}, ensure_ascii=False))


if __name__ == "__main__":
    main()
