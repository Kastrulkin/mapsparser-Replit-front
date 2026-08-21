#!/usr/bin/env python3
"""Read-only verification of exact Party 1-3 Gmail drafts and no sends."""

from __future__ import annotations

import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

import create_localos_party_email_drafts_20260811 as creator
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config


OUTPUT = Path(
    f"/app/debug_data/localos-party{creator.PARTY_TAG}-email-drafts-verification-20260811.json"
)


def _special_mailbox(client: Any, flag: bytes) -> str:
    status, data = client.list()
    if creator._text(status).upper() != "OK":
        raise RuntimeError("imap_list_failed")
    names = [
        creator._mailbox_name(line)
        for line in (data or [])
        if isinstance(line, bytes) and flag in line
    ]
    if len(names) != 1:
        raise RuntimeError(f"special_mailbox_ambiguous:{flag!r}:{names}")
    return names[0]


def _fetch_all(client: Any, query: str) -> list[Any]:
    status, data = client.uid("fetch", "1:*", query)
    if creator._text(status).upper() != "OK":
        raise RuntimeError(f"imap_batch_fetch_failed:{query}")
    return [
        BytesParser(policy=policy.default).parsebytes(item[1])
        for item in (data or [])
        if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes)
    ]


def main() -> int:
    candidates = creator._artifact_candidates()
    eligible, excluded, sender = creator._production_preflight(candidates)
    config = load_mailbox_config(sender)
    client = None
    try:
        client = _imap_connection(config, timeout=30)
        drafts = _special_mailbox(client, b"\\Drafts")
        sent = _special_mailbox(client, b"\\Sent")
        status, _data = client.select(drafts, readonly=True)
        if creator._text(status).upper() != "OK":
            raise RuntimeError("drafts_mailbox_unavailable")
        messages_by_key: dict[str, list[Any]] = {}
        for message in _fetch_all(client, "(BODY.PEEK[])"):
            key = creator._text(message.get("X-LocalOS-Draft-Key")).strip()
            if key:
                messages_by_key.setdefault(key, []).append(message)
        draft_matches: dict[str, int] = {}
        exact_drafts = 0
        mismatches: list[dict[str, Any]] = []
        for candidate in eligible:
            messages = messages_by_key.get(candidate["draft_key"], [])
            draft_matches[candidate["draft_key"]] = len(messages)
            if len(messages) != 1:
                continue
            message = messages[0]
            recipient_ok = creator._text(message.get("To")).strip().lower() == candidate["recipient"]
            subject_ok = creator._text(message.get("Subject")).strip() == candidate["subject"]
            actual_body_sha = creator._sha(creator._plain_body(message))
            body_ok = actual_body_sha == candidate["content_sha256"]
            if recipient_ok and subject_ok and body_ok:
                exact_drafts += 1
            else:
                mismatches.append(
                    {
                        "party": candidate["party"],
                        "lead_name": candidate["lead_name"],
                        "draft_key": candidate["draft_key"],
                        "recipient_ok": recipient_ok,
                        "subject_ok": subject_ok,
                        "body_ok": body_ok,
                        "expected_body_sha256": candidate["content_sha256"],
                        "actual_body_sha256": actual_body_sha,
                    }
                )

        status, _data = client.select(sent, readonly=True)
        if creator._text(status).upper() != "OK":
            raise RuntimeError("sent_mailbox_unavailable")
        eligible_keys = {candidate["draft_key"] for candidate in eligible}
        sent_keys = [
            creator._text(message.get("X-LocalOS-Draft-Key")).strip()
            for message in _fetch_all(
                client, "(BODY.PEEK[HEADER.FIELDS (X-LOCALOS-DRAFT-KEY)])"
            )
        ]
        sent_match_count = sum(key in eligible_keys for key in sent_keys if key)
        result = {
            "sender_identity": creator.EXPECTED_IDENTITY,
            "eligible_count": len(eligible),
            "excluded_count": len(excluded),
            "exact_draft_count": exact_drafts,
            "draft_key_match_counts": {
                "exactly_one": sum(value == 1 for value in draft_matches.values()),
                "missing": sum(value == 0 for value in draft_matches.values()),
                "duplicate": sum(value > 1 for value in draft_matches.values()),
            },
            "sent_match_count": sent_match_count,
            "mismatches": mismatches,
            "smtp_used": False,
            "database_mutations": 0,
            "verification_passed": (
                exact_drafts == len(eligible)
                and all(value == 1 for value in draft_matches.values())
                and sent_match_count == 0
            ),
        }
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["verification_passed"]:
            raise RuntimeError("draft_verification_failed")
        return 0
    finally:
        _close_imap(client)


if __name__ == "__main__":
    raise SystemExit(main())
