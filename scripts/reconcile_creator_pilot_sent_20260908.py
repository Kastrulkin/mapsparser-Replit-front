"""Read-only Gmail Sent reconciliation for the two approved LocalOS pilot emails."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime

from pg_db_utils import get_db_connection
from services.outreach_email_adapter import (
    _close_imap,
    _imap_connection,
    _imap_mailbox_argument,
    _sent_mailbox,
    _text,
    load_mailbox_config,
)


SENDER_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
MAILBOX = "localosgo@gmail.com"
EXPECTED = {
    "f2529b9a-f17a-4eeb-b6c4-e7a6d8a9faf4": {
        "recipient": "as_kotkin@mail.ru",
        "touch_id": "9c93123a-3283-4531-91bb-0332ff586c5a",
        "subject": "Алексей | LocalOS | сотрудничество",
        "body_sha256": "e4f71385b2ccef500e19ff60ed345c9580583ab209daa57aa5d07c334a97eb4d",
    },
    "779ad74c-52d5-4a05-bfb8-2f92065ca90a": {
        "recipient": "info@cozy-spb.ru",
        "touch_id": "87fa2596-87ab-4ee2-b3eb-792da087fb62",
        "subject": "Татьяна и Яна | LocalOS | сотрудничество",
        "body_sha256": "b04c7ac6f5b1ea7996a8c358570690516cdb677c46b130af0fc9edfe9316f178",
    },
}


def addresses(message, field):
    return sorted(
        address.lower()
        for _, address in getaddresses(message.get_all(field, []))
        if address
    )


def body_result(message, expected_hash):
    parts = [
        part
        for part in message.walk()
        if part.get_content_type() == "text/plain"
        and part.get_content_disposition() != "attachment"
    ]
    if len(parts) != 1:
        return {"matches": False, "reason": "plain_body_count_mismatch"}
    body = parts[0].get_content()
    if not isinstance(body, str):
        return {"matches": False, "reason": "plain_body_not_text"}
    normalized = body.replace("\r\n", "\n")
    candidates = [(normalized, "CRLF_to_LF_only")]
    if normalized.endswith("\n"):
        candidates.append(
            (
                normalized[:-1],
                "CRLF_to_LF_and_one_transport_terminal_LF_removed",
            )
        )
    for candidate, normalization in candidates:
        digest = hashlib.sha256(candidate.encode()).hexdigest()
        if digest == expected_hash:
            return {
                "matches": True,
                "sha256": digest,
                "normalization": normalization,
            }
    return {
        "matches": False,
        "sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "normalization": "CRLF_to_LF_only",
    }


connection = get_db_connection()
try:
    connection.set_session(readonly=True, autocommit=False)
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM outreach_sender_accounts WHERE id=%s", (SENDER_ID,))
    sender = dict(cursor.fetchone())
    cursor.execute(
        """
        SELECT q.id::text queue_id, q.sender_account_id::text sender_account_id,
               q.delivery_status, q.provider_message_id, q.sent_at,
               q.dispatch_started_at, q.attempts, q.error_text, q.updated_at,
               t.id::text touch_id, t.status touch_status, t.subject,
               lower(p.normalized_value) recipient, d.approved_text,
               d.generated_text, c.id::text campaign_id, c.status campaign_status,
               c.version
        FROM outreachsendqueue q
        JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
        JOIN outreach_campaigns c ON c.id=t.campaign_id
        JOIN lead_contact_points p ON p.id=t.contact_point_id
        JOIN outreachmessagedrafts d ON d.id=q.draft_id
        WHERE q.id IN (%s, %s)
        ORDER BY q.id
        """,
        tuple(EXPECTED),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    connection.rollback()
finally:
    connection.close()

if len(rows) != len(EXPECTED):
    raise RuntimeError("exact_queue_set_missing")
config = load_mailbox_config(sender)
if (
    config.get("email", "").lower() != MAILBOX
    or config.get("username", "").lower() != MAILBOX
    or sender.get("sender_identity", "").lower() != MAILBOX
):
    raise RuntimeError("configured_sender_identity_mismatch")

client = None
results = []
try:
    client = _imap_connection(config, timeout=30)
    folder = _sent_mailbox(client)
    status, _ = client.select(_imap_mailbox_argument(folder), readonly=True)
    if _text(status).upper() != "OK":
        raise RuntimeError("sent_folder_unavailable")
    for row in rows:
        expected = EXPECTED[row["queue_id"]]
        approved = row.get("approved_text") or row.get("generated_text") or ""
        approved_hash = hashlib.sha256(approved.encode()).hexdigest()
        if (
            row["sender_account_id"] != SENDER_ID
            or row["touch_id"] != expected["touch_id"]
            or row["recipient"] != expected["recipient"]
            or row["subject"] != expected["subject"]
            or row["version"] != 1
            or approved_hash != expected["body_sha256"]
        ):
            raise RuntimeError("approved_queue_content_changed")

        status, data = client.uid(
            "search",
            None,
            "SINCE",
            "08-Sep-2026",
            "HEADER",
            "To",
            expected["recipient"],
        )
        if _text(status).upper() != "OK" or not data:
            raise RuntimeError("sent_recipient_search_failed")
        exact_matches = []
        for uid in data[0].split() if data[0] else []:
            status, fetched = client.uid(
                "fetch",
                uid,
                "(UID X-GM-MSGID X-GM-THRID INTERNALDATE BODY.PEEK[])",
            )
            pairs = [
                item
                for item in (fetched or [])
                if isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[1], bytes)
            ]
            if _text(status).upper() != "OK" or len(pairs) != 1:
                raise RuntimeError("sent_candidate_fetch_failed")
            metadata = (
                pairs[0][0].decode("ascii", errors="replace")
                if isinstance(pairs[0][0], bytes)
                else str(pairs[0][0])
            )
            message = BytesParser(policy=policy.default).parsebytes(pairs[0][1])
            body = body_result(message, expected["body_sha256"])
            from_matches = addresses(message, "From") == [MAILBOX]
            recipient_matches = addresses(message, "To") == [expected["recipient"]]
            extra_recipients = bool(addresses(message, "Cc") or addresses(message, "Bcc"))
            subject_matches = message.get("Subject") == expected["subject"]
            if not (
                from_matches
                and recipient_matches
                and not extra_recipients
                and subject_matches
                and body["matches"]
            ):
                continue
            gmail_id = re.search(r"X-GM-MSGID (\d+)", metadata)
            gmail_thread = re.search(r"X-GM-THRID (\d+)", metadata)
            internal_date = re.search(r'INTERNALDATE "([^"]+)"', metadata)
            message_date = parsedate_to_datetime(message.get("Date"))
            exact_matches.append(
                {
                    "sent_uid": uid.decode("ascii"),
                    "message_id": str(message.get("Message-ID") or ""),
                    "gmail_message_id": gmail_id.group(1) if gmail_id else None,
                    "gmail_thread_id": gmail_thread.group(1) if gmail_thread else None,
                    "message_date": message_date.astimezone(timezone.utc).isoformat(),
                    "internal_date": internal_date.group(1) if internal_date else None,
                    "from_matches": from_matches,
                    "recipient_matches": recipient_matches,
                    "unexpected_cc_bcc": extra_recipients,
                    "subject_matches": subject_matches,
                    "body": body,
                }
            )
        results.append(
            {
                **{
                    key: value
                    for key, value in row.items()
                    if key not in {"approved_text", "generated_text"}
                },
                "approved_body_sha256": approved_hash,
                "provider": {
                    "verified_sent": len(exact_matches) == 1,
                    "exact_match_count": len(exact_matches),
                    "matches": exact_matches,
                },
            }
        )
finally:
    _close_imap(client)

print(
    json.dumps(
        {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "mailbox": MAILBOX,
            "scope": "exact_two_approved_messages_read_only",
            "verified_sent": sum(
                row["provider"]["verified_sent"] for row in results
            ),
            "results": results,
        },
        ensure_ascii=False,
        default=str,
    )
)
