#!/usr/bin/env python3
"""Replace exactly two Gmail drafts whose RFC 2047 folding lost a space."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import create_localos_party_email_drafts_20260811 as creator
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config


TARGET_KEYS = {
    "838733eab0c795287698f1c503228b7a7e2ff45332337f703130d615c9f1c91d",
    "e58f4d141743fe3d3158e276f62d0eb2f6dac7c29e3b0f909498b4f7952a0bd2",
}
OUTPUT = Path("/app/debug_data/localos-folded-subject-drafts-replacement-20260811.json")


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
        raise RuntimeError(f"mailbox_ambiguity:{flag!r}:{names}")
    return names[0]


def main() -> int:
    candidates = creator._artifact_candidates()
    eligible, _excluded, sender = creator._production_preflight(candidates)
    targets = {item["draft_key"]: item for item in eligible if item["draft_key"] in TARGET_KEYS}
    if set(targets) != TARGET_KEYS:
        raise RuntimeError(f"target_candidate_mismatch:{sorted(targets)}")
    client = None
    replaced: list[dict[str, str]] = []
    try:
        client = _imap_connection(load_mailbox_config(sender), timeout=30)
        drafts = _special_mailbox(client, b"\\Drafts")
        trash = _special_mailbox(client, b"\\Trash")
        status, _data = client.select(drafts, readonly=False)
        if creator._text(status).upper() != "OK":
            raise RuntimeError("drafts_mailbox_unavailable")
        for key, candidate in targets.items():
            old_uids = creator._uid_search(client, "HEADER", "X-LocalOS-Draft-Key", key)
            if len(old_uids) != 1:
                raise RuntimeError(f"old_draft_count:{key}:{len(old_uids)}")
            old_message = creator._fetch_message(client, old_uids[0])
            if creator._sha(creator._plain_body(old_message)) != candidate["content_sha256"]:
                raise RuntimeError(f"old_body_mismatch:{key}")

            status, _data = client.append(drafts, r"(\Draft)", None, creator._message(candidate))
            if creator._text(status).upper() != "OK":
                raise RuntimeError(f"corrected_append_failed:{key}")
            all_uids = creator._uid_search(client, "HEADER", "X-LocalOS-Draft-Key", key)
            if len(all_uids) != 2:
                raise RuntimeError(f"post_append_count:{key}:{len(all_uids)}")
            exact_uids: list[str] = []
            stale_uids: list[str] = []
            for uid in all_uids:
                message = creator._fetch_message(client, uid)
                subject_ok = creator._text(message.get("Subject")).strip() == candidate["subject"]
                body_ok = creator._sha(creator._plain_body(message)) == candidate["content_sha256"]
                recipient_ok = creator._text(message.get("To")).strip().lower() == candidate["recipient"]
                (exact_uids if subject_ok and body_ok and recipient_ok else stale_uids).append(uid)
            if len(exact_uids) != 1 or len(stale_uids) != 1:
                raise RuntimeError(f"corrected_identity_failed:{key}")
            status, _data = client.uid("COPY", stale_uids[0], trash)
            if creator._text(status).upper() != "OK":
                raise RuntimeError(f"stale_copy_to_trash_failed:{key}")
            status, _data = client.uid("STORE", stale_uids[0], "+FLAGS.SILENT", r"(\Deleted)")
            if creator._text(status).upper() != "OK":
                raise RuntimeError(f"stale_mark_deleted_failed:{key}")
            replaced.append(
                {
                    "draft_key": key,
                    "lead_name": candidate["lead_name"],
                    "subject": candidate["subject"],
                }
            )
        status, _data = client.expunge()
        if creator._text(status).upper() != "OK":
            raise RuntimeError("drafts_expunge_failed")

        status, _data = client.select(drafts, readonly=True)
        if creator._text(status).upper() != "OK":
            raise RuntimeError("drafts_readback_unavailable")
        for key, candidate in targets.items():
            uids = creator._uid_search(client, "HEADER", "X-LocalOS-Draft-Key", key)
            if len(uids) != 1:
                raise RuntimeError(f"final_count:{key}:{len(uids)}")
            message = creator._fetch_message(client, uids[0])
            if creator._text(message.get("Subject")).strip() != candidate["subject"]:
                raise RuntimeError(f"final_subject_mismatch:{key}")
            if creator._sha(creator._plain_body(message)) != candidate["content_sha256"]:
                raise RuntimeError(f"final_body_mismatch:{key}")
        result = {
            "sender_identity": creator.EXPECTED_IDENTITY,
            "replaced_count": len(replaced),
            "replaced": replaced,
            "old_versions_moved_to_trash": len(replaced),
            "recoverable": True,
            "smtp_used": False,
            "database_mutations": 0,
        }
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        _close_imap(client)


if __name__ == "__main__":
    raise SystemExit(main())
