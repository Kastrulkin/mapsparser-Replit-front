#!/usr/bin/env python3
"""Inspect the two subject-normalization mismatches read-only."""

from __future__ import annotations

import json

import create_localos_party_email_drafts_20260811 as creator
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config


KEYS = {
    "838733eab0c795287698f1c503228b7a7e2ff45332337f703130d615c9f1c91d",
    "e58f4d141743fe3d3158e276f62d0eb2f6dac7c29e3b0f909498b4f7952a0bd2",
}


def main() -> int:
    candidates = creator._artifact_candidates()
    eligible, _excluded, sender = creator._production_preflight(candidates)
    expected = {item["draft_key"]: item["subject"] for item in eligible if item["draft_key"] in KEYS}
    client = None
    try:
        client = _imap_connection(load_mailbox_config(sender), timeout=30)
        mailbox = creator._drafts_mailbox(client)
        status, _data = client.select(mailbox, readonly=True)
        if creator._text(status).upper() != "OK":
            raise RuntimeError("drafts_mailbox_unavailable")
        result = []
        for key in sorted(KEYS):
            uids = creator._uid_search(client, "HEADER", "X-LocalOS-Draft-Key", key)
            if len(uids) != 1:
                raise RuntimeError(f"draft_count:{key}:{len(uids)}")
            message = creator._fetch_message(client, uids[0])
            actual = creator._text(message.get("Subject"))
            result.append(
                {
                    "draft_key": key,
                    "expected": expected[key],
                    "actual": actual,
                    "expected_codepoints": [ord(char) for char in expected[key]],
                    "actual_codepoints": [ord(char) for char in actual],
                }
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        _close_imap(client)


if __name__ == "__main__":
    raise SystemExit(main())
