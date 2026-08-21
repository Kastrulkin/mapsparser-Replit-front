#!/usr/bin/env python3
"""Build a reviewed, unsent 20-lead follow-up batch from canonical v4 first touches."""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import RealDictCursor

sys.path.insert(0, "/app/debug_data")

from database_manager import get_db_connection
from dispatch_v4_email_queue_20260820 import (
    EXPECTED_CANONICAL_SHA,
    SENDER_ID,
    gmail_mailboxes,
    imap_search,
    normalized_email,
    read_message,
    sender_account,
)
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config
from services.outreach_email_reply_service import sync_email_replies


MANIFEST_PATH = Path("/app/debug_data/localos-1000-safe-final-manifest-v4-20260814.json")
OUTPUT_PATH = Path("/app/debug_data/localos-followup-batch-01-review-20260820.json")
FIRST_TOUCH_IDS = [
    "278fbd9b-099e-4f4c-92d8-be0940d9b6a6",
    "377b5a10-6f94-46d7-a272-82be2935ba69",
    "91768999-9b0e-491e-971b-a254ae6004e1",
    "5a44990d-ddb6-4bd3-98f0-8ff037f7ab09",
    "2eaa0456-53da-44d2-ac50-39d066fe2ee0",
    "904c7c7d-c4b5-4c9c-b55e-e85982312ad9",
    "036855ec-c6cb-4614-9860-fbd568b44835",
    "b45c92d1-d573-4c54-a70b-e10446d36e89",
    "e4d01c5e-cde9-40ce-b2b1-277979a58378",
    "dddb13f5-f975-4880-808a-1880b6907405",
    "cfcb52e9-ed92-4c81-8d6e-d28431e83a73",
    "3faf5e4a-65e8-4bbd-b6a1-76dff8644a2c",
    "81d05112-c7ab-4652-baf6-cf9bfd06d17a",
    "1f18629e-4b8c-460d-8f73-4cff7a027a59",
    "c120ed60-8264-4cfa-ad27-d78fa2f1b175",
    "fd4d61a6-868d-4223-8da7-efc13fb177d9",
    "8a44c65a-1f60-4f29-bfee-1189348ae150",
    "acbe68af-2d6b-4363-a6d3-fcdcaa2408e4",
    "24dd0497-df0f-48c5-998d-83f9ae5db693",
    "42632dd1-bfff-4c73-b226-034c6948171c",
]
PLANNED_SEND_AT = datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc)
MIN_FOLLOWUP_INTERVAL_HOURS = 72


def load_first_rows():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "localos_1000_safe_final_manifest_v4":
        raise RuntimeError("manifest_v4_required")
    if manifest.get("canonical_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("manifest_canonical_sha_mismatch")
    rows = {str(row.get("touch_id") or ""): row for row in manifest.get("touches") or []}
    selected = [rows[touch_id] for touch_id in FIRST_TOUCH_IDS]
    if len(selected) != len(FIRST_TOUCH_IDS):
        raise RuntimeError("batch_size_mismatch")
    for row in selected:
        if row.get("channel") != "email" or int(row.get("sequence_index") or 0) != 0:
            raise RuntimeError(f"first_email_required:{row.get('touch_id')}")
    return selected


def fetch_runtime(cursor, row):
    cursor.execute(
        """
        SELECT t.status, t.delivery_json, c.id campaign_id, c.lead_id, c.workstream_id,
               l.name lead_name, l.source_url lead_source_url, l.source_external_id,
               cp.normalized_value recipient, cp.verification_status, cp.source_url contact_source_url
        FROM outreach_campaign_touches t
        JOIN outreach_campaigns c ON c.id=t.campaign_id
        JOIN prospectingleads l ON l.id=c.lead_id
        LEFT JOIN lead_contact_points cp ON cp.id=t.contact_point_id
        WHERE t.id=%s AND c.id=%s AND c.lead_id=%s
        """,
        (row.get("touch_id"), row.get("campaign_id"), row.get("lead_id")),
    )
    return dict(cursor.fetchone() or {})


def database_safety(cursor, row, runtime):
    lead_id = runtime.get("lead_id")
    recipient = normalized_email(row.get("recipient"))
    cursor.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM outreach_suppressions WHERE lead_id=%s AND (expires_at IS NULL OR expires_at>NOW())) suppressions,
          (SELECT COUNT(*) FROM outreach_inbound_events WHERE lead_id=%s AND (COALESCE(is_human,FALSE) OR COALESCE(stops_campaign,FALSE))) inbound,
          (SELECT COUNT(*) FROM outreachreactions WHERE lead_id=%s) reactions,
          (SELECT COUNT(*) FROM outreach_sender_health_events h JOIN outreach_campaigns c ON c.id=h.campaign_id WHERE c.lead_id=%s AND h.event_type='delivery_failed') delivery_failures,
          (SELECT COUNT(DISTINCT lead_id) FROM lead_contact_points WHERE contact_type='email' AND lower(normalized_value)=lower(%s)) email_leads,
          (SELECT COUNT(*) FROM outreach_campaign_touches t JOIN outreach_campaigns c ON c.id=t.campaign_id WHERE c.lead_id=%s AND t.sequence_index>0 AND t.channel='email' AND t.status NOT IN ('cancelled')) later_email_touches
        """,
        (lead_id, lead_id, lead_id, lead_id, recipient, lead_id),
    )
    evidence = dict(cursor.fetchone() or {})
    reasons = []
    for key in ("suppressions", "inbound", "reactions", "delivery_failures", "later_email_touches"):
        if int(evidence.get(key) or 0) > 0:
            reasons.append(key)
    if int(evidence.get("email_leads") or 0) != 1:
        reasons.append("duplicate_email_across_leads")
    if runtime.get("status") not in {"sent", "manual_sent", "delivered"}:
        reasons.append("first_touch_not_sent_in_database")
    if normalized_email(runtime.get("recipient")) != recipient:
        reasons.append("runtime_recipient_mismatch")
    if runtime.get("verification_status") not in {"confirmed_source", "valid_format", "found"}:
        reasons.append("recipient_not_verified")
    return sorted(set(reasons)), evidence


def gmail_safety(client, all_name, sent_name, row):
    recipient = normalized_email(row.get("recipient"))
    sent_ids = imap_search(client, sent_name, f"to:{recipient}")
    reply_ids = imap_search(client, all_name, f"from:{recipient}")
    bounce_ids = imap_search(client, all_name, f"from:mailer-daemon@googlemail.com {recipient}")
    bounce_ids += imap_search(client, all_name, f"from:mailer-daemon@gmail.com {recipient}")
    messages = [read_message(client, sent_name, uid) for uid in sent_ids[-20:]]
    exact = [
        message
        for message in messages
        if message.get("subject") == str(row.get("subject") or "").strip()
        and message.get("body") == str(row.get("text") or "").strip()
    ]
    unique_bodies = {str(message.get("body") or "").strip() for message in messages if message.get("body")}
    first_sent_at = None
    interval_hours = None
    if len(exact) == 1 and exact[0].get("date"):
        try:
            first_sent_at = parsedate_to_datetime(exact[0]["date"])
            if first_sent_at.tzinfo is None:
                first_sent_at = first_sent_at.replace(tzinfo=timezone.utc)
            first_sent_at = first_sent_at.astimezone(timezone.utc)
            interval_hours = (PLANNED_SEND_AT - first_sent_at).total_seconds() / 3600
        except Exception:
            first_sent_at = None
    reasons = []
    if len(exact) != 1:
        reasons.append("gmail_first_exact_missing" if not exact else "gmail_first_exact_duplicate")
    if len(unique_bodies) != 1:
        reasons.append("gmail_unexpected_sent_sequence")
    if reply_ids:
        reasons.append("gmail_reply_exists")
    if bounce_ids:
        reasons.append("gmail_bounce_exists")
    if first_sent_at is None:
        reasons.append("gmail_first_sent_date_missing")
    elif interval_hours < MIN_FOLLOWUP_INTERVAL_HOURS:
        reasons.append("gmail_followup_interval_under_72h")
    return sorted(set(reasons)), {
        "sent_count": len(sent_ids),
        "unique_body_count": len(unique_bodies),
        "first_exact_count": len(exact),
        "reply_count": len(reply_ids),
        "bounce_count": len(set(bounce_ids)),
        "first_sent_at": first_sent_at.isoformat() if first_sent_at else None,
        "planned_send_at": PLANNED_SEND_AT.isoformat(),
        "interval_hours": round(interval_hours, 2) if interval_hours is not None else None,
        "minimum_interval_hours": MIN_FOLLOWUP_INTERVAL_HOURS,
    }


def public_item(url):
    response = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "Mozilla/5.0 (compatible; LocalOSFollowupResearch/1.0; +https://localos.pro)"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    node = soup.find("script", {"type": "application/json"})
    if not node or not node.string:
        raise RuntimeError("public_map_payload_missing")
    return json.loads(node.string)["stack"][0]["results"]["items"][0]


def public_research(row, runtime):
    reasons = []
    source_url = str((row.get("message_brief_json") or {}).get("source_url") or "")
    if "yandex." not in source_url:
        source_url = str(runtime.get("lead_source_url") or "")
    if "yandex." not in source_url:
        return ["current_map_source_missing"], {"source_url": source_url}
    try:
        item = public_item(source_url)
        rating_data = item.get("ratingData") or {}
        org_id = str(item.get("id") or item.get("businessId") or "")
        review_count = int(rating_data.get("reviewCount") or item.get("reviewCount") or 0)
        rating = float(rating_data.get("ratingValue") or item.get("rating") or 0)
        news_count = int((item.get("eventsPreviews") or {}).get("count") or len(item.get("mobilePosts") or []))
        price_url_match = re.search(r"^(https?://[^/]+/maps/org/[^/]+/\d+)", source_url)
        price_url = f"{price_url_match.group(1)}/prices/" if price_url_match else source_url
        price_item = public_item(price_url)
        categories = (price_item.get("fullObjects") or {}).get("categories") or []
        services = [service for category in categories for service in category.get("categoryItems") or []]
        priced = [service for service in services if str(service.get("price") or "").strip()]
        evidence = {
            "source_url": source_url,
            "price_source_url": price_url,
            "title": item.get("title") or item.get("name"),
            "org_id": org_id,
            "review_count": review_count,
            "rating": rating,
            "news_count": news_count,
            "service_count": len(services),
            "priced_service_count": len(priced),
            "categories": [category.get("name") for category in item.get("categories") or []],
            "researched_at": datetime.now(timezone.utc).isoformat(),
        }
        expected_org = str(runtime.get("source_external_id") or "")
        if expected_org and org_id and expected_org != org_id:
            reasons.append("map_org_mismatch")
        return sorted(set(reasons)), evidence
    except Exception as exc:
        return ["current_map_source_unavailable"], {"source_url": source_url, "error": f"{type(exc).__name__}:{exc}"[:300]}


def contact_check(row):
    recipient = normalized_email(row.get("recipient"))
    url = str(row.get("contact_source_url") or "")
    if not url:
        return ["contact_source_missing"], {"source_url": url}
    try:
        response = requests.get(
            url,
            timeout=20,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LocalOSContactAudit/1.0; +https://localos.pro)"},
        )
        body = html.unescape(response.text).lower()
        compact = re.sub(r"\s+", "", body)
        visible = recipient in body or recipient.replace("@", "[at]") in compact or recipient.replace("@", "%40") in body
        reasons = []
        if response.status_code >= 400:
            reasons.append("contact_source_unavailable")
        elif not visible:
            reasons.append("recipient_not_visible_on_current_source")
        return reasons, {"source_url": url, "status": response.status_code, "final_url": response.url, "recipient_visible": visible}
    except Exception as exc:
        return ["contact_source_unavailable"], {"source_url": url, "error": f"{type(exc).__name__}:{exc}"[:300]}


def counted_word(value, one, few, many):
    value = abs(int(value))
    if value % 100 in {11, 12, 13, 14}:
        return many
    if value % 10 == 1:
        return one
    if value % 10 in {2, 3, 4}:
        return few
    return many


def draft_followup(name, first_angle, evidence):
    public_name = str(evidence.get("title") or name).strip()
    categories = " ".join(str(value or "") for value in evidence.get("categories") or []).lower()
    medical = any(value in categories for value in ("medical", "clinic", "dental", "cosmetology", "клиник", "медиц"))
    person = "пациенту" if medical else "клиенту"
    services = int(evidence.get("service_count") or 0)
    priced = int(evidence.get("priced_service_count") or 0)
    reviews = int(evidence.get("review_count") or 0)
    news = int(evidence.get("news_count") or 0)
    if services >= 15 and first_angle not in {"services", "service_prices"}:
        price_phrase = ", у каждой указана цена" if priced == services else f", цена указана у {priced}"
        service_word = counted_word(services, "услуга", "услуги", "услуг")
        observation = f"В карточке {public_name} на Яндекс Картах сейчас опубликовано {services} {service_word}{price_phrase}."
        hypothesis = f"При таком объёме {person} может быть непросто быстро сравнить направления. Это гипотеза, которую можно проверить по структуре меню."
        offer = "LocalOS может подготовить более короткую структуру разделов и названий, не меняя исходный прайс."
        cta = "Показать пример структуры на 5-7 разделов?"
        angle = "service_menu_structure"
    elif news == 0 and first_angle not in {"signal", "missing_map_news"}:
        observation = f"В карточке {public_name} на Яндекс Картах сейчас нет новостей."
        hypothesis = f"Без публикаций {person} сложнее увидеть актуальные направления и повод обратиться. Это гипотеза, а не вывод о вашей работе."
        review_word = counted_word(reviews, "отзыва", "отзывов", "отзывов")
        offer = f"LocalOS может собрать темы из услуг и {reviews} {review_word} в карточке и подготовить три коротких текста для ручной публикации."
        cta = "Показать три темы?"
        angle = "missing_map_news"
    elif first_angle not in {"reviews_content"} and reviews >= 10:
        review_word = counted_word(reviews, "отзыв", "отзыва", "отзывов")
        observation = f"В карточке {public_name} на Яндекс Картах сейчас опубликовано {reviews} {review_word}."
        hypothesis = "В таком объёме уже могут повторяться вопросы и темы, полезные для карточки и сайта. Это можно проверить по текстам отзывов."
        offer = "LocalOS может выделить повторяющиеся темы и превратить их в короткий план материалов."
        cta = "Показать три повторяющиеся темы?"
        angle = "reviews_themes"
    else:
        return None
    subject = f"{public_name} - карточка на Яндекс Картах"
    text = f"Здравствуйте!\n\n{observation}\n\n{hypothesis}\n\n{offer}\n\n{cta}\n\n--\nАлександр\nоснователь LocalOS"
    return {
        "angle": angle,
        "subject": subject,
        "text": text,
        "observation": observation,
        "problem_hypothesis": hypothesis,
        "offer_bridge": offer,
        "cta": cta,
    }


def main():
    rows = load_first_rows()
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    sender = sender_account(cursor)
    connection.rollback()
    reply_sync = sync_email_replies(sender_limit=1, per_sender_limit=500, sender_account_id=SENDER_ID)
    if int(reply_sync.get("failed") or 0) > 0:
        raise RuntimeError("reply_sync_failed")
    client = _imap_connection(load_mailbox_config(sender), timeout=25)
    all_name, sent_name = gmail_mailboxes(client)
    results = []
    try:
        for row in rows:
            runtime = fetch_runtime(cursor, row)
            reasons = []
            evidence = {"first_touch_id": row.get("touch_id")}
            if not runtime:
                reasons.append("runtime_first_touch_missing")
            else:
                db_reasons, db_evidence = database_safety(cursor, row, runtime)
                reasons.extend(db_reasons)
                evidence["database"] = db_evidence
            gmail_reasons, gmail_evidence = gmail_safety(client, all_name, sent_name, row)
            reasons.extend(gmail_reasons)
            evidence["gmail"] = gmail_evidence
            contact_reasons, contact_evidence = contact_check(row)
            reasons.extend(contact_reasons)
            evidence["contact"] = contact_evidence
            research_reasons, research = public_research(row, runtime)
            reasons.extend(research_reasons)
            evidence["research"] = research
            categories_text = " ".join(str(value or "") for value in research.get("categories") or []).lower()
            if "housing complex" in categories_text or "жилой комплекс" in categories_text:
                reasons.append("category_out_of_scope")
            draft = draft_followup(str(row.get("name") or ""), str(row.get("angle_type") or ""), research) if not research_reasons else None
            if not draft:
                reasons.append("no_distinct_supported_second_angle")
            reasons = sorted(set(reasons))
            word_count = len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*", str((draft or {}).get("text") or "")))
            if draft and (word_count > 120 or str(draft.get("text") or "").count("?") != 1):
                reasons.append("draft_guardrail_failed")
            status = "ready_for_user_approval" if not reasons else "blocked"
            result = {
                "name": row.get("name"),
                "lead_id": row.get("lead_id"),
                "campaign_id": row.get("campaign_id"),
                "first_touch_id": row.get("touch_id"),
                "proposed_touch_id": str(uuid.uuid4()),
                "sequence_index": 1,
                "channel": "email",
                "recipient": row.get("recipient"),
                "contact_source_url": row.get("contact_source_url"),
                "first_angle": row.get("angle_type"),
                "status": status,
                "reasons": reasons,
                "evidence": evidence,
                "draft": draft,
                "quality": {
                    "score": 17 if status == "ready_for_user_approval" else 0,
                    "max_score": 18,
                    "verdict": "approve" if status == "ready_for_user_approval" else "reject",
                    "reason_codes": [] if status == "ready_for_user_approval" else reasons,
                    "risk": "Current official-page fact; no dated timing trigger." if status == "ready_for_user_approval" else "Blocked by preflight.",
                    "word_count": word_count,
                },
            }
            results.append(result)
            connection.rollback()
    finally:
        _close_imap(client)
        connection.rollback()
        connection.close()
    payload = {
        "schema_version": "localos_followup_batch_review_v1",
        "base_manifest_canonical_sha256": EXPECTED_CANONICAL_SHA,
        "batch_id": "followup-batch-01-20260820",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "planned_send_date": "2026-08-21",
        "state": "draft_for_user_approval",
        "delivery_authorized": False,
        "queued": False,
        "sent": False,
        "input_count": len(results),
        "ready_count": sum(item["status"] == "ready_for_user_approval" for item in results),
        "blocked_count": sum(item["status"] == "blocked" for item in results),
        "items": results,
    }
    payload["review_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_PATH), "input": payload["input_count"], "ready": payload["ready_count"], "blocked": payload["blocked_count"], "review_sha256": payload["review_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
