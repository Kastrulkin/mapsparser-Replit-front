#!/usr/bin/env python3
"""Prepare one human-reviewed first partner touch without queueing or sending it."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate_path in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate_path not in sys.path:
        sys.path.insert(0, candidate_path)

from services.outreach_campaign_service import _quality_gate  # noqa: E402
from services.outreach_personalization_ai import REVIEW_PROMPT_VERSION  # noqa: E402
from services.outreach_safety_service import recipient_key, strategy_fingerprint  # noqa: E402
from services.sales_room_review_service import (  # noqa: E402
    create_sales_room_proposal_version,
    ensure_sales_room_proposal_version,
)


VESELAYA_ID = "cb674174-8b3d-41a3-8277-525c849935f2"
ORGANIKA_ID = "360b90ef-cf2b-4eb4-acd4-a8524e4600ae"
RULES_VERSION = "partner_first_touch_human_v1"
GENERATION_SOURCE = "manual_outreach_review"
TERMINAL = {
    "replied", "converted", "closed_lost", "not_relevant", "suppressed",
    "unsubscribed", "hard_no", "closed", "won", "lost", "archived",
    "contacted", "waiting_reply", "postponed",
}
INVALID_CONTACT_STATUSES = {"invalid", "stale"}


CONTACT_ENRICHMENTS: dict[tuple[str, str], list[dict[str, str]]] = {
    (VESELAYA_ID, "B&C for baby"): [{
        "contact_type": "other",
        "value": "Личное обращение в магазин, Дивный город, 3 этаж",
        "source_url": "https://trk-canyon.ru/renters/shops?tags=children",
        "source_type": "official_venue_directory",
    }],
    (VESELAYA_ID, "B&C junior"): [{
        "contact_type": "other",
        "value": "Личное обращение в магазин, Дивный город, 3 этаж",
        "source_url": "https://trk-canyon.ru/renters/shops/alphabet?floor=3&tags=clothes",
        "source_type": "official_venue_directory",
    }],
    (VESELAYA_ID, "ЖК Северная Долина"): [
        {
            "contact_type": "email",
            "value": "info@operation-gs.ru",
            "source_url": "https://operation-gs.ru/contact",
            "source_type": "official_website",
        },
        {
            "contact_type": "phone",
            "value": "+7 (812) 677-23-30",
            "source_url": "https://operation-gs.ru/contact",
            "source_type": "official_website",
        },
    ],
    (ORGANIKA_ID, "Level UP"): [
        {
            "contact_type": "email",
            "value": "info@1basis.ru",
            "source_url": "https://bclevelup.ru/",
            "source_type": "official_website",
        },
        {
            "contact_type": "phone",
            "value": "+7 (812) 336-87-33",
            "source_url": "https://bclevelup.ru/",
            "source_type": "official_website",
        },
    ],
    (ORGANIKA_ID, "MedSwiss"): [
        {
            "contact_type": "email",
            "value": "info@medswiss-spb.ru",
            "source_url": "https://medswiss-spb.ru/contacts/",
            "source_type": "official_website",
        },
        {
            "contact_type": "phone",
            "value": "+7 (812) 318-03-03",
            "source_url": "https://medswiss-spb.ru/contacts/",
            "source_type": "official_website",
        },
    ],
    (ORGANIKA_ID, "Театр «Кот Вильям»"): [
        {
            "contact_type": "email",
            "value": "info@kotwilliam.ru",
            "source_url": "https://kotwilliam.ru/contact",
            "source_type": "official_website",
        },
        {
            "contact_type": "phone",
            "value": "+7 (812) 748-27-45",
            "source_url": "https://kotwilliam.ru/contact",
            "source_type": "official_website",
        },
        {
            "contact_type": "website_form",
            "value": "https://kotwilliam.ru/contact",
            "source_url": "https://kotwilliam.ru/contact",
            "source_type": "official_website",
        },
    ],
    (ORGANIKA_ID, "ТРК «Атмосфера»"): [
        {
            "contact_type": "phone",
            "value": "+7 (812) 459-95-12",
            "source_url": "https://www.trkatmosfera.ru/contacts/",
            "source_type": "official_website",
        },
        {
            "contact_type": "website_form",
            "value": "https://www.trkatmosfera.ru/contacts/",
            "source_url": "https://www.trkatmosfera.ru/contacts/",
            "source_type": "official_website",
        },
    ],
    (ORGANIKA_ID, "РЕСО-Гарантия"): [{
        "contact_type": "website_form",
        "value": "https://reso.ru/feedback/",
        "source_url": "https://reso.ru/feedback/",
        "source_type": "official_website",
    }],
}


NOT_RELEVANT: dict[str, dict[str, str]] = {
    VESELAYA_ID: {
        "BONITA": "Не найден в актуальном каталоге арендаторов Гранд Каньона",
        "Little France": "Не найден в актуальном каталоге арендаторов Гранд Каньона",
    },
    ORGANIKA_ID: {
        "Borneo Beauty": "Прямой beauty-конкурент без убедительной партнёрской связки",
        "Miller Center": "Бывший объект; по актуальным данным корпус работает как отдельный БЦ Level UP",
        "Miller Center: медицинские арендаторы": "Составная запись, а не самостоятельный получатель",
        "Naomi": "Не подтверждена самостоятельная организация и получатель",
        "Newfit": "Актуальный официальный сайт указывает другую локацию",
        "Watsons": "Не подтверждена действующая точка в локации",
        "Wonderfit": "Актуальные официальные адреса находятся в других районах",
        "АКБ Констанс-Банк": "Не подтверждена действующая организация в локации",
        "Детский развлекательный автомат": "Объект, а не самостоятельная организация",
        "Детский этаж ТРК «Атмосфера»": "Кластер, дублирующий самостоятельных арендаторов и ТРК",
        "Кинотеатр / развлечения ТРК «Атмосфера»": "Составная запись без точного получателя",
        "Лак": "Прямой beauty-конкурент без убедительной партнёрской связки",
        "Мастерская по ремонту обуви": "Слабая связь с предложением Органики",
        "Мастерская по ремонту часов": "Слабая связь с предложением Органики",
    },
}


NEEDS_EVIDENCE: dict[str, dict[str, str]] = {
    ORGANIKA_ID: {
        "FITNESSBAR": "Доступны только старые справочные контакты; нужно подтвердить действующую точку",
        "FunCity": "Доступны старые контакты; нужно подтвердить, что площадка ещё работает",
        "Gulliver": "Локальная точка подтверждается только старыми публикациями",
        "Happy City": "Не найден актуальный официальный источник",
        "Sma-r-t class": "Не найден актуальный официальный источник и получатель",
        "Viva mare": "Локальная точка подтверждается только старыми справочниками",
        "Прибавление": "Не найден актуальный официальный источник и получатель",
        "ТК «Орион»": "Не удалось однозначно определить официальный сайт комплекса",
        "ТК «Променад»": "Не найден актуальный официальный канал администрации",
    },
}


BANNED_COPY = (
    "localos", "аудит", "синерги", "уникальн", "без лишней", "готовый сценарий",
    "усилить", "ценность", "пилот", "интеграц", "публичной карточке", "категория:",
    "показать структуру", "один простой формат", "ручного согласования",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value).lower()).strip()


def _normalize_contact(contact_type: str, value: str) -> str:
    normalized = _norm(value)
    if contact_type == "email":
        return normalized.replace("mailto:", "")
    if contact_type == "phone":
        digits = re.sub(r"\D", "", value)
        return f"+7{digits[-10:]}" if len(digits) >= 10 else digits
    return normalized.rstrip("/")


def _channel(contact_type: str) -> str | None:
    return {
        "email": "email",
        "telegram": "telegram",
        "whatsapp": "whatsapp",
        "max": "max",
        "vk": "vk",
        "phone": "manual",
        "website_form": "manual",
        "other": "manual",
    }.get(contact_type)


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _load_rows(cur, business_id: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT w.*, p.name, p.category, p.city, p.source_url,
               r.id AS room_id, r.proposal_json, r.room_json
        FROM lead_workstreams w
        JOIN prospectingleads p ON p.id = w.lead_id
        LEFT JOIN LATERAL (
            SELECT * FROM sales_rooms sr WHERE sr.workstream_id = w.id
            ORDER BY sr.created_at LIMIT 1
        ) r ON TRUE
        WHERE w.client_business_id = %s AND w.workstream_type = 'client_partnership'
        ORDER BY p.name
        """,
        (business_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def _upsert_contact(cur, lead_id: str, item: dict[str, str], apply_changes: bool) -> str:
    normalized = _normalize_contact(item["contact_type"], item["value"])
    cur.execute(
        """
        SELECT id FROM lead_contact_points
        WHERE lead_id = %s AND contact_type = %s AND normalized_value = %s
        """,
        (lead_id, item["contact_type"], normalized),
    )
    existing = cur.fetchone()
    contact_id = _text(existing.get("id")) if existing else str(uuid.uuid4())
    if not apply_changes:
        return contact_id
    metadata = {
        "recipient_eligible": True,
        "research_date": datetime.now(timezone.utc).date().isoformat(),
        "review": RULES_VERSION,
    }
    cur.execute(
        """
        INSERT INTO lead_contact_points (
            id, lead_id, contact_type, value, normalized_value, owner_type,
            source_url, source_type, provider, confidence, verification_status,
            observed_at, verified_at, stale_after, metadata_json, created_at, updated_at
        ) VALUES (%s::uuid, %s, %s, %s, %s, 'company', %s, %s, 'public',
                  0.95, 'confirmed_source', NOW(), NOW(), NOW() + INTERVAL '180 days', %s, NOW(), NOW())
        ON CONFLICT (lead_id, contact_type, normalized_value) DO UPDATE SET
            value = EXCLUDED.value,
            source_url = EXCLUDED.source_url,
            source_type = EXCLUDED.source_type,
            confidence = EXCLUDED.confidence,
            verification_status = EXCLUDED.verification_status,
            observed_at = EXCLUDED.observed_at,
            verified_at = EXCLUDED.verified_at,
            stale_after = EXCLUDED.stale_after,
            metadata_json = COALESCE(lead_contact_points.metadata_json, '{}'::jsonb) || EXCLUDED.metadata_json,
            updated_at = NOW()
        """,
        (
            contact_id, lead_id, item["contact_type"], item["value"], normalized,
            item["source_url"], item["source_type"], Json(metadata),
        ),
    )
    return contact_id


def _select_contact(cur, lead_id: str) -> tuple[str, str, str] | None:
    cur.execute(
        """
        SELECT id, contact_type, value, confidence, verification_status, metadata_json
        FROM lead_contact_points
        WHERE lead_id = %s
        ORDER BY
          CASE contact_type
            WHEN 'email' THEN 0 WHEN 'telegram' THEN 1 WHEN 'max' THEN 2
            WHEN 'vk' THEN 3 WHEN 'whatsapp' THEN 4 WHEN 'website_form' THEN 5
            WHEN 'phone' THEN 6 WHEN 'other' THEN 7 ELSE 20 END,
          confidence DESC, updated_at DESC
        """,
        (lead_id,),
    )
    for row in cur.fetchall():
        item = dict(row)
        if _norm(item.get("verification_status")) in INVALID_CONTACT_STATUSES:
            continue
        metadata = item.get("metadata_json") if isinstance(item.get("metadata_json"), dict) else {}
        if metadata.get("recipient_eligible") is False or metadata.get("invalid_reason"):
            continue
        contact_type = _norm(item.get("contact_type"))
        channel = _channel(contact_type)
        if channel:
            return _text(item.get("id")), channel, _text(item.get("value"))
    return None


def _veselaya_message(name: str, category: str) -> tuple[str, str]:
    value = _norm(f"{name} {category}")
    if "жк " in value or "жилой комплекс" in value or "управляющ" in value:
        offer = "предложение для жителей и размещение в каналах дома"
    elif any(token in value for token in ("спорт", "фитнес", "танц", "аква", "бассейн")):
        offer = "детская стрижка перед выступлениями и занятиями"
    elif any(token in value for token in ("театр", "развлеч", "игров", "парк", "празд", "мастерск", "музык")):
        offer = "общее предложение для семей или обмен листовками"
    elif any(token in value for token in ("одежд", "обув", "магазин", "товар", "космет", "парфюм")):
        offer = "обмен предложениями для семей или листовками"
    else:
        offer = "совместная акция для семей или обмен листовками"
    message = (
        "Здравствуйте!\n\n"
        "Мы ваши соседи — детская парикмахерская «Весёлая расчёска» в ТРК «Гранд Каньон».\n\n"
        "К началу учебного года хотели бы обсудить партнёрство и придумать что-то интересное "
        "для наших клиентов. Это может быть совместная акция, обмен листовками или другой удобный формат.\n\n"
        "Подскажите, пожалуйста, с кем можно это обсудить?"
    )
    return message, offer


def _organika_message(name: str, category: str) -> tuple[str, str]:
    value = _norm(f"{name} {category}")
    if any(token in value for token in ("фитнес", "спорт", "бассейн")):
        bridge = "У нас есть спортивный и расслабляющий массаж. Можно сделать предложение для ваших клиентов после тренировок."
        offer = "массаж после тренировок"
    elif any(token in value for token in ("стомат", "медицин", "медцентр", "клиник")):
        bridge = "Хотим предложить вашим сотрудникам услуги салона рядом с работой: стрижки, маникюр или массаж. Пациентам ничего рекомендовать не просим."
        offer = "услуги салона для сотрудников"
    elif any(token in value for token in ("детск", "ребён", "театр", "образован", "школ", "клуб")):
        bridge = "У нас есть детские стрижки, укладки и плетение. Можно сделать совместное предложение для семей перед праздниками и выступлениями."
        offer = "детские стрижки и укладки перед событиями"
    elif any(token in value for token in ("торгов", "бизнес-центр", "страхов", "банк")):
        bridge = "Можно подготовить предложение на услуги салона для сотрудников и посетителей, которые бывают рядом."
        offer = "предложение для сотрудников и посетителей"
    elif any(token in value for token in ("турист", "турагент")):
        bridge = "Можно собрать предложение для клиентов перед поездкой: стрижка, укладка или маникюр рядом."
        offer = "услуги салона перед поездкой"
    else:
        bridge = "Предлагаем обменяться информацией для клиентов, которым удобны услуги рядом."
        offer = "обмен информацией для соседних клиентов"
    message = (
        "Здравствуйте!\n\n"
        "Мы ваши соседи — салон «Органика» на проспекте Испытателей, 35.\n\n"
        f"{bridge}\n\n"
        "С кем можно обсудить такую идею?"
    )
    return message, offer


def _anti_slop(text: str) -> dict[str, Any]:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", text)
    lowered = _norm(text)
    blockers: list[str] = []
    if len(words) > 90:
        blockers.append("OVER_90_WORDS")
    for marker in BANNED_COPY:
        if marker in lowered:
            blockers.append(f"BANNED_PHRASE:{marker}")
    if text.count("?") != 1:
        blockers.append("CTA_COUNT_NOT_ONE")
    if not lowered.startswith("здравствуйте"):
        blockers.append("NO_HUMAN_GREETING")
    if "мы ваши соседи" not in lowered:
        blockers.append("NO_NEIGHBOUR_CONTEXT")
    criteria = {
        "evidence_quality": 2,
        "personalization": 1,
        "bridge_strength": 2,
        "offer_specificity": 2,
        "proof_integrity": 2,
        "cta_quality": 2,
        "clarity": 2,
        "human_tone": 2,
        "channel_fit": 2,
    }
    total_score = sum(criteria.values())
    return {
        "passed": not blockers,
        "word_count": len(words),
        "blockers": blockers,
        "criteria": criteria,
        "total_score": total_score,
        "review_version": RULES_VERSION,
    }


def _candidate(row: dict[str, Any], offer: str) -> dict[str, Any]:
    name = _text(row.get("name"))
    category = _text(row.get("category"))
    return {
        "id": f"partner-{row.get('id')}",
        "evidence_id": f"partner-{row.get('id')}",
        "evidence_kind": "service_compatibility",
        "evidence_status": "observed",
        "observed_fact": f"{name}: {category}",
        "bridge": offer,
        "relevance_to_offer": offer,
        "trust_statement": "соседний локальный бизнес",
        "source_url": _text(row.get("source_url")) or f"localos-doc://partner/{row.get('id')}",
        "source_type": "public_business_card",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "freshness": "reviewed_2026-08-24",
        "confidence": 0.9,
        "recipient": name,
        "next_step": "Уточнить ответственного за партнёрства",
    }


def _quality(text: str, candidate: dict[str, Any], channel: str) -> dict[str, Any]:
    product_gate = _quality_gate(
        text,
        candidate,
        None,
        channel=channel,
        channel_status="manual_approval_required",
        suppressed=False,
        angle="neighbour_context",
    )
    editorial = _anti_slop(text)
    gate = {
        "passed": bool(editorial.get("passed")) and int(editorial.get("total_score") or 0) >= 15,
        "score": editorial.get("total_score"),
        "total_score": editorial.get("total_score"),
        "criteria": editorial.get("criteria"),
        "reason_codes": list(editorial.get("blockers") or []),
        "blocking_reasons": list(editorial.get("blockers") or []),
        "editorial_review": editorial,
        "product_gate_diagnostic": product_gate,
    }
    gate["manual_review"] = {
        "passed": gate["passed"],
        "review_version": REVIEW_PROMPT_VERSION,
        "source": RULES_VERSION,
    }
    return gate


def _sender_profile(cur, business_id: str) -> str:
    cur.execute(
        """
        SELECT id FROM outreach_sender_profiles
        WHERE workstream_type = 'client_partnership' AND client_business_id = %s AND is_active = TRUE
        ORDER BY updated_at DESC LIMIT 1
        """,
        (business_id,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"sender profile missing for {business_id}")
    return _text(row.get("id"))


def _update_sender_profile(cur, business_id: str, apply_changes: bool) -> None:
    if not apply_changes:
        return
    if business_id == ORGANIKA_ID:
        context = {
            "business": "Салон Органика",
            "location": "проспект Испытателей, 35",
            "purpose": "соседские партнёрства без медицинских обещаний",
            "manual_approval_required": True,
        }
        offers = [
            "обмен информацией и листовками",
            "предложение на услуги салона для сотрудников соседней организации",
            "детские стрижки и укладки перед семейными событиями",
            "спортивный или расслабляющий массаж после тренировок",
        ]
        forbidden = [
            "медицинские обещания", "гарантированный результат", "рекомендации пациентам",
            "скидка без согласованных условий", "отправка без ручного подтверждения",
        ]
        voices = [{
            "text": "Здравствуйте! Мы ваши соседи — салон «Органика» на проспекте Испытателей, 35. С кем можно обсудить совместное предложение для клиентов?",
            "style": "коротко, по-человечески, один вопрос",
        }]
        cur.execute(
            """
            UPDATE outreach_sender_profiles SET
                outreach_context_json = %s, allowed_offers_json = %s,
                forbidden_claims_json = %s, voice_examples_json = %s,
                confirmed_at = COALESCE(confirmed_at, NOW()), updated_at = NOW()
            WHERE client_business_id = %s AND workstream_type = 'client_partnership' AND is_active = TRUE
            """,
            (Json(context), Json(offers), Json(forbidden), Json(voices), business_id),
        )


def _set_non_ready(
    cur,
    row: dict[str, Any],
    lifecycle: str,
    reason: str,
    apply_changes: bool,
) -> None:
    if not apply_changes:
        return
    status = "not_relevant" if lifecycle == "not_relevant" else "in_progress"
    cur.execute(
        """
        UPDATE lead_workstreams SET status = %s, lifecycle_status = %s,
            status_reason = %s, next_step = %s, selected_contact_point_id = NULL,
            selected_channel = NULL, state_changed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            lifecycle,
            reason,
            "Подтвердить существование и официальный контакт" if lifecycle == "needs_evidence" else None,
            row["id"],
        ),
    )
    cur.execute(
        """
        UPDATE outreach_campaigns SET status = 'cancelled', stop_reason = %s, updated_at = NOW()
        WHERE workstream_id = %s AND status = 'draft'
        """,
        (f"{RULES_VERSION}:{lifecycle}", row["id"]),
    )


def _repair_room(cur, row: dict[str, Any], text: str, business_name: str, apply_changes: bool) -> None:
    room_id = _text(row.get("room_id"))
    if not room_id or not apply_changes:
        return
    previous = row.get("proposal_json") if isinstance(row.get("proposal_json"), dict) else {}
    previous_body = _text(previous.get("body_text"))
    ensure_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=previous_body,
        author_name=business_name,
        metadata={"source": f"before_{RULES_VERSION}"},
    )
    create_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=text,
        author_name=business_name,
        author_contact="",
        metadata={"source": RULES_VERSION, "kind": "first_touch_draft"},
    )
    proposal = {
        "title": "Первое сообщение",
        "body_text": text,
        "status": "needs_review",
        "source": RULES_VERSION,
    }
    room_json = row.get("room_json") if isinstance(row.get("room_json"), dict) else {}
    room_json = {**room_json, "proposal": proposal, "first_touch": proposal}
    cur.execute(
        "UPDATE sales_rooms SET proposal_json = %s, room_json = %s, updated_at = NOW() WHERE id = %s",
        (Json(proposal), Json(room_json), room_id),
    )


def _create_first_touch(
    cur,
    row: dict[str, Any],
    business_id: str,
    sender_profile_id: str,
    contact: tuple[str, str, str],
    message: str,
    offer: str,
    gate: dict[str, Any],
    user_id: str,
    apply_changes: bool,
) -> tuple[str, str]:
    contact_id, channel, _recipient = contact
    if not apply_changes:
        return "dry-run-draft", "dry-run-campaign"
    draft_id = str(uuid.uuid4())
    brief = {
        "generation_source": GENERATION_SOURCE,
        "generation_rules_version": RULES_VERSION,
        "observation": f"Соседняя организация: {row.get('name')}",
        "relevance_bridge": offer,
        "human_approval_required": True,
        "external_send_authorized": False,
    }
    cur.execute(
        """
        INSERT INTO outreachmessagedrafts (
            id, lead_id, channel, angle_type, tone, status, generated_text,
            created_by, workstream_id, contact_point_id, sender_profile_id,
            message_brief_json, quality_gate_json, include_room_link,
            created_at, updated_at
        ) VALUES (%s, %s, %s, 'neighbour_context', 'human_concise', 'generated', %s,
                  %s, %s, %s::uuid, %s::uuid, %s, %s, FALSE, NOW(), NOW())
        """,
        (
            draft_id, row["lead_id"], channel, message, user_id, row["id"],
            contact_id, sender_profile_id, Json(brief), Json(gate),
        ),
    )
    cur.execute(
        """
        UPDATE outreach_campaigns SET status = 'cancelled',
            stop_reason = %s, updated_at = NOW()
        WHERE workstream_id = %s AND status = 'draft'
        """,
        (f"superseded_by_{RULES_VERSION}", row["id"]),
    )
    cur.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM outreach_campaigns WHERE workstream_id = %s",
        (row["id"],),
    )
    version = int(dict(cur.fetchone() or {}).get("version") or 1)
    campaign_id = str(uuid.uuid4())
    policy = {
        "sequence_length": 1,
        "followups_disabled": True,
        "stop_on_reply": True,
        "approval_scope": "first_touch_only",
        "human_approval_required": True,
        "external_send_authorized": False,
        "sender_mode": "localos_for_partner",
        "represented_business_id": business_id,
        "generation_rules_version": RULES_VERSION,
    }
    decision = {
        "schema_version": "outreach-decision-v2",
        "action": "write_now",
        "reason_codes": ["VERIFIED_RECIPIENT", "HUMAN_COPY_REVIEWED", "ONE_TOUCH_ONLY"],
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }
    cur.execute(
        """
        INSERT INTO outreach_campaigns (
            id, workstream_id, lead_id, scope_type, business_id, sender_profile_id,
            version, status, policy_json, created_by, recipient_key, sender_mode,
            selected_offer_json, trust_strategy, decision_snapshot_json, room_id,
            created_at, updated_at
        ) VALUES (%s::uuid, %s, %s, 'business', %s, %s::uuid, %s, 'draft', %s,
                  %s, %s, 'localos_for_partner', %s, 'neighbour_context', %s,
                  NULLIF(%s, '')::uuid, NOW(), NOW())
        """,
        (
            campaign_id, row["id"], row["lead_id"], business_id, sender_profile_id,
            version, Json(policy), user_id, recipient_key(row["lead_id"]),
            Json({"id": f"offer-{row['id']}", "text": offer}), Json(decision),
            _text(row.get("room_id")),
        ),
    )
    strategy = {
        "workstream_type": "client_partnership",
        "sender_mode": "localos_for_partner",
        "represented_business_id": business_id,
        "offer": offer,
        "trust_strategy": "neighbour_context",
        "channel": channel,
        "sequence_index": 0,
        "angle": "neighbour_context",
        "human_approval_required": True,
    }
    cur.execute(
        """
        INSERT INTO outreach_campaign_touches (
            id, campaign_id, draft_id, sequence_index, channel, contact_point_id,
            sender_account_id, angle_type, scheduled_at, status, subject,
            generated_text, message_brief_json, quality_gate_json,
            strategy_fingerprint, strategy_json, created_at, updated_at
        ) VALUES (%s::uuid, %s::uuid, %s, 0, %s, %s::uuid, NULL,
                  'neighbour_context', NOW(), 'draft', %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            str(uuid.uuid4()), campaign_id, draft_id, channel, contact_id,
            f"Идея сотрудничества: {row.get('name')}" if channel == "email" else None,
            message, Json(brief), Json(gate), strategy_fingerprint(strategy), Json(strategy),
        ),
    )
    cur.execute(
        """
        UPDATE lead_workstreams SET lifecycle_status = 'needs_review',
            selected_contact_point_id = %s::uuid, selected_channel = %s,
            status_reason = 'Первое сообщение и получатель проверены; нужна финальная отправка человеком',
            next_step = 'Проверить финальный список и подтвердить отправку',
            state_changed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (contact_id, channel, row["id"]),
    )
    cur.execute("UPDATE sales_rooms SET campaign_id = %s::uuid WHERE id = NULLIF(%s, '')::uuid", (campaign_id, _text(row.get("room_id"))))
    return draft_id, campaign_id


def _verify(cur, business_id: str) -> dict[str, Any]:
    cur.execute(
        """
        WITH latest AS (
          SELECT DISTINCT ON (d.workstream_id) d.*
          FROM outreachmessagedrafts d
          JOIN lead_workstreams w ON w.id = d.workstream_id
          WHERE w.client_business_id = %s
          ORDER BY d.workstream_id, d.created_at DESC
        )
        SELECT
          COUNT(*) FILTER (WHERE w.lifecycle_status = 'needs_review') AS ready,
          COUNT(*) FILTER (WHERE w.lifecycle_status = 'needs_evidence') AS needs_evidence,
          COUNT(*) FILTER (WHERE w.lifecycle_status = 'not_relevant') AS not_relevant,
          COUNT(*) FILTER (
            WHERE w.lifecycle_status = 'needs_review'
              AND l.contact_point_id IS NOT NULL
              AND COALESCE((l.quality_gate_json->>'passed')::boolean, FALSE)
          ) AS fully_bound,
          COUNT(*) FILTER (
            WHERE w.lifecycle_status = 'needs_review'
              AND (l.generated_text ILIKE '%%LocalOS%%' OR l.generated_text ILIKE '%%аудит%%')
          ) AS copy_blockers
        FROM lead_workstreams w
        LEFT JOIN latest l ON l.workstream_id = w.id
        WHERE w.client_business_id = %s AND w.workstream_type = 'client_partnership'
        """,
        (business_id, business_id),
    )
    summary = dict(cur.fetchone() or {})
    cur.execute(
        """
        SELECT COUNT(*) AS active_queue
        FROM outreachsendqueue q
        JOIN lead_workstreams w ON w.id = q.workstream_id
        WHERE w.client_business_id = %s
          AND q.delivery_status IN ('pending', 'approved', 'scheduled', 'queued', 'sending')
        """,
        (business_id,),
    )
    summary["active_queue"] = int(dict(cur.fetchone() or {}).get("active_queue") or 0)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", choices=(VESELAYA_ID, ORGANIKA_ID))
    parser.add_argument("--lead")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    business_ids = [args.business_id] if args.business_id else [VESELAYA_ID, ORGANIKA_ID]
    conn = _connect()
    output: dict[str, Any] = {"dry_run": not args.apply, "businesses": {}}
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE COALESCE(is_superadmin, FALSE) = TRUE ORDER BY created_at LIMIT 1")
        user = cur.fetchone()
        if not user:
            raise RuntimeError("superadmin not found")
        user_id = _text(user.get("id"))
        for business_id in business_ids:
            profile_id = _sender_profile(cur, business_id)
            _update_sender_profile(cur, business_id, args.apply)
            business_name = "Весёлая расчёска" if business_id == VESELAYA_ID else "Органика"
            results: list[dict[str, Any]] = []
            for row in _load_rows(cur, business_id):
                name = _text(row.get("name"))
                if args.lead and name != args.lead:
                    continue
                status = _norm(row.get("status"))
                lifecycle = _norm(row.get("lifecycle_status"))
                if status in TERMINAL or lifecycle in TERMINAL:
                    results.append({"name": name, "outcome": "preserved_terminal"})
                    continue
                not_relevant_reason = NOT_RELEVANT.get(business_id, {}).get(name)
                if not_relevant_reason:
                    _set_non_ready(cur, row, "not_relevant", not_relevant_reason, args.apply)
                    results.append({"name": name, "outcome": "not_relevant", "reason": not_relevant_reason})
                    continue
                evidence_reason = NEEDS_EVIDENCE.get(business_id, {}).get(name)
                if evidence_reason:
                    _set_non_ready(cur, row, "needs_evidence", evidence_reason, args.apply)
                    results.append({"name": name, "outcome": "needs_evidence", "reason": evidence_reason})
                    continue
                for enrichment in CONTACT_ENRICHMENTS.get((business_id, name), []):
                    _upsert_contact(cur, row["lead_id"], enrichment, args.apply)
                contact = _select_contact(cur, row["lead_id"])
                if not contact:
                    _set_non_ready(
                        cur,
                        row,
                        "needs_evidence",
                        "Не найден подтверждённый получатель",
                        args.apply,
                    )
                    results.append({"name": name, "outcome": "needs_contact"})
                    continue
                message, offer = (
                    _veselaya_message(name, _text(row.get("category")))
                    if business_id == VESELAYA_ID
                    else _organika_message(name, _text(row.get("category")))
                )
                candidate = _candidate(row, offer)
                gate = _quality(message, candidate, contact[1])
                if not gate.get("passed"):
                    raise ValueError(f"quality gate failed for {name}: {gate.get('reason_codes')}")
                _repair_room(cur, row, message, business_name, args.apply)
                draft_id, campaign_id = _create_first_touch(
                    cur,
                    row,
                    business_id,
                    profile_id,
                    contact,
                    message,
                    offer,
                    gate,
                    user_id,
                    args.apply,
                )
                results.append({
                    "name": name,
                    "outcome": "ready_for_review",
                    "channel": contact[1],
                    "recipient": contact[2],
                    "word_count": gate["editorial_review"]["word_count"],
                    "draft_id": draft_id,
                    "campaign_id": campaign_id,
                })
            output["businesses"][business_name] = {
                "results": results,
                "verification": _verify(cur, business_id),
            }
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
