#!/usr/bin/env python3
"""Dispatch only the explicitly approved revised v4 service-menu cohort."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import Json, RealDictCursor

from database_manager import get_db_connection
from dispatch_v4_email_queue_20260820 import (
    EXPECTED_CANONICAL_SHA,
    SENDER_ID,
    SENDER_IDENTITY,
    UNSUITABLE_LOCAL_PARTS,
    block_touch,
    database_safety,
    fetch_runtime,
    gmail_mailboxes,
    gmail_safety,
    imap_search,
    normalized_email,
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
REVISED_PATH = Path("/app/debug_data/localos-v4-revised-service-menu-drafts-20260820.json")
JOURNAL_PATH = Path("/app/debug_data/localos-v4-revised-service-menu-dispatch-20260820.jsonl")
EXPECTED_TOUCH_IDS = {
    "ec975c57-da8b-40fb-95a3-9b325e273910",
    "74f3702c-be57-44b8-909f-bd320e199208",
    "0f840f7c-9748-4902-a294-e3a79bca530c",
    "79ed0287-3e45-4950-9148-c6340adba0be",
    "404c1efa-9b10-4fe9-9b54-6a76821e1871",
    "dabb08e9-9484-4be2-ad8c-041ac6805d69",
}


def journal(payload):
    payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        stream.flush()
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def load_items():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "localos_1000_safe_final_manifest_v4":
        raise RuntimeError("manifest_v4_required")
    if manifest.get("canonical_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("manifest_canonical_sha_mismatch")
    original = {
        str(row.get("touch_id") or ""): row
        for row in manifest.get("touches") or []
        if str(row.get("touch_id") or "") in EXPECTED_TOUCH_IDS
    }
    if set(original) != EXPECTED_TOUCH_IDS:
        raise RuntimeError("canonical_touch_missing")

    revised = json.loads(REVISED_PATH.read_text(encoding="utf-8"))
    if revised.get("base_manifest_canonical_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("revision_manifest_mismatch")
    if revised.get("state") != "draft_for_user_approval":
        raise RuntimeError("revision_state_invalid")
    rows = revised.get("items") or []
    if {str(row.get("touch_id") or "") for row in rows} != EXPECTED_TOUCH_IDS:
        raise RuntimeError("revision_cohort_mismatch")

    checked = []
    for row in rows:
        source = original[str(row["touch_id"])]
        for key in ("lead_id", "campaign_id", "recipient"):
            if str(row.get(key) or "").strip().lower() != str(source.get(key) or "").strip().lower():
                raise RuntimeError(f"revision_{key}_mismatch:{row['touch_id']}")
        if source.get("channel") != "email" or int(source.get("sequence_index") or 0) != 0:
            raise RuntimeError(f"not_first_email_touch:{row['touch_id']}")
        if not str(row.get("subject") or "").strip() or not str(row.get("text") or "").strip():
            raise RuntimeError(f"revision_text_missing:{row['touch_id']}")
        checked.append(row)
    return checked


def public_service_fact(row):
    reasons = []
    evidence = {
        "source_url": row.get("source_url"),
        "contact_source_url": row.get("contact_source_url"),
    }
    count_match = re.search(r"(\d+)\s+услуг", str(row.get("observation") or ""), re.IGNORECASE)
    if not count_match:
        return ["expected_service_count_missing"], evidence
    expected_count = int(count_match.group(1))
    try:
        response = requests.get(
            str(row.get("source_url") or ""),
            timeout=25,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LocalOSCurrentFactCheck/1.0; +https://localos.pro)"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        node = soup.find("script", {"type": "application/json"})
        if not node or not node.string:
            raise RuntimeError("public_map_payload_missing")
        payload = json.loads(node.string)
        public_item = payload["stack"][0]["results"]["items"][0]
        categories = (public_item.get("fullObjects") or {}).get("categories") or []
        services = [item for category in categories for item in category.get("categoryItems") or []]
        priced = [item for item in services if str(item.get("price") or "").strip()]
        expected_org_match = re.search(r"/(\d{6,})/prices", str(row.get("source_url") or ""))
        expected_org = expected_org_match.group(1) if expected_org_match else ""
        actual_org = str(public_item.get("id") or public_item.get("businessId") or "")
        evidence.update(
            {
                "current_title": public_item.get("title") or public_item.get("name"),
                "current_org_id": actual_org,
                "current_service_count": len(services),
                "current_priced_count": len(priced),
                "expected_service_count": expected_count,
            }
        )
        if expected_org and actual_org and expected_org != actual_org:
            reasons.append("map_org_mismatch")
        if len(services) != expected_count:
            reasons.append("service_count_changed")
        if len(priced) != expected_count:
            reasons.append("service_price_coverage_changed")
    except Exception as exc:
        evidence["source_error"] = f"{type(exc).__name__}:{exc}"[:300]
        reasons.append("current_source_unavailable")

    recipient = normalized_email(row.get("recipient"))
    try:
        response = requests.get(
            str(row.get("contact_source_url") or ""),
            timeout=20,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LocalOSContactAudit/1.0; +https://localos.pro)"},
        )
        body = html.unescape(response.text).lower()
        compact = re.sub(r"\s+", "", body)
        visible = (
            recipient in body
            or recipient.replace("@", "&#64;") in body
            or recipient.replace("@", "[at]") in compact
            or recipient.replace("@", "%40") in body
        )
        evidence.update(
            {
                "contact_status": response.status_code,
                "contact_final_url": response.url,
                "contact_visible": visible,
            }
        )
        if response.status_code >= 400:
            reasons.append("contact_source_unavailable")
        elif not visible:
            reasons.append("recipient_not_visible_on_current_source")
    except Exception as exc:
        evidence["contact_error"] = f"{type(exc).__name__}:{exc}"[:300]
        reasons.append("contact_source_unavailable")
    return sorted(set(reasons)), evidence


def record_sent(cursor, runtime, row, delivery):
    sent_at = datetime.now(timezone.utc)
    body_hash = hashlib.sha256(str(row.get("text") or "").encode("utf-8")).hexdigest()
    payload = {
        "source": "native_email_user_authorized_revised_v4",
        "revision_file": REVISED_PATH.name,
        "recipient": row.get("recipient"),
        "operation_key": f"v4-revised-{row.get('touch_id')}",
        "manifest_sha256": EXPECTED_CANONICAL_SHA,
        "provider_message_id": delivery.get("provider_message_id"),
        "sender_identity": SENDER_IDENTITY,
    }
    cursor.execute(
        """
        UPDATE outreach_campaign_touches
        SET status='sent',scheduled_at=%s,subject=%s,generated_text=%s,approved_text=%s,
            preflight_at=%s,preflight_reason=NULL,
            delivery_json=delivery_json || %s,updated_at=%s
        WHERE id=%s AND status NOT IN ('sent','manual_sent','delivered')
        """,
        (
            sent_at,
            row.get("subject"),
            row.get("text"),
            row.get("text"),
            sent_at,
            Json(
                {
                    **payload,
                    "sent_at": sent_at.isoformat(),
                    "delivery_status": "sent",
                    "gmail_sent_verified": True,
                    "body_sha256": body_hash,
                }
            ),
            sent_at,
            runtime.get("id"),
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("touch_state_changed_during_send")
    cursor.execute(
        """
        UPDATE prospectingleads
        SET status='sent',pipeline_status='contacted',last_contact_at=%s,
            last_contact_channel='email',last_contact_comment='Sent approved revised v4 via localosgo@gmail.com',updated_at=%s
        WHERE id=%s
        """,
        (sent_at, sent_at, runtime.get("lead_id")),
    )
    cursor.execute(
        """
        UPDATE lead_workstreams
        SET lifecycle_status='waiting_reply',status_reason='email_sent_revised_v4_user_authorized',
            next_step='Await inbound reply; no YouGile reply-check task requested',state_changed_at=%s,updated_at=%s
        WHERE id=%s
        """,
        (sent_at, sent_at, runtime.get("workstream_id")),
    )
    cursor.execute(
        """
        INSERT INTO outreach_campaign_events(id,campaign_id,touch_id,event_type,payload_json,created_at)
        VALUES(%s,%s,%s,'sent',%s,%s)
        """,
        (str(uuid.uuid4()), runtime.get("campaign_id"), runtime.get("id"), Json(payload), sent_at),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if not args.authorized and not args.preflight_only:
        raise RuntimeError("explicit_authorization_flag_required")

    rows = load_items()
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
    blocked = 0
    try:
        for row in rows:
            recipient = normalized_email(row.get("recipient"))
            runtime = fetch_runtime(cursor, row)
            reasons = []
            evidence = {"manifest_sha256": EXPECTED_CANONICAL_SHA}
            if not runtime:
                reasons.append("runtime_touch_missing")
            else:
                if runtime.get("status") in {"sent", "manual_sent", "delivered"}:
                    connection.rollback()
                    journal({"status": "skipped_already_sent", "name": row.get("name"), "recipient": recipient})
                    continue
                if normalized_email(runtime.get("contact_email")) != recipient:
                    reasons.append("runtime_recipient_mismatch")
                if runtime.get("verification_status") not in {"confirmed_source", "valid_format", "found"}:
                    reasons.append("recipient_not_verified")
                reasons.extend(database_safety(cursor, runtime, recipient))
            local_part = recipient.split("@", 1)[0] if "@" in recipient else ""
            if not recipient or UNSUITABLE_LOCAL_PARTS.search(local_part):
                reasons.append("unsuitable_recipient_role")
            gmail_reasons, gmail_evidence = gmail_safety(client, all_name, sent_name, recipient, row)
            reasons.extend(gmail_reasons)
            evidence["gmail"] = gmail_evidence
            fact_reasons, fact_evidence = public_service_fact(row)
            reasons.extend(fact_reasons)
            evidence["fact_check"] = fact_evidence
            reasons = sorted(set(reasons))
            if reasons:
                if runtime:
                    block_touch(cursor, runtime, ",".join(reasons), evidence)
                    connection.commit()
                else:
                    connection.rollback()
                blocked += 1
                journal(
                    {
                        "status": "blocked",
                        "name": row.get("name"),
                        "recipient": recipient,
                        "touch_id": row.get("touch_id"),
                        "reasons": reasons,
                        "evidence": evidence,
                    }
                )
                continue
            if args.preflight_only:
                connection.rollback()
                journal(
                    {
                        "status": "preflight_passed",
                        "name": row.get("name"),
                        "recipient": recipient,
                        "touch_id": row.get("touch_id"),
                        "evidence": evidence,
                    }
                )
                continue
            delivery = send_email(
                sender,
                recipient=recipient,
                subject=str(row.get("subject") or ""),
                body=str(row.get("text") or ""),
                idempotency_key=f"v4-revised-{row.get('touch_id')}",
                timeout=25,
            )
            provider_id = str(delivery.get("provider_message_id") or "")
            verified_ids = imap_search(client, sent_name, f"rfc822msgid:{provider_id}") if provider_id else []
            if len(verified_ids) != 1:
                connection.rollback()
                journal(
                    {
                        "status": "send_uncertain",
                        "name": row.get("name"),
                        "recipient": recipient,
                        "touch_id": row.get("touch_id"),
                    }
                )
                break
            record_sent(cursor, runtime, row, delivery)
            connection.commit()
            sent += 1
            journal(
                {
                    "status": "sent",
                    "name": row.get("name"),
                    "recipient": recipient,
                    "touch_id": row.get("touch_id"),
                    "sent_count": sent,
                }
            )
    finally:
        _close_imap(client)
        connection.rollback()
        connection.close()
    journal({"status": "complete", "sent": sent, "blocked": blocked, "total": len(rows), "preflight_only": args.preflight_only})


if __name__ == "__main__":
    main()
