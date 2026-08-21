#!/usr/bin/env python3
"""Move exactly two accidental placeholder drafts to Gmail Trash."""

from __future__ import annotations

import json
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from database_manager import get_db_connection
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config


SENDER_ACCOUNT_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
EXPECTED_IDENTITY = "localosgo@gmail.com"
TARGETS = {
    "6065a410de22100693db9d121b53f7c8f869c8599bc148e69fc1e9ba2a0c32d9": "mail@example.com",
    "9df1f91d7c7f4007f5a238d0d0216c59aafba9c419d77c47e3ca55416124e6cd": "test@test.ru",
}
OUTPUT = Path("/app/debug_data/localos-placeholder-drafts-rollback-20260811.json")


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _mailbox_name(raw_line: bytes) -> str:
    line = _text(raw_line).strip()
    match = re.search(r'\)\s+"(?:[^"\\]|\\.)*"\s+("(?:[^"\\]|\\.)*"|\S+)\s*$', line)
    if not match:
        raise RuntimeError(f"imap_list_line_unparsed:{line}")
    value = match.group(1)
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1].replace(r'\"', '"').replace(r'\\', '\\')
    return value


def _mailboxes(client: Any) -> tuple[str, str]:
    status, data = client.list()
    if _text(status).upper() != "OK":
        raise RuntimeError("imap_list_failed")
    lines = [line for line in (data or []) if isinstance(line, bytes)]
    drafts = [_mailbox_name(line) for line in lines if b"\\Drafts" in line]
    trash = [_mailbox_name(line) for line in lines if b"\\Trash" in line]
    if len(drafts) != 1 or len(trash) != 1:
        raise RuntimeError(f"mailbox_ambiguity:drafts={drafts}:trash={trash}")
    return drafts[0], trash[0]


def _search(client: Any, key: str) -> list[str]:
    status, data = client.uid("search", None, "HEADER", "X-LocalOS-Draft-Key", key)
    if _text(status).upper() != "OK":
        raise RuntimeError(f"imap_search_failed:{key}")
    return _text(data[0] if data else "").split()


def _recipient(client: Any, uid: str) -> str:
    status, data = client.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (TO)])")
    if _text(status).upper() != "OK":
        raise RuntimeError(f"imap_fetch_failed:{uid}")
    raw = next(
        (item[1] for item in (data or []) if isinstance(item, tuple) and len(item) > 1),
        b"",
    )
    message = BytesParser(policy=policy.default).parsebytes(raw)
    return _text(message.get("To")).strip().lower()


def main() -> int:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(
            "SELECT * FROM outreach_sender_accounts WHERE id=%s AND channel='email'",
            (SENDER_ACCOUNT_ID,),
        )
        rows = cursor.fetchall()
        connection.rollback()
    finally:
        connection.close()
    if len(rows) != 1:
        raise RuntimeError(f"sender_account_count:{len(rows)}")
    sender = dict(rows[0])
    if _text(sender.get("sender_identity")).lower() != EXPECTED_IDENTITY:
        raise RuntimeError("sender_identity_mismatch")
    config = load_mailbox_config(sender)
    client = None
    moved: list[dict[str, str]] = []
    try:
        client = _imap_connection(config, timeout=30)
        capabilities = {_text(value).upper() for value in client.capabilities}
        move_mode = "uid_move" if "MOVE" in capabilities else "copy_delete_expunge"
        drafts, trash = _mailboxes(client)
        status, _data = client.select(drafts, readonly=False)
        if _text(status).upper() != "OK":
            raise RuntimeError("drafts_mailbox_unavailable")
        for key, expected_recipient in TARGETS.items():
            uids = _search(client, key)
            if len(uids) != 1:
                raise RuntimeError(f"target_count:{key}:{len(uids)}")
            if _recipient(client, uids[0]) != expected_recipient:
                raise RuntimeError(f"recipient_mismatch:{key}")
            if move_mode == "uid_move":
                status, _data = client.uid("MOVE", uids[0], trash)
                if _text(status).upper() != "OK":
                    raise RuntimeError(f"move_failed:{key}")
            else:
                status, _data = client.uid("COPY", uids[0], trash)
                if _text(status).upper() != "OK":
                    raise RuntimeError(f"copy_to_trash_failed:{key}")
                status, _data = client.uid("STORE", uids[0], "+FLAGS.SILENT", r"(\Deleted)")
                if _text(status).upper() != "OK":
                    raise RuntimeError(f"mark_deleted_failed:{key}")
            moved.append({"draft_key": key, "recipient": expected_recipient})
        if move_mode == "copy_delete_expunge":
            status, _data = client.expunge()
            if _text(status).upper() != "OK":
                raise RuntimeError("drafts_expunge_failed")

        status, _data = client.select(drafts, readonly=True)
        if _text(status).upper() != "OK":
            raise RuntimeError("drafts_readback_unavailable")
        drafts_remaining = {key: len(_search(client, key)) for key in TARGETS}
        status, _data = client.select(trash, readonly=True)
        if _text(status).upper() != "OK":
            raise RuntimeError("trash_readback_unavailable")
        trash_matches = {key: len(_search(client, key)) for key in TARGETS}
        if any(drafts_remaining.values()) or any(value != 1 for value in trash_matches.values()):
            raise RuntimeError(
                f"rollback_readback_failed:drafts={drafts_remaining}:trash={trash_matches}"
            )
        result = {
            "sender_identity": EXPECTED_IDENTITY,
            "moved_to_trash": moved,
            "drafts_remaining": drafts_remaining,
            "trash_matches": trash_matches,
            "recoverable": True,
            "move_mode": move_mode,
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
