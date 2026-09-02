#!/usr/bin/env python3
"""Record verified creator replies and bounces in the LocalOS creator catalog."""

from __future__ import annotations

import argparse
import html
import json
import re
import uuid
from datetime import datetime, timezone

from psycopg2.extras import Json

from database_manager import get_db_connection
from services.outreach_email_adapter import fetch_replies


CAMPAIGN_ID = "09da9779-cd9b-4722-84ea-51d0a57e8389"
SENDER_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
CLASSIFICATION_VERSION = "creator-taxonomy-v1+creator-reply-v1"

FORMAT_BY_PLATFORM = {
    "telegram": "telegram_post",
    "youtube": "video",
    "instagram": "visual_post",
    "threads": "short_text_post",
    "tiktok": "short_video",
    "vk": "social_post",
}

RESPONSES = {
    "annaclava69@gmail.com": {
        "outcome": "interested",
        "summary": "Автор живёт на две страны, сейчас на Сицилии; заинтересована в сотрудничестве и проводит в том числе видеоэкскурсии.",
        "content_geographies": ["Санкт-Петербург", "Сицилия"],
        "platforms": ["youtube"],
        "accepts_barter": True,
        "conditions": "Интересуют предложения для России и за рубежом; на момент ответа находится на Сицилии.",
        "characteristics": ["живёт на две страны", "видеоэкскурсии", "зарубежная география"],
    },
    "lizavetavimm@gmail.com": {
        "outcome": "interested",
        "summary": "Снимает в Санкт-Петербурге; публикует в YouTube, Instagram, Telegram и TikTok; формат сотрудничества интересен.",
        "content_geographies": ["Санкт-Петербург"],
        "platforms": ["youtube", "instagram", "telegram", "tiktok"],
        "accepts_barter": True,
        "conditions": "Готова рассматривать результативный бартер; конкретные условия ещё не согласованы.",
        "characteristics": ["мультиплатформенный автор", "снимает локальные места Санкт-Петербурга"],
    },
    "asherst07@gmail.com": {
        "outcome": "interested",
        "summary": "Интересуется сотрудничеством; чаще бывает в центральных районах Санкт-Петербурга; основная площадка YouTube, возможен Telegram; просит конкретику по услугам, результату и формату публикации.",
        "content_geographies": ["Санкт-Петербург", "Центральные районы Санкт-Петербурга"],
        "platforms": ["youtube", "telegram"],
        "accepts_barter": True,
        "conditions": "До согласия нужны конкретные услуга, ожидаемый результат и формат публикации.",
        "characteristics": ["основная площадка YouTube", "готова рассмотреть Telegram", "нужен подробный бриф"],
    },
    "elenaworldsport@gmail.com": {
        "outcome": "interested",
        "summary": "Готова рассматривать предложения; предпочитает YouTube и Instagram.",
        "content_geographies": [],
        "platforms": ["youtube", "instagram"],
        "accepts_barter": True,
        "conditions": "Рассматривает предложения; конкретные условия ещё не согласованы.",
        "characteristics": ["видеоконтент", "предпочитает YouTube и Instagram"],
    },
    "someundertalefan3@gmail.com": {
        "outcome": "not_interested",
        "summary": "Сообщил, что не занимается обзорами Петербурга; исходная квалификация была ошибочной.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": None,
        "conditions": "Не предлагать локальные обзоры: автор не работает в этом формате.",
        "characteristics": ["не занимается обзорами мест", "ошибочная квалификация"],
    },
    "viktorianposti@icloud.com": {
        "outcome": "not_interested",
        "summary": "Редко бывает в России; сотрудничество с российскими локальными бизнесами ей не подходит.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": None,
        "conditions": "Не предлагать российские локальные размещения без подтверждённой поездки.",
        "characteristics": ["редко бывает в России", "география не подходит текущей кампании"],
    },
    "arut.rapublic@gmail.com": {
        "outcome": "paid_only",
        "summary": "Бартер не рассматривает: предлагает только платное размещение из-за дорогого продакшна.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": False,
        "conditions": "Только платное сотрудничество; цену не сообщил.",
        "phone": "+7 911 228 22 65",
        "characteristics": ["дорогой продакшн", "платное размещение", "бартер не рассматривает"],
    },
    "jeykhoon2@gmail.com": {
        "outcome": "interested",
        "summary": "Сотрудничество интересно; чаще всего бывает в Санкт-Петербурге и Москве.",
        "content_geographies": ["Санкт-Петербург", "Москва"],
        "platforms": [],
        "accepts_barter": True,
        "conditions": "Готов рассматривать результативный бартер; площадку и детали нужно уточнить.",
        "characteristics": ["работает с Санкт-Петербургом и Москвой"],
    },
    "positivnajaja@gmail.com": {
        "outcome": "not_interested",
        "summary": "Отказался от предложения.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": False,
        "conditions": "Не предлагать повторно без нового запроса автора.",
        "characteristics": ["отказ от сотрудничества"],
    },
    "margomeow.meo@gmail.com": {
        "outcome": "interested",
        "summary": "Не против сотрудничества; находится в Твери.",
        "home_city": "Тверь",
        "content_geographies": ["Тверь"],
        "platforms": [],
        "accepts_barter": True,
        "conditions": "Готова рассматривать результативный бартер; площадку и детали нужно уточнить.",
        "characteristics": ["автор из Твери"],
    },
    "an.an.che27@yandex.ru": {
        "outcome": "question",
        "summary": "Просит сайт, соцсети и примеры сотрудничества с авторами, чтобы понять устройство проекта.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": None,
        "conditions": "До решения нужны сайт LocalOS, соцсети и примеры сотрудничества.",
        "characteristics": ["проверяет доверие к проекту", "нужны публичные материалы и кейсы"],
    },
    "vavilov88spb@gmail.com": {
        "outcome": "question",
        "summary": "Просит понятно и конкретно объяснить формат сотрудничества и предложение.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": None,
        "conditions": "Нужен конкретный оффер с обязанностями автора и бизнеса.",
        "characteristics": ["нужен подробный бриф"],
    },
    "hello@slovo.biz": {
        "outcome": "interested",
        "summary": "Готов попробовать; предлагает YouTube; работает по Санкт-Петербургу, любому району, Ленинградской области и Карелии.",
        "home_city": "Санкт-Петербург",
        "content_geographies": ["Санкт-Петербург", "Ленинградская область", "Карелия"],
        "platforms": ["youtube"],
        "accepts_barter": True,
        "conditions": "Готов попробовать сотрудничество; предлагает развиваемый YouTube-канал.",
        "characteristics": ["широкая локальная география", "развивает YouTube"],
    },
    "irodionova71@mail.ru": {
        "outcome": "interested",
        "summary": "Не против бартера; базовая география — Москва и близлежащие города по выходным; сейчас путешествует по Китаю; публикует в YouTube и VK.",
        "home_city": "Москва",
        "content_geographies": ["Москва", "Близлежащие города Москвы", "Китай"],
        "platforms": ["youtube", "vk"],
        "accepts_barter": True,
        "conditions": "Бартер интересен; поездки преимущественно по выходным.",
        "characteristics": ["путешествия", "поездки выходного дня", "YouTube и VK"],
    },
    "otvperm@gmail.com": {
        "outcome": "question",
        "summary": "Просит конкретно описать, что должен сделать автор YouTube и что предоставляет LocalOS или клиент.",
        "content_geographies": [],
        "platforms": ["youtube"],
        "accepts_barter": None,
        "conditions": "До решения нужен двусторонний конкретный оффер без общих формулировок.",
        "characteristics": ["YouTube-автор", "нужен предельно конкретный оффер"],
    },
    "pokidkofamily@gmail.com": {
        "outcome": "interested",
        "summary": "Подтвердил интерес к сотрудничеству.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": True,
        "conditions": "Готов рассматривать результативный бартер; географию и площадку нужно уточнить.",
        "characteristics": ["семейный и многодетный контент"],
    },
    "contactbrandyy@gmail.com": {
        "outcome": "interested",
        "summary": "Находится в Москве; интересуется сотрудничеством; предпочитает TikTok, YouTube и Instagram; просит детали по механике и видам мест или услуг.",
        "home_city": "Москва",
        "content_geographies": ["Москва"],
        "platforms": ["tiktok", "youtube", "instagram"],
        "accepts_barter": True,
        "conditions": "Нужны детали механики и примеры мест или услуг.",
        "characteristics": ["англоязычный ответ", "мультиплатформенный автор", "Москва"],
    },
    "tellmeaboutbusiness@gmail.com": {
        "outcome": "interested",
        "summary": "Готова рассматривать сотрудничество при условии, что предлагаются достойные места.",
        "content_geographies": ["Санкт-Петербург"],
        "platforms": [],
        "accepts_barter": True,
        "conditions": "Рассматривает только достойные, предварительно проверенные места.",
        "characteristics": ["обзоры локальных мест", "важно качество предлагаемого бизнеса"],
    },
    "olgafedorovna57@mail.ru": {
        "outcome": "question",
        "summary": "Канал посвящён Санкт-Петербургу; автор много снимает город и просит конкретику предложения.",
        "home_city": "Санкт-Петербург",
        "content_geographies": ["Санкт-Петербург"],
        "platforms": ["youtube"],
        "accepts_barter": None,
        "conditions": "Нужен конкретный оффер и объяснение интереса к автору.",
        "characteristics": ["много свободного времени", "городской видеоконтент", "канал о Санкт-Петербурге"],
    },
    "natalia-perova@mail.ru": {
        "outcome": "question",
        "summary": "Просит конкретно описать предложение; в подписи представилась как Наталья Перова.",
        "content_geographies": [],
        "platforms": [],
        "accepts_barter": None,
        "conditions": "Нужен конкретный оффер.",
        "contact_name": "Наталья Перова",
        "characteristics": ["имя в подписи отличается от названия профиля", "нужен конкретный оффер"],
    },
}


def dictionary(value) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def list_value(value) -> list:
    return list(value) if isinstance(value, list) else []


def clean_reply(value: str) -> str:
    text = html.unescape(value or "")
    text = re.split(r"<blockquote\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    markers = (
        "\nВт, ", "\nСр, ", "\nвт, ", "\nср, ", "\n> ",
        "\nOn Tue", "\nOn Wed", "\nвторник,", "\nсреда,",
        "\n--\nОтправлено", "\nLähetetty iPhonesta",
    )
    cut = len(text)
    for marker in markers:
        position = text.find(marker)
        if position >= 0:
            cut = min(cut, position)
    return re.sub(r"\n{3,}", "\n\n", text[:cut]).strip()[:4000]


def normalize_message_id(value: str) -> str:
    return str(value or "").strip().strip("<>").lower()


def merge_unique(existing: list, incoming: list) -> list:
    result = list(existing)
    seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in result}
    for item in incoming:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result


def geography_entries(names: list[str]) -> list[dict]:
    entries = []
    for name in names:
        kind = "region" if name in {"Ленинградская область", "Карелия"} else "area" if "район" in name.lower() else "city"
        entries.append({"kind": kind, "name": name, "confidence": 1.0, "basis": "creator_email_reply"})
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM outreach_sender_accounts WHERE id=%s", (SENDER_ID,))
        sender = dict(cursor.fetchone() or {})
        replies = fetch_replies(
            sender,
            since_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            limit=500,
            timeout=30,
        )
        cursor.execute(
            """
            SELECT collaboration.id collaboration_id, collaboration.creator_profile_id,
                   collaboration.campaign_candidate_id candidate_id,
                   collaboration.agreed_terms_json, profile.display_name,
                   collaboration.agreed_terms_json->'outreach'->>'recipient' recipient,
                   collaboration.agreed_terms_json->'outreach'->>'provider_message_id' provider_message_id
            FROM creator_collaborations collaboration
            JOIN creator_profiles profile ON profile.id=collaboration.creator_profile_id
            WHERE collaboration.campaign_id=%s
            """,
            (CAMPAIGN_ID,),
        )
        campaign_rows = [dict(row) for row in cursor.fetchall()]
        by_email = {str(row.get("recipient") or "").lower(): row for row in campaign_rows if row.get("recipient")}
        by_message = {
            normalize_message_id(str(row.get("provider_message_id") or "")): row
            for row in campaign_rows
            if row.get("provider_message_id")
        }
        human_messages: dict[str, list[dict]] = {}
        bounce_messages: dict[str, list[dict]] = {}
        for reply in replies:
            from_email = str(reply.get("from_email") or "").strip().lower()
            is_bounce = "mailer-daemon" in from_email or "delivery status notification" in str(reply.get("subject") or "").lower()
            if not is_bounce and from_email in RESPONSES and from_email in by_email:
                human_messages.setdefault(from_email, []).append(reply)
                continue
            if not is_bounce:
                continue
            references = " ".join([str(reply.get("in_reply_to") or ""), str(reply.get("references") or "")])
            matched_row = None
            for token in re.findall(r"<([^>]+)>", references):
                matched_row = by_message.get(normalize_message_id(token))
                if matched_row:
                    break
            if matched_row:
                bounce_messages.setdefault(str(matched_row["recipient"]).lower(), []).append(reply)

        planned = []
        for email_address, response in RESPONSES.items():
            row = by_email.get(email_address)
            messages = human_messages.get(email_address, [])
            if not row or not messages:
                continue
            messages.sort(key=lambda item: item.get("occurred_at") or datetime.min.replace(tzinfo=timezone.utc))
            latest_at = messages[-1].get("occurred_at") or datetime.now(timezone.utc)
            reply_items = [
                {
                    "provider_event_id": str(message.get("provider_event_id") or ""),
                    "message_id": str(message.get("message_id") or ""),
                    "received_at": str(message.get("occurred_at") or ""),
                    "subject": str(message.get("subject") or ""),
                    "text": clean_reply(str(message.get("body") or "")),
                }
                for message in messages
            ]
            outcome = str(response["outcome"])
            status = "declined" if outcome in {"not_interested", "paid_only"} else "replied"
            planned.append({"creator": row["display_name"], "email": email_address, "outcome": outcome, "status": status})
            if not options.apply:
                continue

            profile_id = str(row["creator_profile_id"])
            candidate_id = str(row["candidate_id"])
            collaboration_id = str(row["collaboration_id"])
            terms = dictionary(row.get("agreed_terms_json"))
            terms["response"] = {
                "source": "creator_email_reply",
                "outcome": outcome,
                "summary": response["summary"],
                "contact_email": email_address,
                "contact_name": response.get("contact_name"),
                "phone": response.get("phone"),
                "content_geographies": response.get("content_geographies", []),
                "platforms": response.get("platforms", []),
                "accepts_barter": response.get("accepts_barter"),
                "conditions": response.get("conditions"),
                "characteristics": response.get("characteristics", []),
                "received_at": str(latest_at),
                "messages": reply_items,
            }
            cursor.execute(
                "UPDATE creator_collaborations SET status=%s,agreed_terms_json=%s,updated_at=NOW() WHERE id=%s",
                (status, Json(terms), collaboration_id),
            )
            cursor.execute(
                "UPDATE creator_campaign_candidates SET status=%s,selection_reason=%s,updated_at=NOW() WHERE id=%s",
                (status, response["summary"], candidate_id),
            )

            cursor.execute("SELECT metadata_json,primary_city,primary_area FROM creator_profiles WHERE id=%s", (profile_id,))
            profile = dict(cursor.fetchone() or {})
            profile_metadata = dictionary(profile.get("metadata_json"))
            profile_metadata["creator_reply_profile"] = {
                "contact": {
                    "type": "email", "value": email_address, "status": "confirmed_by_reply",
                    "confirmed_at": str(latest_at), "phone": response.get("phone"),
                    "contact_name": response.get("contact_name"),
                },
                "outcome": outcome,
                "summary": response["summary"],
                "content_geographies": response.get("content_geographies", []),
                "platforms": response.get("platforms", []),
                "conditions": response.get("conditions"),
                "characteristics": response.get("characteristics", []),
                "source": "creator_email_reply",
                "updated_at": str(latest_at),
            }
            cursor.execute(
                """
                UPDATE creator_profiles SET
                    primary_city=COALESCE(%s,primary_city),
                    verification_status=CASE WHEN verification_status='candidate' THEN 'observed' ELSE verification_status END,
                    metadata_json=%s,updated_at=NOW()
                WHERE id=%s
                """,
                (response.get("home_city"), Json(profile_metadata), profile_id),
            )

            cursor.execute(
                """
                INSERT INTO creator_profile_taxonomy (
                    creator_profile_id,classification_version,classification_status
                ) VALUES (%s,%s,'needs_review')
                ON CONFLICT (creator_profile_id) DO NOTHING
                """,
                (profile_id, CLASSIFICATION_VERSION),
            )
            cursor.execute("SELECT * FROM creator_profile_taxonomy WHERE creator_profile_id=%s", (profile_id,))
            taxonomy = dict(cursor.fetchone() or {})
            current_geographies = list_value(taxonomy.get("content_geographies_json"))
            current_formats = list_value(taxonomy.get("confirmed_formats_json"))
            current_confidence = dictionary(taxonomy.get("confidence_json"))
            current_evidence = list_value(taxonomy.get("evidence_json"))
            formats = [FORMAT_BY_PLATFORM[item] for item in response.get("platforms", []) if item in FORMAT_BY_PLATFORM]
            evidence_entry = {
                "source": "creator_email_reply",
                "contact": email_address,
                "observed": response["summary"],
                "confidence": 1.0,
                "observed_at": str(latest_at),
                "fields": ["contact", "geography", "platforms", "conditions", "interest"],
            }
            current_confidence.update({"contact": 1.0, "creator_reply": 1.0})
            if response.get("home_city"):
                current_confidence["home_city"] = 1.0
            if response.get("content_geographies"):
                current_confidence["content_geography"] = 1.0
            if response.get("platforms"):
                current_confidence["confirmed_formats"] = 1.0
            cursor.execute(
                """
                UPDATE creator_profile_taxonomy SET
                    home_city=COALESCE(%s,home_city),
                    content_geographies_json=%s,
                    confirmed_formats_json=%s,
                    confidence_json=%s,evidence_json=%s,
                    classification_version=%s,classifed_at=classified_at,
                    updated_at=NOW()
                WHERE creator_profile_id=%s
                """.replace("classifed_at=classified_at,", "classified_at=NOW(),"),
                (
                    response.get("home_city"),
                    Json(merge_unique(current_geographies, geography_entries(response.get("content_geographies", [])))),
                    Json(merge_unique(current_formats, formats)),
                    Json(current_confidence), Json(merge_unique(current_evidence, [evidence_entry])),
                    CLASSIFICATION_VERSION, profile_id,
                ),
            )

            cursor.execute("SELECT * FROM creator_commercial_profiles WHERE creator_profile_id=%s", (profile_id,))
            commercial = dict(cursor.fetchone() or {})
            commercial_formats = merge_unique(list_value(commercial.get("formats_json")), formats)
            commercial_metadata = dictionary(commercial.get("metadata_json"))
            commercial_metadata["creator_reply"] = {
                "outcome": outcome,
                "self_reported_platforms": response.get("platforms", []),
                "conditions": response.get("conditions"),
                "confirmed_at": str(latest_at),
            }
            cursor.execute(
                """
                INSERT INTO creator_commercial_profiles (
                    id,creator_profile_id,formats_json,accepts_barter,preferred_contact,
                    availability_text,confirmation_status,confirmed_at,metadata_json
                ) VALUES (%s,%s,%s,%s,%s,%s,'creator_confirmed',%s,%s)
                ON CONFLICT (creator_profile_id) DO UPDATE SET
                    formats_json=EXCLUDED.formats_json,
                    accepts_barter=COALESCE(EXCLUDED.accepts_barter,creator_commercial_profiles.accepts_barter),
                    preferred_contact=EXCLUDED.preferred_contact,
                    availability_text=EXCLUDED.availability_text,
                    confirmation_status='creator_confirmed',confirmed_at=EXCLUDED.confirmed_at,
                    metadata_json=EXCLUDED.metadata_json,updated_at=NOW()
                """,
                (
                    str(uuid.uuid4()), profile_id, Json(commercial_formats), response.get("accepts_barter"),
                    email_address, response.get("conditions"), latest_at, Json(commercial_metadata),
                ),
            )
            for message, reply_item in zip(messages, reply_items):
                provider_message_id = str(message.get("message_id") or "")
                cursor.execute(
                    "SELECT id FROM creator_evidence WHERE creator_profile_id=%s AND evidence_type='creator_reply' AND metadata_json->>'provider_message_id'=%s",
                    (profile_id, provider_message_id),
                )
                if cursor.fetchone():
                    continue
                cursor.execute(
                    """
                    INSERT INTO creator_evidence (
                        id,creator_profile_id,evidence_type,summary_text,confidence,observed_at,metadata_json
                    ) VALUES (%s,%s,'creator_reply',%s,1,%s,%s)
                    """,
                    (
                        str(uuid.uuid4()), profile_id, reply_item["text"] or response["summary"],
                        message.get("occurred_at"), Json({
                            "provider": "gmail", "provider_message_id": provider_message_id,
                            "provider_event_id": message.get("provider_event_id"), "contact_email": email_address,
                            "outcome": outcome, "campaign_id": CAMPAIGN_ID,
                        }),
                    ),
                )

        bounced = []
        for email_address, messages in bounce_messages.items():
            row = by_email[email_address]
            messages.sort(key=lambda item: item.get("occurred_at") or datetime.min.replace(tzinfo=timezone.utc))
            message = messages[-1]
            bounce_text = clean_reply(str(message.get("body") or ""))
            bounced.append({"creator": row["display_name"], "email": email_address, "status": "failed"})
            if not options.apply:
                continue
            profile_id = str(row["creator_profile_id"])
            candidate_id = str(row["candidate_id"])
            collaboration_id = str(row["collaboration_id"])
            terms = dictionary(row.get("agreed_terms_json"))
            terms["delivery_failure"] = {
                "source": "gmail_bounce", "email": email_address,
                "reason": bounce_text, "received_at": str(message.get("occurred_at") or ""),
                "provider_message_id": str(message.get("message_id") or ""),
            }
            cursor.execute("UPDATE creator_collaborations SET status='stopped',agreed_terms_json=%s,updated_at=NOW() WHERE id=%s", (Json(terms), collaboration_id))
            cursor.execute("UPDATE creator_campaign_candidates SET status='removed',selection_reason=%s,updated_at=NOW() WHERE id=%s", ("Email недействителен: " + bounce_text[:300], candidate_id))
            cursor.execute("SELECT metadata_json FROM creator_profiles WHERE id=%s", (profile_id,))
            profile_metadata = dictionary((cursor.fetchone() or {}).get("metadata_json"))
            profile_metadata["invalid_contact"] = {
                "type": "email", "value": email_address, "status": "bounced",
                "reason": bounce_text, "observed_at": str(message.get("occurred_at") or ""),
            }
            cursor.execute("UPDATE creator_profiles SET metadata_json=%s,updated_at=NOW() WHERE id=%s", (Json(profile_metadata), profile_id))
            cursor.execute(
                """
                UPDATE creator_commercial_profiles SET
                    preferred_contact=CASE WHEN LOWER(preferred_contact)=LOWER(%s) THEN NULL ELSE preferred_contact END,
                    confirmation_status='expired',
                    metadata_json=metadata_json || %s,updated_at=NOW()
                WHERE creator_profile_id=%s
                """,
                (email_address, Json({"email_delivery_failure": {"email": email_address, "reason": bounce_text}}), profile_id),
            )
            provider_message_id = str(message.get("message_id") or "")
            cursor.execute(
                "SELECT id FROM creator_evidence WHERE creator_profile_id=%s AND evidence_type='email_bounce' AND metadata_json->>'provider_message_id'=%s",
                (profile_id, provider_message_id),
            )
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO creator_evidence (
                        id,creator_profile_id,evidence_type,summary_text,confidence,observed_at,metadata_json
                    ) VALUES (%s,%s,'email_bounce',%s,1,%s,%s)
                    """,
                    (
                        str(uuid.uuid4()), profile_id, bounce_text,
                        message.get("occurred_at"), Json({
                            "provider": "gmail", "provider_message_id": provider_message_id,
                            "contact_email": email_address, "campaign_id": CAMPAIGN_ID,
                        }),
                    ),
                )

        result = {
            "mode": "apply" if options.apply else "dry_run",
            "human_profiles": len(planned),
            "bounced_profiles": len(bounced),
            "outcomes": {
                outcome: len([item for item in planned if item["outcome"] == outcome])
                for outcome in sorted({item["outcome"] for item in planned})
            },
            "profiles": planned,
            "bounces": bounced,
        }
        if options.apply:
            connection.commit()
        else:
            connection.rollback()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
