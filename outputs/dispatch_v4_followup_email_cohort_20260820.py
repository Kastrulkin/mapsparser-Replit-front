#!/usr/bin/env python3
"""Safely reconcile or send the five existing v4 email follow-ups due in YouGile."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from psycopg2.extras import RealDictCursor

from database_manager import get_db_connection
from dispatch_v4_email_queue_20260820 import (
    EXPECTED_CANONICAL_SHA,
    SENDER_ID,
    block_touch,
    fact_check,
    fetch_runtime,
    gmail_mailboxes,
    imap_search,
    normalized_email,
    read_message,
    record_sent,
    sender_account,
)
from services.outreach_email_adapter import (
    _close_imap,
    _imap_connection,
    load_mailbox_config,
    send_email,
)
from services.outreach_email_reply_service import sync_email_replies


MANIFEST_PATH = Path("/app/debug_data/localos-1000-safe-final-manifest-v4-20260814.json")
JOURNAL_PATH = Path("/app/debug_data/localos-v4-followup-email-dispatch-20260820.jsonl")
TARGET_IDS = {
    "39b617da-44d3-40ee-be39-755bab8d18c1",
    "02228d2e-13e0-4211-a402-88835dd8833f",
    "653b6b61-2a14-4b13-9338-7b45f0711543",
    "9d608aeb-b8b2-43ea-b2c8-342660014fa5",
    "d7be6cb7-6fea-4afe-a17f-94a6c3832ff4",
    "695b2e65-c1cf-4b60-bf44-a95fc5ac26e3",
    "ea1d992c-5024-4b78-b852-7c7debded59e",
    "329135de-f4bd-49cb-bf20-fed4a35c7eb9",
}


def journal(payload):
    payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        stream.flush()
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def load_rows():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "localos_1000_safe_final_manifest_v4":
        raise RuntimeError("manifest_v4_required")
    if manifest.get("canonical_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("manifest_canonical_sha_mismatch")
    rows = [row for row in manifest.get("touches") or [] if str(row.get("touch_id") or "") in TARGET_IDS]
    if {str(row.get("touch_id") or "") for row in rows} != TARGET_IDS:
        raise RuntimeError("target_manifest_touch_missing")
    for row in rows:
        if row.get("channel") != "email" or int(row.get("sequence_index") or 0) != 1:
            raise RuntimeError(f"target_not_second_email:{row.get('touch_id')}")
    return rows, manifest.get("touches") or []


def fetch_email_message(client, mailbox, uid):
    selected = f'"{mailbox}"' if any(character.isspace() for character in mailbox) else mailbox
    status, _ = client.select(selected, readonly=True)
    if str(status).upper() != "OK":
        return {}
    status, fetched = client.uid("fetch", uid, "(RFC822)")
    if str(status).upper() != "OK":
        return {}
    raw = next(
        (part[1] for part in fetched or [] if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], bytes)),
        None,
    )
    if not raw:
        return {}
    message = BytesParser(policy=policy.default).parsebytes(raw)
    body = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                try:
                    body = str(part.get_content()).strip()
                    break
                except Exception:
                    continue
    else:
        try:
            body = str(message.get_content()).strip()
        except Exception:
            body = ""
    sent_at = None
    try:
        sent_at = parsedate_to_datetime(str(message.get("Date") or ""))
        if sent_at and sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
    except Exception:
        sent_at = None
    return {
        "subject": str(message.get("Subject") or "").strip(),
        "body": body,
        "message_id": str(message.get("Message-ID") or "").strip(),
        "sent_at": sent_at,
    }


def database_followup_safety(cursor, runtime, recipient):
    lead_id = runtime.get("lead_id")
    cursor.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM outreach_suppressions WHERE lead_id=%s AND (expires_at IS NULL OR expires_at>NOW())) suppressions,
          (SELECT COUNT(*) FROM outreach_inbound_events WHERE lead_id=%s AND (COALESCE(is_human,FALSE) OR COALESCE(stops_campaign,FALSE))) inbound,
          (SELECT COUNT(*) FROM outreachreactions WHERE lead_id=%s) reactions,
          (SELECT COUNT(DISTINCT lead_id) FROM lead_contact_points WHERE contact_type='email' AND lower(normalized_value)=lower(%s)) email_leads,
          (SELECT COUNT(*) FROM outreach_sender_health_events health JOIN outreach_campaigns c ON c.id=health.campaign_id WHERE c.lead_id=%s AND health.event_type='delivery_failed') delivery_failures,
          (SELECT COUNT(*) FROM outreachsendqueue q WHERE lower(q.recipient_value)=lower(%s) AND q.delivery_status IN ('sent','delivered')) queue_sent
        """,
        (lead_id, lead_id, lead_id, recipient, lead_id, recipient),
    )
    row = dict(cursor.fetchone() or {})
    reasons = []
    for key in ("suppressions", "inbound", "reactions", "delivery_failures"):
        if int(row.get(key) or 0) > 0:
            reasons.append(key)
    if int(row.get("email_leads") or 0) != 1:
        reasons.append("duplicate_email_across_leads")
    return reasons, row


def prior_manifest_row(all_rows, row):
    candidates = [
        item
        for item in all_rows
        if str(item.get("campaign_id") or "") == str(row.get("campaign_id") or "")
        and item.get("channel") == "email"
        and int(item.get("sequence_index") or 0) == 0
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]


def gmail_followup_safety(client, all_name, sent_name, row, previous):
    recipient = normalized_email(row.get("recipient"))
    sent_ids = imap_search(client, sent_name, f"to:{recipient}")
    reply_ids = imap_search(client, all_name, f"from:{recipient}")
    bounce_ids = imap_search(client, all_name, f"from:mailer-daemon@googlemail.com {recipient}")
    bounce_ids += imap_search(client, all_name, f"from:mailer-daemon@gmail.com {recipient}")
    messages = [fetch_email_message(client, sent_name, uid) for uid in sent_ids[-20:]]
    previous_exact = [
        message
        for message in messages
        if message.get("subject") == str(previous.get("subject") or "").strip()
        and message.get("body") == str(previous.get("text") or "").strip()
    ]
    current_exact = [
        message
        for message in messages
        if message.get("subject") == str(row.get("subject") or "").strip()
        and message.get("body") == str(row.get("text") or "").strip()
    ]
    unique_bodies = {str(message.get("body") or "").strip() for message in messages if message.get("body")}
    reasons = []
    if len(previous_exact) != 1:
        reasons.append("gmail_previous_exact_missing" if not previous_exact else "gmail_previous_exact_duplicate")
    if len(current_exact) > 1:
        reasons.append("gmail_current_exact_duplicate")
    if reply_ids:
        reasons.append("gmail_reply_exists")
    if bounce_ids:
        reasons.append("gmail_bounce_exists")
    if len(unique_bodies) > 2:
        reasons.append("gmail_unexpected_sent_sequence")
    previous_at = previous_exact[0].get("sent_at") if len(previous_exact) == 1 else None
    if previous_at and not current_exact:
        age_hours = (datetime.now(timezone.utc) - previous_at.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours < 72:
            reasons.append("followup_interval_too_short")
    else:
        age_hours = None
    return sorted(set(reasons)), {
        "sent_count": len(sent_ids),
        "unique_body_count": len(unique_bodies),
        "reply_count": len(reply_ids),
        "bounce_count": len(set(bounce_ids)),
        "previous_exact_count": len(previous_exact),
        "current_exact_count": len(current_exact),
        "previous_age_hours": age_hours,
        "current_message_id": current_exact[0].get("message_id") if len(current_exact) == 1 else "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if not args.authorized and not args.preflight_only:
        raise RuntimeError("explicit_authorization_flag_required")
    rows, all_rows = load_rows()
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    sender = sender_account(cursor)
    connection.rollback()
    reply_sync = sync_email_replies(sender_limit=1, per_sender_limit=500, sender_account_id=SENDER_ID)
    if int(reply_sync.get("failed") or 0) > 0:
        raise RuntimeError("reply_sync_failed")
    client = _imap_connection(load_mailbox_config(sender), timeout=25)
    all_name, sent_name = gmail_mailboxes(client)
    sent = 0
    reconciled = 0
    blocked = 0
    try:
        for row in rows:
            recipient = normalized_email(row.get("recipient"))
            runtime = fetch_runtime(cursor, row)
            previous = prior_manifest_row(all_rows, row)
            reasons = []
            evidence = {"manifest_sha256": EXPECTED_CANONICAL_SHA}
            if not runtime:
                reasons.append("runtime_touch_missing")
            if not previous:
                reasons.append("previous_manifest_touch_missing")
            if runtime:
                if normalized_email(runtime.get("contact_email")) != recipient:
                    reasons.append("runtime_recipient_mismatch")
                if runtime.get("verification_status") not in {"confirmed_source", "valid_format", "found"}:
                    reasons.append("recipient_not_verified")
                db_reasons, db_evidence = database_followup_safety(cursor, runtime, recipient)
                reasons.extend(db_reasons)
                evidence["database"] = db_evidence
            if previous:
                gmail_reasons, gmail_evidence = gmail_followup_safety(client, all_name, sent_name, row, previous)
                reasons.extend(gmail_reasons)
                evidence["gmail"] = gmail_evidence
            fact_reasons, fact_evidence = fact_check(row, recipient)
            reasons.extend(fact_reasons)
            evidence["fact_check"] = fact_evidence
            current_exact = int((evidence.get("gmail") or {}).get("current_exact_count") or 0) == 1
            if current_exact:
                reasons = [reason for reason in reasons if reason not in {"gmail_unexpected_sent_sequence"}]
            reasons = sorted(set(reasons))
            if reasons:
                if runtime and runtime.get("status") not in {"sent", "manual_sent", "delivered"}:
                    block_touch(cursor, runtime, ",".join(reasons), evidence)
                    connection.commit()
                else:
                    connection.rollback()
                blocked += 1
                journal({"status": "blocked", "name": row.get("name"), "recipient": recipient, "touch_id": row.get("touch_id"), "reasons": reasons, "evidence": evidence})
                continue
            if current_exact:
                delivery = {"provider_message_id": (evidence.get("gmail") or {}).get("current_message_id"), "delivery_status": "sent"}
                if runtime.get("status") not in {"sent", "manual_sent", "delivered"}:
                    record_sent(cursor, runtime, row, delivery, "gmail_reconciled_existing_v4_followup")
                    connection.commit()
                else:
                    connection.rollback()
                reconciled += 1
                journal({"status": "reconciled_already_sent", "name": row.get("name"), "recipient": recipient, "touch_id": row.get("touch_id")})
                continue
            if runtime.get("status") in {"sent", "manual_sent", "delivered"}:
                connection.rollback()
                blocked += 1
                journal({"status": "blocked_db_sent_gmail_missing", "name": row.get("name"), "recipient": recipient, "touch_id": row.get("touch_id")})
                continue
            if args.preflight_only:
                connection.rollback()
                journal({"status": "preflight_passed", "name": row.get("name"), "recipient": recipient, "touch_id": row.get("touch_id"), "evidence": evidence})
                continue
            delivery = send_email(
                sender,
                recipient=recipient,
                subject=str(row.get("subject") or ""),
                body=str(row.get("text") or ""),
                idempotency_key=f"v4-followup-{row.get('touch_id')}",
                timeout=25,
            )
            provider_id = str(delivery.get("provider_message_id") or "")
            verified = imap_search(client, sent_name, f"rfc822msgid:{provider_id}") if provider_id else []
            if len(verified) != 1:
                connection.rollback()
                journal({"status": "send_uncertain", "name": row.get("name"), "recipient": recipient, "touch_id": row.get("touch_id")})
                break
            record_sent(cursor, runtime, row, delivery, "native_email_user_authorized_v4_followup")
            connection.commit()
            sent += 1
            journal({"status": "sent", "name": row.get("name"), "recipient": recipient, "touch_id": row.get("touch_id"), "sent_count": sent})
    finally:
        _close_imap(client)
        connection.rollback()
        connection.close()
    journal({"status": "complete", "sent": sent, "reconciled": reconciled, "blocked": blocked, "total": len(rows), "preflight_only": args.preflight_only})


if __name__ == "__main__":
    main()
