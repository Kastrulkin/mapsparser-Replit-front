#!/usr/bin/env python3
"""Create Gmail drafts for LocalOS Parties 1-3 without sending.

The operation uses IMAP APPEND to the exact Gmail Drafts mailbox. SMTP is never
opened. Production reads are transaction-read-only; only Gmail Drafts changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from database_manager import get_db_connection
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config


SENDER_ACCOUNT_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
EXPECTED_IDENTITY = "localosgo@gmail.com"
PARTY_NUMBERS = tuple(
    int(value.strip())
    for value in os.environ.get("LOCALOS_DRAFT_PARTIES", "1,2,3").split(",")
    if value.strip()
)
PARTY_TAG = "-".join(str(value) for value in PARTY_NUMBERS)
OUTPUT = Path(f"/app/debug_data/localos-party{PARTY_TAG}-email-drafts-result-20260811.json")
PARTIES = tuple(
    (
        party,
        Path("/app/debug_data/localos-template-review-v12-20260811.json")
        if party == 1
        else Path(f"/app/debug_data/localos-party{party}-review-v1-20260811.json"),
    )
    for party in PARTY_NUMBERS
)
ALLOWED_CONTACT_STATUSES = {"verified", "confirmed_source"}
PLACEHOLDER_EMAILS = {"mail@example.com", "test@test.ru"}
TERMINAL_LEAD_STATUSES = {
    "sent", "responded", "replied", "disqualified", "rejected",
    "not_relevant", "converted",
}
TERMINAL_PIPELINE_STATUSES = {
    "contacted", "waiting_reply", "second_message_sent", "replied",
    "converted", "closed_lost", "not_relevant", "disqualified",
    "rejected", "sent", "dialog",
}


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _body(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _sha(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _mailbox_name(raw_line: bytes) -> str:
    line = _text(raw_line).strip()
    match = re.search(r'\)\s+"(?:[^"\\]|\\.)*"\s+("(?:[^"\\]|\\.)*"|\S+)\s*$', line)
    if not match:
        raise RuntimeError(f"imap_list_line_unparsed:{line}")
    value = match.group(1)
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1].replace(r'\"', '"').replace(r'\\', '\\')
    return value


def _drafts_mailbox(client: Any) -> str:
    status, data = client.list()
    if _text(status).upper() != "OK":
        raise RuntimeError("imap_list_failed")
    names = [
        _mailbox_name(line)
        for line in (data or [])
        if isinstance(line, bytes) and b"\\Drafts" in line
    ]
    if len(names) != 1:
        raise RuntimeError(f"drafts_mailbox_ambiguous:{names}")
    return names[0]


def _uid_search(client: Any, *criteria: str) -> list[str]:
    status, data = client.uid("search", None, *criteria)
    if _text(status).upper() != "OK":
        raise RuntimeError(f"imap_search_failed:{criteria}")
    return _text(data[0] if data else "").split()


def _fetch_message(client: Any, uid: str) -> Any:
    status, data = client.uid("fetch", uid, "(BODY.PEEK[])")
    if _text(status).upper() != "OK":
        raise RuntimeError(f"imap_fetch_failed:{uid}")
    raw = next(
        (
            item[1]
            for item in (data or [])
            if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes)
        ),
        b"",
    )
    return BytesParser(policy=policy.default).parsebytes(raw)


def _plain_body(message: Any) -> str:
    if message.is_multipart():
        part = message.get_body(preferencelist=("plain",))
        return _body(part.get_content() if part else "")
    return _body(message.get_content())


def _legacy_fingerprint(recipient: str, subject: str, body: str) -> str:
    return _sha(f"{recipient.strip().lower()}\n{subject.strip()}\n{_body(body)}")


def _message(candidate: dict[str, Any]) -> bytes:
    # Keep long UTF-8 subjects in one encoded word. Default RFC 2047 folding
    # can erase a semantic space when Gmail joins adjacent encoded words.
    smtp_policy = policy.SMTP.clone(max_line_length=998, refold_source="none")
    message = EmailMessage(policy=smtp_policy)
    message["From"] = EXPECTED_IDENTITY
    message["To"] = candidate["recipient"]
    message["Subject"] = candidate["subject"]
    message["X-LocalOS-Draft-Key"] = candidate["draft_key"]
    message["X-LocalOS-Party"] = str(candidate["party"])
    message["X-LocalOS-Lead-ID"] = candidate["lead_id"]
    message["X-LocalOS-Workstream-ID"] = candidate["workstream_id"]
    message["X-LocalOS-Content-SHA256"] = candidate["content_sha256"]
    message.set_content(candidate["body"], subtype="plain", charset="utf-8")
    return message.as_bytes()


def _artifact_candidates() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for party, path in PARTIES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for lead in payload.get("results") or []:
            for touch in lead.get("touches") or []:
                if touch.get("channel") != "email":
                    continue
                gate = touch.get("quality_gate") or {}
                if not gate.get("passed") or int(gate.get("total_score") or 0) != 18:
                    raise RuntimeError(f"ungated_email:{party}:{lead.get('lead_id')}")
                if touch.get("sender_account_id") != SENDER_ACCOUNT_ID:
                    raise RuntimeError(f"sender_account_mismatch:{party}:{lead.get('lead_id')}")
                body = _body(_text(touch.get("text")))
                subject = _text(touch.get("subject")).strip()
                base = {
                    "party": party,
                    "lead_name": lead.get("name"),
                    "lead_id": str(lead["lead_id"]),
                    "workstream_id": str(lead["workstream_id"]),
                    "contact_point_id": str(touch["contact_point_id"]),
                    "subject": subject,
                    "body": body,
                    "content_sha256": _sha(body),
                }
                base["draft_key"] = _sha(
                    "|".join(
                        [
                            "localos-party-email-draft-v1",
                            str(party),
                            base["lead_id"],
                            base["workstream_id"],
                            base["contact_point_id"],
                            subject,
                            base["content_sha256"],
                        ]
                    )
                )
                records.append(base)
    return records


def _production_preflight(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    contact_ids = [item["contact_point_id"] for item in candidates]
    lead_ids = [item["lead_id"] for item in candidates]
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(
            """
            SELECT cp.id,cp.lead_id,cp.contact_type,cp.value,cp.normalized_value,
                   cp.verification_status,cp.source_url,cp.verified_at,
                   l.status AS lead_status,l.pipeline_status,
                   ws.id AS workstream_id,ws.status AS workstream_status,
                   ws.lifecycle_status
            FROM lead_contact_points cp
            JOIN prospectingleads l ON l.id=cp.lead_id
            JOIN lead_workstreams ws ON ws.lead_id=l.id AND ws.workstream_type='localos_sales'
            WHERE cp.id=ANY(%s::uuid[])
            """,
            (contact_ids,),
        )
        contacts = {str(row["id"]): dict(row) for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT l.id AS lead_id,
              (SELECT COUNT(*) FROM outreachsendqueue q
                 WHERE q.lead_id=l.id AND q.sent_at IS NOT NULL) AS sent_queue,
              (SELECT COUNT(*) FROM outreach_campaign_touches t
                 JOIN outreach_campaigns c ON c.id=t.campaign_id
                 WHERE c.lead_id=l.id AND t.status IN ('sent','delivered','manual_sent')) AS sent_touches,
              (SELECT COUNT(*) FROM outreach_inbound_events i
                 WHERE i.lead_id=l.id AND COALESCE(i.is_human,FALSE)=TRUE) AS human_inbound,
              (SELECT COUNT(*) FROM outreachreactions r WHERE r.lead_id=l.id) AS reactions,
              (SELECT COUNT(*) FROM outreach_suppressions s
                 WHERE s.lead_id=l.id AND (s.expires_at IS NULL OR s.expires_at>NOW())) AS suppressions,
              (SELECT COUNT(*) FROM outreachsendqueue q
                 WHERE q.lead_id=l.id AND q.sent_at IS NULL
                   AND q.delivery_status IN ('queued','retry','sending')) AS active_queue
            FROM prospectingleads l WHERE l.id=ANY(%s)
            """,
            (lead_ids,),
        )
        safety = {str(row["lead_id"]): dict(row) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT * FROM outreach_sender_accounts WHERE id=%s AND channel='email'",
            (SENDER_ACCOUNT_ID,),
        )
        sender_rows = cursor.fetchall()
        connection.rollback()
    finally:
        connection.close()
    if len(sender_rows) != 1:
        raise RuntimeError(f"sender_account_count:{len(sender_rows)}")
    sender = dict(sender_rows[0])
    if _text(sender.get("sender_identity")).lower() != EXPECTED_IDENTITY:
        raise RuntimeError("sender_identity_mismatch")
    if sender.get("status") != "connected" or not sender.get("outreach_enabled"):
        raise RuntimeError("sender_not_connected_or_enabled")

    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen_recipient: set[str] = set()
    for candidate in candidates:
        contact = contacts.get(candidate["contact_point_id"])
        current = safety.get(candidate["lead_id"]) or {}
        reasons: list[str] = []
        if not contact:
            reasons.append("CONTACT_NOT_FOUND")
        else:
            if str(contact.get("lead_id")) != candidate["lead_id"]:
                reasons.append("CONTACT_LEAD_MISMATCH")
            if str(contact.get("workstream_id")) != candidate["workstream_id"]:
                reasons.append("CONTACT_WORKSTREAM_MISMATCH")
            if contact.get("contact_type") != "email":
                reasons.append("CONTACT_NOT_EMAIL")
            if contact.get("verification_status") not in ALLOWED_CONTACT_STATUSES:
                reasons.append("CONTACT_NOT_VERIFIED")
            recipient = _text(contact.get("normalized_value") or contact.get("value")).strip().lower()
            if not recipient or "@" not in recipient:
                reasons.append("RECIPIENT_INVALID")
            if recipient in PLACEHOLDER_EMAILS:
                reasons.append("PLACEHOLDER_RECIPIENT")
            if recipient in seen_recipient:
                reasons.append("DUPLICATE_RECIPIENT")
            if _text(contact.get("lead_status")) in TERMINAL_LEAD_STATUSES:
                reasons.append("TERMINAL_LEAD_STATUS")
            if _text(contact.get("pipeline_status")) in TERMINAL_PIPELINE_STATUSES:
                reasons.append("TERMINAL_PIPELINE_STATUS")
        for key, reason in (
            ("sent_queue", "ALREADY_SENT"),
            ("sent_touches", "ALREADY_SENT"),
            ("human_inbound", "HUMAN_INBOUND"),
            ("reactions", "REACTION_HISTORY"),
            ("suppressions", "SUPPRESSED"),
        ):
            if int(current.get(key) or 0):
                reasons.append(reason)
        if reasons:
            excluded.append(
                {
                    "party": candidate["party"],
                    "lead_name": candidate["lead_name"],
                    "lead_id": candidate["lead_id"],
                    "reasons": sorted(set(reasons)),
                }
            )
            continue
        enriched = {
            **candidate,
            "recipient": recipient,
            "contact_verification_status": contact.get("verification_status"),
            "contact_source_url": contact.get("source_url"),
            "active_queue_count": int(current.get("active_queue") or 0),
        }
        enriched["legacy_fingerprint"] = _legacy_fingerprint(
            recipient, enriched["subject"], enriched["body"]
        )
        eligible.append(enriched)
        seen_recipient.add(recipient)
    return eligible, excluded, sender


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    candidates = _artifact_candidates()
    eligible, excluded, sender = _production_preflight(candidates)
    config = load_mailbox_config(sender)
    if config["email"].lower() != EXPECTED_IDENTITY or config["username"].lower() != EXPECTED_IDENTITY:
        raise RuntimeError("mailbox_config_identity_mismatch")

    client = None
    created: list[dict[str, Any]] = []
    existing: list[dict[str, Any]] = []
    try:
        client = _imap_connection(config, timeout=30)
        drafts_mailbox = _drafts_mailbox(client)
        status, _data = client.select(drafts_mailbox, readonly=not args.apply)
        if _text(status).upper() != "OK":
            raise RuntimeError("drafts_mailbox_unavailable")
        existing_uids = _uid_search(client, "ALL")
        existing_keys: set[str] = set()
        existing_fingerprints: set[str] = set()
        for uid in existing_uids:
            message = _fetch_message(client, uid)
            key = _text(message.get("X-LocalOS-Draft-Key")).strip()
            if key:
                existing_keys.add(key)
            recipients = message.get_all("To", [])
            recipient = ",".join(_text(value) for value in recipients).strip().lower()
            existing_fingerprints.add(
                _legacy_fingerprint(
                    recipient,
                    _text(message.get("Subject")),
                    _plain_body(message),
                )
            )

        pending: list[dict[str, Any]] = []
        for candidate in eligible:
            if (
                candidate["draft_key"] in existing_keys
                or candidate["legacy_fingerprint"] in existing_fingerprints
            ):
                existing.append(
                    {
                        "party": candidate["party"],
                        "lead_name": candidate["lead_name"],
                        "recipient": candidate["recipient"],
                        "subject": candidate["subject"],
                        "draft_key": candidate["draft_key"],
                    }
                )
            else:
                pending.append(candidate)

        if args.apply:
            for candidate in pending:
                raw = _message(candidate)
                status, data = client.append(drafts_mailbox, r"(\Draft)", None, raw)
                if _text(status).upper() != "OK":
                    raise RuntimeError(
                        f"imap_append_failed:{candidate['party']}:{candidate['lead_id']}"
                    )
                created.append(
                    {
                        "party": candidate["party"],
                        "lead_name": candidate["lead_name"],
                        "recipient": candidate["recipient"],
                        "subject": candidate["subject"],
                        "draft_key": candidate["draft_key"],
                        "content_sha256": candidate["content_sha256"],
                        "append_response": [_text(value) for value in (data or [])],
                    }
                )

            status, _data = client.select(drafts_mailbox, readonly=True)
            if _text(status).upper() != "OK":
                raise RuntimeError("drafts_readback_unavailable")
            verified_keys: set[str] = set()
            for candidate in created:
                matched = _uid_search(
                    client,
                    "HEADER",
                    "X-LocalOS-Draft-Key",
                    candidate["draft_key"],
                )
                if len(matched) != 1:
                    raise RuntimeError(
                        f"draft_readback_count:{candidate['draft_key']}:{len(matched)}"
                    )
                message = _fetch_message(client, matched[0])
                if _text(message.get("To")).strip().lower() != candidate["recipient"]:
                    raise RuntimeError(f"draft_recipient_mismatch:{candidate['draft_key']}")
                if _text(message.get("Subject")).strip() != candidate["subject"]:
                    raise RuntimeError(f"draft_subject_mismatch:{candidate['draft_key']}")
                if _sha(_plain_body(message)) != candidate["content_sha256"]:
                    raise RuntimeError(f"draft_body_mismatch:{candidate['draft_key']}")
                verified_keys.add(candidate["draft_key"])
        else:
            verified_keys = set()

        result = {
            "mode": "apply" if args.apply else "dry_run",
            "sender_identity": EXPECTED_IDENTITY,
            "sender_account_id": SENDER_ACCOUNT_ID,
            "drafts_mailbox": drafts_mailbox,
            "smtp_used": False,
            "artifact_email_count": len(candidates),
            "eligible_count": len(eligible),
            "excluded_count": len(excluded),
            "existing_count": len(existing),
            "pending_count": len(pending),
            "created_count": len(created),
            "verified_created_count": len(verified_keys),
            "party_counts": {
                str(party): {
                    "eligible": sum(item["party"] == party for item in eligible),
                    "excluded": sum(item["party"] == party for item in excluded),
                    "existing": sum(item["party"] == party for item in existing),
                    "pending": sum(item["party"] == party for item in pending),
                    "created": sum(item["party"] == party for item in created),
                }
                for party, _path in PARTIES
            },
            "excluded": excluded,
            "existing": existing,
            "created": created,
            "database_mutations": 0,
        }
        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    finally:
        _close_imap(client)


if __name__ == "__main__":
    raise SystemExit(main())
