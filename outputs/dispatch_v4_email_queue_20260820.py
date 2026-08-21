#!/usr/bin/env python3
"""Safely dispatch exact email touches from the canonical LocalOS v4 manifest."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import Json, RealDictCursor

from database_manager import get_db_connection
from services.outreach_email_adapter import (
    _close_imap,
    _imap_connection,
    load_mailbox_config,
    send_email,
)
from services.outreach_email_reply_service import sync_email_replies


MANIFEST_PATH = Path("/app/debug_data/localos-1000-safe-final-manifest-v4-20260814.json")
BLOCKLIST_PATH = Path("/app/debug_data/localos-goal-current-fact-blocklist-20260816.json")
JOURNAL_PATH = Path("/app/debug_data/localos-v4-email-dispatch-20260820.jsonl")
EXPECTED_CANONICAL_SHA = "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386"
SENDER_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
SENDER_IDENTITY = "localosgo@gmail.com"
START_AFTER_TOUCH_ID = "6b4320f9-a590-4ff3-bb6b-92a7d633d7d2"
QUARANTINE_NAMES = {
    "laserprolab", "proskin", "proлицотело", "yourfaceclinic", "yourwings",
    "аристократка", "благодатная", "грейсклуб", "отражение", "ремеди", "эсма",
    "hairfcker", "diadema",
}
UNSUITABLE_LOCAL_PARTS = re.compile(
    r"(^|[._-])(no.?reply|donotreply|hr|career|careers|job|jobs|vacancy|resume|"
    r"press|support|help|security|abuse|postmaster|webmaster|privacy|legal|billing|"
    r"accounting|zakaz|order|booking|reservation|reception|call.?center|desk|"
    r"franchise|claim|offer)([._-]|$)",
    re.IGNORECASE,
)


def clean_name(value: Any) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", str(value or "").lower().replace("ё", "е"))


def normalized_email(value: Any) -> str:
    return str(value or "").strip().lower()


def journal(payload: dict[str, Any]) -> None:
    payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        stream.flush()
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def manifest_rows() -> tuple[list[dict[str, Any]], set[str]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "localos_1000_safe_final_manifest_v4":
        raise RuntimeError("manifest_v4_required")
    if manifest.get("canonical_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("manifest_canonical_sha_mismatch")
    blocklist = json.loads(BLOCKLIST_PATH.read_text(encoding="utf-8"))
    if blocklist.get("base_manifest_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("blocklist_manifest_mismatch")
    blocked_touch_ids = {
        str(item.get("touch_id") or "") for item in blocklist.get("blocks", [])
    }
    touches = manifest.get("touches") or []
    start_index = next(
        index for index, item in enumerate(touches)
        if item.get("touch_id") == START_AFTER_TOUCH_ID
    )
    ordered = touches[start_index + 1:] + touches[:start_index]
    return [item for item in ordered if item.get("channel") == "email"], blocked_touch_ids


def sender_account(cursor: Any) -> dict[str, Any]:
    cursor.execute("SELECT * FROM outreach_sender_accounts WHERE id=%s", (SENDER_ID,))
    row = dict(cursor.fetchone() or {})
    caps = row.get("capabilities_json") or {}
    if (
        normalized_email(row.get("sender_identity")) != SENDER_IDENTITY
        or row.get("status") != "connected"
        or row.get("health_status") != "healthy"
        or not row.get("outreach_enabled")
        or not caps.get("direct_send")
        or not caps.get("reply_sync")
        or row.get("reply_sync_error")
    ):
        raise RuntimeError("sender_not_ready")
    return row


def fetch_runtime(cursor: Any, item: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT touch.*, campaign.lead_id, campaign.workstream_id,
               campaign.status AS campaign_status,
               lead.name AS lead_name, lead.city, lead.address, lead.website,
               lead.status AS lead_status, lead.pipeline_status,
               workstream.lifecycle_status,
               contact.normalized_value AS contact_email,
               contact.verification_status, contact.source_url AS current_contact_source_url
        FROM outreach_campaign_touches touch
        JOIN outreach_campaigns campaign ON campaign.id=touch.campaign_id
        JOIN prospectingleads lead ON lead.id=campaign.lead_id
        JOIN lead_workstreams workstream ON workstream.id=campaign.workstream_id
        LEFT JOIN lead_contact_points contact ON contact.id=touch.contact_point_id
        WHERE touch.id=%s AND campaign.id=%s AND campaign.lead_id=%s
        """,
        (item.get("touch_id"), item.get("campaign_id"), item.get("lead_id")),
    )
    return dict(cursor.fetchone() or {})


def database_safety(cursor: Any, runtime: dict[str, Any], recipient: str) -> list[str]:
    lead_id = runtime.get("lead_id")
    touch_id = runtime.get("id")
    reasons: list[str] = []
    cursor.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM outreach_suppressions WHERE lead_id=%s AND (expires_at IS NULL OR expires_at>NOW())) suppressions,
          (SELECT COUNT(*) FROM outreach_inbound_events WHERE lead_id=%s AND (COALESCE(is_human,FALSE) OR COALESCE(stops_campaign,FALSE))) inbound,
          (SELECT COUNT(*) FROM outreachreactions WHERE lead_id=%s) reactions,
          (SELECT COUNT(DISTINCT lead_id) FROM lead_contact_points WHERE contact_type='email' AND lower(normalized_value)=lower(%s)) email_leads,
          (SELECT COUNT(*) FROM outreach_sender_health_events health JOIN outreach_campaigns c ON c.id=health.campaign_id WHERE c.lead_id=%s AND health.event_type='delivery_failed') delivery_failures,
          (SELECT COUNT(*) FROM outreach_campaigns c JOIN outreach_campaign_touches t ON t.campaign_id=c.id LEFT JOIN lead_contact_points cp ON cp.id=t.contact_point_id WHERE t.id<>%s AND lower(cp.normalized_value)=lower(%s) AND t.status IN ('sent','manual_sent','delivered')) prior_touch_rows,
          (SELECT COUNT(*) FROM outreachsendqueue q WHERE lower(q.recipient_value)=lower(%s) AND q.delivery_status IN ('sent','delivered')) prior_queue_rows
        """,
        (lead_id, lead_id, lead_id, recipient, lead_id, touch_id, recipient, recipient),
    )
    safety = dict(cursor.fetchone() or {})
    for key in ("suppressions", "inbound", "reactions", "delivery_failures", "prior_touch_rows", "prior_queue_rows"):
        if int(safety.get(key) or 0) > 0:
            reasons.append(key)
    if int(safety.get("email_leads") or 0) != 1:
        reasons.append("duplicate_email_across_leads")
    return reasons


def gmail_mailboxes(client: Any) -> tuple[str, str]:
    status, data = client.list()
    if str(status).upper() != "OK":
        raise RuntimeError("imap_list_failed")
    all_name = ""
    sent_name = ""
    for raw in data or []:
        if not isinstance(raw, bytes):
            continue
        line = raw.decode("utf-8", errors="replace")
        match = re.search(r'\)\s+"(?:[^"\\]|\\.)*"\s+("(?:[^"\\]|\\.)*"|\S+)\s*$', line)
        if not match:
            continue
        name = match.group(1).strip('"').replace(r'\"', '"').replace(r'\\', '\\')
        if "\\All" in line:
            all_name = name
        if "\\Sent" in line:
            sent_name = name
    if not all_name or not sent_name:
        raise RuntimeError("gmail_mailboxes_missing")
    return all_name, sent_name


def imap_search(client: Any, mailbox: str, query: str) -> list[str]:
    selected_mailbox = f'"{mailbox}"' if any(character.isspace() for character in mailbox) else mailbox
    status, _ = client.select(selected_mailbox, readonly=True)
    if str(status).upper() != "OK":
        raise RuntimeError("imap_select_failed")
    status, data = client.uid("search", None, "X-GM-RAW", f'"{query}"')
    if str(status).upper() != "OK":
        raise RuntimeError("imap_search_failed")
    raw = data[0] if data else b""
    if isinstance(raw, bytes):
        return raw.decode("ascii", errors="ignore").split()
    return str(raw or "").split()


def read_message(client: Any, mailbox: str, uid: str) -> dict[str, str]:
    selected_mailbox = f'"{mailbox}"' if any(character.isspace() for character in mailbox) else mailbox
    status, _ = client.select(selected_mailbox, readonly=True)
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
                    body = str(part.get_content())
                    break
                except Exception:
                    continue
    else:
        try:
            body = str(message.get_content())
        except Exception:
            body = ""
    return {
        "subject": str(message.get("Subject") or "").strip(),
        "body": body.strip(),
        "message_id": str(message.get("Message-ID") or "").strip(),
        "date": str(message.get("Date") or "").strip(),
    }


def gmail_safety(client: Any, all_name: str, sent_name: str, recipient: str, item: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    sent_ids = imap_search(client, sent_name, f"to:{recipient}")
    reply_ids = imap_search(client, all_name, f"from:{recipient}")
    bounce_ids = imap_search(client, all_name, f"from:mailer-daemon@googlemail.com {recipient}")
    bounce_ids += imap_search(client, all_name, f"from:mailer-daemon@gmail.com {recipient}")
    bounce_ids = sorted(set(bounce_ids))
    exact_prior = False
    if sent_ids:
        for uid in sent_ids[-10:]:
            message = read_message(client, sent_name, uid)
            if message.get("subject") == str(item.get("subject") or "").strip() and message.get("body") == str(item.get("text") or "").strip():
                exact_prior = True
                break
    reasons: list[str] = []
    if sent_ids:
        reasons.append("gmail_sent_exists_exact" if exact_prior else "gmail_sent_exists_other")
    if reply_ids:
        reasons.append("gmail_reply_exists")
    if bounce_ids:
        reasons.append("gmail_bounce_exists")
    return reasons, {
        "sent_count": len(sent_ids),
        "reply_count": len(reply_ids),
        "bounce_count": len(bounce_ids),
        "exact_prior": exact_prior,
    }


def yandex_item(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "Mozilla/5.0 (compatible; LocalOSCurrentFactCheck/1.0; +https://localos.pro)"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    node = soup.find("script", {"type": "application/json"})
    if not node or not node.string:
        raise RuntimeError("public_map_payload_missing")
    payload = json.loads(node.string)
    return payload["stack"][0]["results"]["items"][0]


def fact_check(item: dict[str, Any], recipient: str) -> tuple[list[str], dict[str, Any]]:
    reasons: list[str] = []
    source_url = str(item.get("source_url") or (item.get("message_brief_json") or {}).get("source_url") or "").strip()
    contact_url = str(item.get("contact_source_url") or item.get("open_url") or "").strip()
    observation = str((item.get("message_brief_json") or {}).get("observation") or "").strip()
    fact_text = "\n".join(value for value in (observation, str(item.get("text") or "")) if value)
    evidence: dict[str, Any] = {"source_url": source_url, "contact_url": contact_url, "observation": observation}
    if not source_url or "yandex." not in urllib.parse.urlparse(source_url).netloc:
        reasons.append("unsupported_current_observation_source")
    else:
        try:
            public_item = yandex_item(source_url)
            rating_data = public_item.get("ratingData") or {}
            review_count = int(rating_data.get("reviewCount") or public_item.get("reviewCount") or 0)
            rating = float(rating_data.get("ratingValue") or public_item.get("rating") or 0)
            news_count = int((public_item.get("eventsPreviews") or {}).get("count") or len(public_item.get("mobilePosts") or []))
            evidence.update({
                "current_title": public_item.get("title") or public_item.get("name"),
                "current_review_count": review_count,
                "current_rating": rating,
                "current_news_count": news_count,
                "current_org_id": str(public_item.get("id") or public_item.get("businessId") or ""),
            })
            source_org_match = re.search(r"/(\d{6,})/?(?:reviews/?)?$", urllib.parse.urlparse(source_url).path)
            if source_org_match and evidence["current_org_id"] and source_org_match.group(1) != evidence["current_org_id"]:
                reasons.append("map_org_mismatch")
            review_match = re.search(r"(?:опубликован[оы]?|уже)\s+(\d+)\s+отзы", fact_text.lower())
            generic_reviews = "опубликованы отзывы" in fact_text.lower()
            rating_match = re.search(r"рейтинг\s+([0-9]+(?:[,.][0-9]+)?)", fact_text.lower())
            if review_match and int(review_match.group(1)) != review_count:
                reasons.append("review_count_changed")
            elif rating_match and abs(float(rating_match.group(1).replace(",", ".")) - rating) > 0.01:
                reasons.append("rating_changed")
            elif generic_reviews and review_count <= 0:
                reasons.append("review_fact_changed")
            elif "нет новостей" in fact_text.lower() and news_count != 0:
                reasons.append("news_fact_changed")
            elif ("публикуете новости" in fact_text.lower() or "публикует новости" in fact_text.lower()) and news_count == 0:
                reasons.append("news_fact_changed")
            elif not any((review_match, generic_reviews, rating_match, "новост" in fact_text.lower())):
                reasons.append("unsupported_observation_fact")
        except Exception as exc:
            evidence["source_error"] = f"{type(exc).__name__}:{exc}"[:300]
            reasons.append("current_source_unavailable")
    if not contact_url:
        reasons.append("contact_source_missing")
    else:
        try:
            response = requests.get(
                contact_url,
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
            evidence.update({"contact_status": response.status_code, "contact_final_url": response.url, "contact_visible": visible})
            if response.status_code >= 400:
                reasons.append("contact_source_unavailable")
            elif not visible:
                reasons.append("recipient_not_visible_on_current_source")
        except Exception as exc:
            evidence["contact_error"] = f"{type(exc).__name__}:{exc}"[:300]
            reasons.append("contact_source_unavailable")
    return reasons, evidence


def block_touch(cursor: Any, runtime: dict[str, Any], reason: str, evidence: dict[str, Any]) -> None:
    cursor.execute(
        "UPDATE outreach_campaign_touches SET preflight_at=NOW(),preflight_reason=%s,updated_at=NOW() WHERE id=%s AND status NOT IN ('sent','manual_sent','delivered')",
        (reason[:200], runtime.get("id")),
    )
    cursor.execute(
        """
        INSERT INTO outreach_campaign_events(id,campaign_id,touch_id,event_type,reason_code,payload_json,created_at)
        VALUES(%s,%s,%s,'dispatch_blocked',%s,%s,NOW())
        """,
        (str(uuid.uuid4()), runtime.get("campaign_id"), runtime.get("id"), reason[:200], Json(evidence)),
    )


def record_sent(cursor: Any, runtime: dict[str, Any], item: dict[str, Any], delivery: dict[str, Any], source: str) -> None:
    sent_at = datetime.now(timezone.utc)
    body_hash = hashlib.sha256(str(item.get("text") or "").encode("utf-8")).hexdigest()
    payload = {
        "source": source,
        "recipient": item.get("recipient"),
        "operation_key": f"v4-{item.get('touch_id')}",
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
        WHERE id=%s
        """,
        (
            sent_at, item.get("subject"), item.get("text"), item.get("text"), sent_at,
            Json({**payload, "sent_at": sent_at.isoformat(), "delivery_status": "sent", "gmail_sent_verified": True, "body_sha256": body_hash}),
            sent_at, runtime.get("id"),
        ),
    )
    cursor.execute(
        """
        UPDATE prospectingleads
        SET status='sent',pipeline_status='contacted',last_contact_at=%s,
            last_contact_channel='email',last_contact_comment='Sent exact v4 via localosgo@gmail.com',updated_at=%s
        WHERE id=%s
        """,
        (sent_at, sent_at, runtime.get("lead_id")),
    )
    cursor.execute(
        """
        UPDATE lead_workstreams
        SET lifecycle_status='waiting_reply',status_reason='email_sent_v4_user_authorized',
            next_step='Ожидать входящий ответ',state_changed_at=%s,updated_at=%s
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=149)
    parser.add_argument("--spacing-seconds", type=int, default=180)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    rows, blocked_touch_ids = manifest_rows()
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    sender = sender_account(cursor)
    connection.rollback()
    reply_sync = sync_email_replies(sender_limit=1, per_sender_limit=500, sender_account_id=SENDER_ID)
    if int(reply_sync.get("failed") or 0) > 0:
        raise RuntimeError("reply_sync_failed")
    config = load_mailbox_config(sender)
    client = _imap_connection(config, timeout=25)
    all_name, sent_name = gmail_mailboxes(client)
    sent = 0
    checked = 0
    try:
        for item in rows:
            if sent >= args.limit:
                break
            if int(item.get("sequence_index") or 0) != 0:
                continue
            checked += 1
            recipient = normalized_email(item.get("recipient"))
            reasons: list[str] = []
            evidence: dict[str, Any] = {"manifest_sha256": EXPECTED_CANONICAL_SHA}
            runtime = fetch_runtime(cursor, item)
            if not runtime:
                reasons.append("runtime_touch_missing")
            else:
                if runtime.get("status") in {"sent", "manual_sent", "delivered"}:
                    connection.rollback()
                    journal({"status": "skipped_already_sent", "name": item.get("name"), "recipient": recipient, "touch_id": item.get("touch_id")})
                    continue
                if normalized_email(runtime.get("contact_email")) != recipient:
                    reasons.append("runtime_recipient_mismatch")
                if runtime.get("verification_status") not in {"confirmed_source", "valid_format", "found"}:
                    reasons.append("recipient_not_verified")
                reasons.extend(database_safety(cursor, runtime, recipient))
            name_key = clean_name(item.get("name"))
            if any(value in name_key for value in QUARANTINE_NAMES):
                reasons.append("quarantine")
            if item.get("touch_id") in blocked_touch_ids:
                reasons.append("current_fact_blocklist")
            local_part = recipient.split("@", 1)[0] if "@" in recipient else ""
            if not recipient or UNSUITABLE_LOCAL_PARTS.search(local_part):
                reasons.append("unsuitable_recipient_role")
            gmail_reasons, gmail_evidence = gmail_safety(client, all_name, sent_name, recipient, item)
            reasons.extend(gmail_reasons)
            evidence["gmail"] = gmail_evidence
            fact_reasons, fact_evidence = fact_check(item, recipient)
            reasons.extend(fact_reasons)
            evidence["fact_check"] = fact_evidence
            reasons = sorted(set(reasons))
            if reasons:
                reason = ",".join(reasons)
                if runtime and reason != "runtime_already_sent":
                    block_touch(cursor, runtime, reason, evidence)
                    connection.commit()
                else:
                    connection.rollback()
                journal({"status": "blocked", "name": item.get("name"), "recipient": recipient, "touch_id": item.get("touch_id"), "reasons": reasons, "evidence": evidence})
                continue
            if args.preflight_only:
                connection.rollback()
                journal({"status": "preflight_passed", "name": item.get("name"), "recipient": recipient, "touch_id": item.get("touch_id"), "evidence": evidence})
                sent += 1
                continue
            delivery = send_email(
                sender,
                recipient=recipient,
                subject=str(item.get("subject") or ""),
                body=str(item.get("text") or ""),
                idempotency_key=f"v4-{item.get('touch_id')}",
                timeout=25,
            )
            provider_id = str(delivery.get("provider_message_id") or "")
            verified_ids = imap_search(client, sent_name, f"rfc822msgid:{provider_id}") if provider_id else []
            if len(verified_ids) != 1:
                connection.rollback()
                journal({"status": "send_uncertain", "name": item.get("name"), "recipient": recipient, "touch_id": item.get("touch_id"), "provider_message_id": provider_id})
                break
            record_sent(cursor, runtime, item, delivery, "native_email_user_authorized")
            connection.commit()
            sent += 1
            journal({"status": "sent", "name": item.get("name"), "recipient": recipient, "touch_id": item.get("touch_id"), "provider_message_id": provider_id, "sent_count": sent})
            if sent < args.limit and args.spacing_seconds > 0:
                time.sleep(args.spacing_seconds)
    finally:
        _close_imap(client)
        connection.rollback()
        connection.close()
    journal({"status": "complete", "sent": sent, "checked": checked, "limit": args.limit, "preflight_only": args.preflight_only})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
