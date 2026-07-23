#!/usr/bin/env python3
"""Review Veselaya Rascheska partner rooms and create safe manual campaign drafts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from core.ai_learning import record_ai_learning_event  # noqa: E402
from services.outreach_campaign_service import (  # noqa: E402
    _aggregate_quality_gate,
    _quality_gate,
    record_campaign_event,
)
from services.outreach_personalization_ai import (  # noqa: E402
    PROMPT_VERSION,
    REVIEW_PROMPT_VERSION,
)
from services.outreach_relationship_service import build_room_preview  # noqa: E402
from services.outreach_safety_service import recipient_key, strategy_fingerprint  # noqa: E402
from services.sales_room_review_service import (  # noqa: E402
    create_sales_room_proposal_version,
    ensure_sales_room_proposal_version,
)


DEFAULT_BUSINESS_ID = "cb674174-8b3d-41a3-8277-525c849935f2"
PLATFORM_EMAIL = "localosgo@gmail.com"
GENERATION_SOURCE = "manual_product_correction"
REPAIR_VERSION = "veselaya_partner_rules_v3"
TERMINAL_STATES = {
    "replied", "converted", "closed_lost", "not_relevant", "suppressed",
    "unsubscribed", "hard_no", "closed", "won", "lost", "archived",
}
BLOCKING_CAMPAIGN_STATES = {"approved", "active", "paused"}
INVALID_CONTACT_STATUSES = {"invalid", "rejected", "stale", "bounced", "suppressed"}
USABLE_CONTACT_STATUSES = {"confirmed_source", "valid_format", "verified", "format_verified"}


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value).lower()).strip()


def _partner_kind(category: Any, name: Any = "") -> str:
    value = f"{_normalized(category)} {_normalized(name)}"
    if any(marker in value for marker in ("жилой комплекс", "жк ", "управляющая компания")):
        return "residential"
    if any(marker in value for marker in ("одежд", "обув", "детский магазин", "детские товар", "игруш")):
        return "retail"
    if any(marker in value for marker in ("спорт", "фитнес", "танц", "секци", "каток", "ледов", "плаван", "аква")):
        return "sport"
    if any(marker in value for marker in ("образоват", "школ", "обуч", "музык", "клуб", "мастерск")):
        return "education"
    if any(marker in value for marker in (
        "развлекатель", "театр", "музей", "зоопарк", "парк", "аттракцион",
        "праздник", "игров", "квест", "город професс", "досуг", "экскурс",
    )):
        return "entertainment"
    if any(marker in value for marker in ("стомат", "медицин", "клиник", "здоров")):
        return "medical"
    if any(marker in value for marker in ("салон", "beauty", "spa", "космет", "парфюмер", "ногт")):
        return "beauty"
    return "family"


def _offer_summary(name: str, category: str) -> str:
    if _partner_kind(category, name) == "residential":
        audience = (
            "семей гостей и жителей Yes Apart"
            if _normalized(name) == "yes apart"
            else f"жителей {name}"
        )
        return f"предложить особые условия на детские стрижки для {audience}"
    if "кидбург" in _normalized(name):
        return (
            "провести для детей мастер-класс по профессии парикмахера: плетение косичек, простые причёски "
            "и знакомство с работой мастера"
        )
    kind = _partner_kind(category, name)
    residential_audience = "семьи гостей и жителей" if "апарт-отель" in _normalized(category) else f"жителей {name}"
    offers = {
        "residential": (
            f"пригласить {residential_audience} в детскую парикмахерскую рядом: согласовать размещение информации "
            "или листовок и отдельно обсудить мастер-класс для семей"
        ),
        "retail": (
            f"подготовить небольшой совместный материал для семей, чтобы посетители {name} и Весёлой "
            "расчёски узнали о двух полезных местах рядом"
        ),
        "sport": (
            f"предложить семьям из {name} удобный формат подготовки детских причёсок перед выступлениями "
            "или соревнованиями и проверить интерес на одном небольшом пилоте"
        ),
        "education": (
            f"провести для семей из {name} небольшой мастер-класс по детским причёскам или собрать полезный "
            "материал перед праздниками и выступлениями"
        ),
        "entertainment": (
            f"собрать для посетителей {name} один семейный формат: мастер-класс, подготовку образа к событию или "
            "небольшой совместный материал"
        ),
        "medical": (
            f"подготовить вместе с {name} спокойный информационный материал для семей района о двух полезных "
            "местах рядом, без медицинских обещаний и автоматической рассылки"
        ),
        "beauty": (
            f"проверить с {name} один семейный формат для родителей и детей: совместный материал о разных "
            "сценариях ухода без заранее обещанных скидок"
        ),
        "family": (
            f"выбрать вместе с {name} один конкретный и небольшой формат для семей района и сначала проверить "
            "его без сложной интеграции"
        ),
    }
    return offers[kind]


def _proposal(name: str, category: str) -> dict[str, Any]:
    kind = _partner_kind(category, name)
    if kind == "residential":
        audience = (
            "семей гостей и жителей Yes Apart"
            if _normalized(name) == "yes apart"
            else f"жителей {name}"
        )
        if _normalized(name) == "yes apart":
            body = (
                "Мы ваши соседи - сеть детских парикмахерских Весёлая расчёска.\n\n"
                f"Предлагаем особые условия на детские стрижки для {audience}. "
                "Информацию можно разместить на ресепшене или в каналах комплекса.\n\n"
                "Конкретные условия и формат публикации согласуем отдельно до запуска. Дополнительно можно "
                "обсудить небольшой мастер-класс для детей."
            )
        else:
            body = (
                "Мы ваши соседи - сеть детских парикмахерских Весёлая расчёска.\n\n"
                f"Предлагаем особые условия на детские стрижки для {audience}. Формат информирования можно "
                "согласовать с управляющей компанией: каналы ЖК, листовки или объявления в общих зонах.\n\n"
                "Конкретные условия и формат публикации согласуем отдельно до запуска. Дополнительно можно "
                "пригласить семьи на небольшой мастер-класс для детей."
            )
    else:
        body = (
            "Мы ваши соседи - сеть детских парикмахерских Весёлая расчёска в ТРК Гранд Каньон.\n\n"
            f"В карточке {name} указана категория: {category}. У нас может пересекаться аудитория семей с детьми.\n\n"
            f"Предлагаем {_offer_summary(name, category)}. Скидки, рекомендации и передача контактов заранее "
            "не обещаются - сначала согласуем безопасный формат и проверим интерес."
        )
    return {
        "title": "Идея сотрудничества",
        "body_text": body,
        "status": "draft",
        "source": REPAIR_VERSION,
        "recipient_kind": kind,
    }


def _room_needs_repair(name: str, body: str, category: str = "") -> bool:
    if not body:
        return True
    lowered = _normalized(body)
    generic_markers = (
        "у весёлая расчёска и",
        "20-минутный разговор",
        "без интеграции и автоматической рассылки",
        "один безопасный совместный тест",
    )
    if any(marker in lowered for marker in generic_markers):
        return True
    if _normalized(name) == "спортивный клуб gymfusion" and "кабриоль" in lowered:
        return True
    if _normalized(name) == "yes apart" and "гостей" not in lowered:
        return True
    if (
        _partner_kind(category, name) == "residential"
        and "особые условия на детские стрижки" not in lowered
    ):
        return True
    return False


def _usable_contact(contact: dict[str, Any], lead_name: str) -> bool:
    status = _normalized(contact.get("verification_status"))
    if status in INVALID_CONTACT_STATUSES or status not in USABLE_CONTACT_STATUSES:
        return False
    source = _normalized(contact.get("source_url"))
    value = _normalized(contact.get("value"))
    if lead_name in {"Eco beauty bar", "Королевство Попугаев"} and "trk-canyon.ru/contacts" in source:
        return False
    if lead_name == "Спортивный клуб Gymfusion" and ("kabriol" in source or "kabriol" in value):
        return False
    contact_type = _normalized(contact.get("contact_type"))
    if contact_type == "email":
        value = _normalized(contact.get("value"))
        if value.startswith("mailto:") or "@" not in value:
            return False
        local_part = value.split("@", 1)[0]
        if local_part.startswith((
            "owner", "rent", "daily", "zakupki", "purchase", "career",
            "vacancy", "job", "noreply", "no-reply",
        )):
            return False
    metadata = contact.get("metadata_json") if isinstance(contact.get("metadata_json"), dict) else {}
    if metadata.get("recipient_eligible") is False:
        return False
    telegram_kind = _normalized(metadata.get("telegram_entity_kind") or metadata.get("entity_kind"))
    if contact_type == "telegram" and telegram_kind in {"channel", "supergroup", "group"}:
        return False
    if _normalized(contact.get("owner_type")) in {"public_source", "organization_channel", "shared_platform"}:
        return False
    return bool(_text(contact.get("value")))


def _channel_for_contact(contact: dict[str, Any]) -> str | None:
    contact_type = _normalized(contact.get("contact_type"))
    mapping = {
        "email": "email",
        "telegram": "telegram",
        "whatsapp": "whatsapp",
        "max": "max",
        "vk": "vk",
        "phone": "manual",
        "sms": "sms",
    }
    return mapping.get(contact_type)


def _choose_contacts(contacts: list[dict[str, Any]], lead_name: str) -> list[tuple[str, dict[str, Any]]]:
    priorities = {"email": 0, "telegram": 1, "whatsapp": 2, "max": 3, "vk": 4, "sms": 5}
    chosen: dict[str, dict[str, Any]] = {}
    def recipient_rank(contact: dict[str, Any]) -> tuple[int, str]:
        if _normalized(contact.get("contact_type")) != "email":
            return 10, _normalized(contact.get("value"))
        local_part = _normalized(contact.get("value")).split("@", 1)[0]
        preferred = {"office": 0, "info": 1, "marketing": 2, "partnership": 3, "pr": 4}
        return preferred.get(local_part, 5), local_part

    for contact in sorted(contacts, key=recipient_rank):
        if not _usable_contact(contact, lead_name):
            continue
        channel = _channel_for_contact(contact)
        if channel and channel not in chosen:
            chosen[channel] = contact
    return sorted(chosen.items(), key=lambda item: priorities.get(item[0], 99))


def _observation(name: str, category: str) -> str:
    return f"В публичной карточке {name} указана категория: {category}."


def _messages(name: str, category: str) -> list[dict[str, str]]:
    if _partner_kind(category, name) == "residential":
        audience = (
            "семей гостей и жителей Yes Apart"
            if _normalized(name) == "yes apart"
            else f"жителей {name}"
        )
        placement = (
            "на ресепшене или в каналах комплекса"
            if _normalized(name) == "yes apart"
            else "в каналах ЖК или общих зонах"
        )
        return [
            {
                "angle": "signal",
                "text": (
                    "Здравствуйте! Мы ваши соседи - сеть детских парикмахерских Весёлая расчёска. "
                    f"Хотим предложить особые условия на детские стрижки для {audience}. "
                    "Не подскажете, с кем я мог бы обсудить детали?"
                ),
            },
            {
                "angle": "matching_authority",
                "text": (
                    f"Здравствуйте! Весёлая расчёска может подготовить для {name} короткий текст и макет с "
                    f"особыми условиями для семей. Их можно разместить {placement}. Показать вариант?"
                ),
            },
            {
                "angle": "proof",
                "text": (
                    f"Здравствуйте! Для {audience} Весёлая расчёска может предложить особые условия на "
                    "детские стрижки и небольшой мастер-класс для детей. Прислать два варианта сотрудничества?"
                ),
            },
            {
                "angle": "respectful_close",
                "text": (
                    f"Здравствуйте! Весёлая расчёска предлагает особые условия для {audience}. "
                    "Если сейчас неактуально, больше писать не будем. Вернуться к идее позже?"
                ),
            },
        ]
    fact = _observation(name, category)
    bridge = "Поэтому предлагаем проверить один конкретный формат сотрудничества для семей с детьми."
    idea = _offer_summary(name, category)
    return [
        {
            "angle": "signal",
            "text": (
                "Здравствуйте! Мы ваши соседи - сеть детских парикмахерских Весёлая расчёска. "
                f"{fact} {bridge} Можно {idea}. Прислать короткое предложение?"
            ),
        },
        {
            "angle": "matching_authority",
            "text": (
                f"Здравствуйте! Возвращаемся к идее сотрудничества. {name} и Весёлая расчёска работают с семьями "
                f"с детьми. {bridge} В качестве первого варианта можно {idea}. Удобно прислать два возможных варианта?"
            ),
        },
        {
            "angle": "proof",
            "text": (
                f"Здравствуйте! Пишем команде {name}. Мы не предлагаем сложную интеграцию или автоматическую "
                f"рассылку. {bridge} Первый шаг - {idea}. Прислать план небольшого пилота?"
            ),
        },
        {
            "angle": "respectful_close",
            "text": (
                f"Здравствуйте! Не хотим отвлекать команду {name}. {bridge} Если формат сейчас не "
                "актуален, больше писать не будем. Вернуться к идее позже?"
            ),
        },
    ]


def _candidate(name: str, category: str, source_url: str, workstream_id: str) -> dict[str, Any]:
    bridge = "Поэтому предлагаем проверить один конкретный формат сотрудничества для семей с детьми."
    return {
        "id": f"partner-card-{workstream_id}",
        "evidence_id": f"partner-card-{workstream_id}",
        "evidence_kind": "service_compatibility",
        "evidence_status": "observed",
        "observed_fact": _observation(name, category),
        "bridge": bridge,
        "relevance_to_offer": bridge,
        "trust_statement": (
            "Весёлая расчёска"
            if _partner_kind(category, name) == "residential"
            else "Мы ваши соседи - сеть детских парикмахерских Весёлая расчёска."
        ),
        "source_url": source_url or f"localos-doc://partner-card/{workstream_id}",
        "source_type": "public_business_card",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "freshness": "current_snapshot",
        "confidence": 0.9,
        "recipient": name,
        "next_step": "Получить короткое предложение и решить, обсуждать ли пилот",
    }


def _manual_gate(text: str, candidate: dict[str, Any], channel: str, angle: str) -> dict[str, Any]:
    gate = _quality_gate(
        text,
        candidate,
        None,
        channel=channel,
        channel_status="permission_required" if channel in {"email", "telegram"} else "manual",
        suppressed=False,
        angle=angle,
    )
    gate["manual_review"] = {
        "passed": bool(gate.get("passed")),
        "review_version": REVIEW_PROMPT_VERSION,
        "reviewer_role": "superadmin",
        "source": REPAIR_VERSION,
    }
    return gate


def _load_rows(cur, business_id: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT ws.id AS workstream_id, ws.status AS workstream_status, ws.lead_id,
               l.name, l.category, l.city, l.source_url,
               sr.id AS room_id, sr.slug AS room_slug, sr.status AS room_status,
               sr.visibility AS room_visibility, sr.proposal_json, sr.room_json,
               sr.match_json, sr.created_by AS room_created_by
        FROM lead_workstreams ws
        JOIN prospectingleads l ON l.id = ws.lead_id
        LEFT JOIN sales_rooms sr ON sr.workstream_id = ws.id
        WHERE ws.client_business_id = %s AND ws.workstream_type = 'client_partnership'
        ORDER BY l.name, sr.created_at ASC
        """,
        (business_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def _load_contacts(cur, lead_id: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT * FROM lead_contact_points
        WHERE lead_id = %s
        ORDER BY confidence DESC NULLS LAST, created_at ASC
        """,
        (lead_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def _latest_campaign(cur, workstream_id: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT * FROM outreach_campaigns
        WHERE workstream_id = %s
        ORDER BY version DESC, created_at DESC
        LIMIT 1
        """,
        (workstream_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else {}


def _campaign_is_current(cur, campaign: dict[str, Any]) -> bool:
    if not campaign or campaign.get("status") != "draft":
        return False
    cur.execute(
        """
        SELECT COUNT(*) AS count,
               BOOL_AND(message_brief_json->>'generation_source' = %s) AS current_source,
               BOOL_AND(message_brief_json->>'generation_rules_version' = %s) AS current_rules,
               BOOL_AND(COALESCE((quality_gate_json->>'passed')::boolean, FALSE)) AS quality_passed
        FROM outreach_campaign_touches WHERE campaign_id = %s
        """,
        (GENERATION_SOURCE, REPAIR_VERSION, campaign.get("id")),
    )
    row = dict(cur.fetchone() or {})
    return (
        int(row.get("count") or 0) == 4
        and bool(row.get("current_source"))
        and bool(row.get("current_rules"))
        and bool(row.get("quality_passed"))
    )


def _suppressed(cur, business_id: str, lead_id: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM outreach_suppressions
        WHERE (expires_at IS NULL OR expires_at > NOW())
          AND (lead_id = %s OR NULLIF(recipient_key, '') = %s)
          AND (scope_type = 'platform_safety' OR (scope_type = 'business' AND business_id = %s))
        LIMIT 1
        """,
        (lead_id, recipient_key(lead_id), business_id),
    )
    return bool(cur.fetchone())


def _repair_contacts(cur, business_id: str, apply_changes: bool) -> int:
    predicates = """
        (l.name IN ('Eco beauty bar', 'Королевство Попугаев') AND cp.source_url ILIKE '%%trk-canyon.ru/contacts%%')
        OR (l.name = 'Спортивный клуб Gymfusion' AND (cp.source_url ILIKE '%%kabriol%%' OR cp.value ILIKE '%%kabriol%%'))
    """
    cur.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM lead_contact_points cp JOIN prospectingleads l ON l.id = cp.lead_id
        JOIN lead_workstreams ws ON ws.lead_id = l.id
        WHERE ws.client_business_id = %s AND ({predicates})
          AND cp.verification_status <> 'invalid'
        """,
        (business_id,),
    )
    count = int(dict(cur.fetchone() or {}).get("count") or 0)
    if apply_changes and count:
        cur.execute(
            f"""
            UPDATE lead_contact_points cp
            SET verification_status = 'invalid',
                metadata_json = COALESCE(cp.metadata_json, '{{}}'::jsonb) || %s,
                updated_at = NOW()
            FROM prospectingleads l, lead_workstreams ws
            WHERE l.id = cp.lead_id AND ws.lead_id = l.id
              AND ws.client_business_id = %s AND ({predicates})
              AND cp.verification_status <> 'invalid'
            """,
            (Json({"invalid_reason": "contact_belongs_to_shared_venue_or_different_business", "review": REPAIR_VERSION}), business_id),
        )
    return count


def _repair_room(
    cur,
    row: dict[str, Any],
    proposal: dict[str, Any],
    business_id: str,
    user_id: str,
    apply_changes: bool,
    force_repair: bool = False,
) -> tuple[str | None, str]:
    room_id = _text(row.get("room_id"))
    previous = row.get("proposal_json") if isinstance(row.get("proposal_json"), dict) else {}
    previous_body = _text(previous.get("body_text"))
    if room_id and not force_repair and not _room_needs_repair(
        _text(row.get("name")), previous_body, _text(row.get("category"))
    ):
        return room_id, "preserved"
    if not apply_changes:
        return room_id or "dry-run-new-room", "would_repair" if room_id else "would_create"
    if room_id:
        ensure_sales_room_proposal_version(
            cur,
            room_id=room_id,
            body_text=previous_body,
            author_name="Весёлая расчёска",
            metadata={"source": "existing_before_veselaya_partner_rules_v1"},
        )
        create_sales_room_proposal_version(
            cur,
            room_id=room_id,
            body_text=proposal["body_text"],
            author_name="Весёлая расчёска",
            author_contact="",
            metadata={"source": REPAIR_VERSION, "manual_reviewed": True},
        )
        room_json = row.get("room_json") if isinstance(row.get("room_json"), dict) else {}
        room_json = {**room_json, "proposal": proposal}
        cur.execute(
            "UPDATE sales_rooms SET proposal_json = %s, room_json = %s, updated_at = NOW() WHERE id = %s",
            (Json(proposal), Json(room_json), room_id),
        )
        record_ai_learning_event(
            capability="sales_room.partner_offer",
            event_type="accepted",
            intent="partnership_outreach",
            user_id=user_id,
            business_id=business_id,
            accepted=True,
            edited_before_accept=True,
            prompt_key="veselaya_partner_offer",
            prompt_version=REPAIR_VERSION,
            draft_text=previous_body[:3000],
            final_text=proposal["body_text"][:3000],
            metadata={"room_id": room_id, "lead_id": row.get("lead_id"), "reason": "manual_product_correction"},
            conn=cur.connection,
        )
        return room_id, "repaired"
    room_id = str(uuid.uuid4())
    slug = f"room-{room_id[:12]}"
    preview = {
        "lead_id": row.get("lead_id"),
        "sender_mode": "localos_for_partner",
        "represented_business_id": business_id,
        "represented_business_name": "Весёлая расчёска",
        "decision": {"action": "write_now"},
        "selected_offer": {"id": f"offer-{row.get('workstream_id')}", "text": proposal["body_text"]},
        "selected_trust": {"strategy": "matching_authority"},
    }
    room_json = build_room_preview(
        preview,
        {
            "lead_name": row.get("name"),
            "category": row.get("category"),
            "city": row.get("city"),
            "source_url": row.get("source_url"),
            "client_business_name": "Весёлая расчёска",
        },
    )
    room_json["proposal"] = proposal
    cur.execute(
        """
        INSERT INTO sales_rooms (
            id, slug, business_id, mode, lead_id, workstream_id, data_mode,
            match_json, proposal_json, room_json, status, visibility, created_by,
            created_at, updated_at
        ) VALUES (%s, %s, %s::uuid, 'partner_search', %s, %s, 'outreach_v2',
                  %s, %s, %s, 'prepared', 'private', %s::uuid, NOW(), NOW())
        """,
        (
            room_id, slug, business_id, row.get("lead_id"), row.get("workstream_id"),
            Json(row.get("match_json") if isinstance(row.get("match_json"), dict) else {}),
            Json(proposal), Json(room_json), user_id,
        ),
    )
    create_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=proposal["body_text"],
        author_name="Весёлая расчёска",
        author_contact="",
        metadata={"source": REPAIR_VERSION, "manual_reviewed": True},
    )
    return room_id, "created"


def _create_campaign(
    cur,
    row: dict[str, Any],
    contacts: list[tuple[str, dict[str, Any]]],
    room_id: str | None,
    sender_profile_id: str,
    email_sender_id: str | None,
    user_id: str,
    business_id: str,
    apply_changes: bool,
    force_repair: bool = False,
) -> tuple[str | None, str]:
    latest = _latest_campaign(cur, _text(row.get("workstream_id")))
    if latest.get("status") in BLOCKING_CAMPAIGN_STATES:
        return None, f"blocked_existing_{latest.get('status')}"
    if not force_repair and _campaign_is_current(cur, latest):
        return _text(latest.get("id")), "current"
    if not contacts:
        return None, "needs_contact"
    if not _text(row.get("category")):
        return None, "needs_evidence"
    candidate = _candidate(
        _text(row.get("name")),
        _text(row.get("category")),
        _text(row.get("source_url")),
        _text(row.get("workstream_id")),
    )
    messages = _messages(_text(row.get("name")), _text(row.get("category")))
    days = (0, 3, 7, 12)
    touches: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        channel, contact = contacts[index % len(contacts)]
        channel_status = "permission_required" if channel in {"email", "telegram"} else "manual"
        sender_account_id = email_sender_id if channel == "email" else None
        if channel == "telegram":
            channel_status = "connect_required"
        gate = _manual_gate(message["text"], candidate, channel, message["angle"])
        if not gate.get("passed"):
            raise ValueError(
                f"quality gate failed for {row.get('name')} touch {index}: {gate.get('reason_codes')}"
            )
        strategy = {
            "workstream_type": "client_partnership",
            "sender_mode": "localos_for_partner",
            "represented_business_id": business_id,
            "segment": row.get("category"),
            "signal_kind": "service_compatibility",
            "freshness": "current_snapshot",
            "bridge_type": "audience_and_service_compatibility",
            "offer_id": f"offer-{row.get('workstream_id')}",
            "offer": _offer_summary(_text(row.get("name")), _text(row.get("category"))),
            "trust_strategy": "matching_authority",
            "trust_statement": candidate["trust_statement"],
            "cta": candidate["next_step"],
            "channel": channel,
            "sequence_index": index,
            "day_offset": days[index],
            "angle": message["angle"],
        }
        touches.append({
            "sequence_index": index,
            "channel": channel,
            "contact_point_id": _text(contact.get("id")),
            "sender_account_id": sender_account_id,
            "angle": message["angle"],
            "scheduled_at": datetime.now(timezone.utc) + timedelta(days=days[index]),
            "subject": f"Идея сотрудничества: Весёлая расчёска и {row.get('name')}" if channel == "email" else None,
            "text": message["text"],
            "channel_status": channel_status,
            "quality_gate": gate,
            "strategy": strategy,
            "strategy_fingerprint": strategy_fingerprint(strategy),
        })
    aggregate = _aggregate_quality_gate(touches)
    if not aggregate.get("passed") or int(aggregate.get("total_score") or 0) < 15:
        raise ValueError(f"campaign quality gate failed for {row.get('name')}: {aggregate}")
    if not apply_changes:
        return "dry-run-campaign", "would_create"
    cur.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM outreach_campaigns WHERE workstream_id = %s",
        (row.get("workstream_id"),),
    )
    version = int(dict(cur.fetchone() or {}).get("version") or 1)
    campaign_id = str(uuid.uuid4())
    decision = {
        "schema_version": "outreach-decision-v2",
        "action": "write_now",
        "reason_codes": ["PARTNERSHIP_COMPATIBILITY_CONFIRMED", "MANUAL_PRODUCT_REVIEW"],
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }
    selected_offer = {
        "id": f"offer-{row.get('workstream_id')}",
        "text": _offer_summary(_text(row.get("name")), _text(row.get("category"))),
        "source": _text(row.get("source_url")) or f"localos-doc://partner-card/{row.get('workstream_id')}",
    }
    cur.execute(
        """
        INSERT INTO outreach_campaigns (
            id, workstream_id, lead_id, scope_type, business_id, sender_profile_id,
            version, status, sender_mode, selected_offer_json, trust_strategy,
            decision_snapshot_json, policy_json, recipient_key, room_id, created_by,
            created_at, updated_at
        ) VALUES (%s, %s, %s, 'business', %s, %s::uuid, %s, 'draft',
                  'localos_for_partner', %s, 'matching_authority', %s, %s, %s,
                  %s::uuid, %s, NOW(), NOW())
        """,
        (
            campaign_id, row.get("workstream_id"), row.get("lead_id"), business_id,
            sender_profile_id, version, Json(selected_offer), Json(decision),
            Json({
                "stop_on_reply": True,
                "approval_scope": "whole_sequence",
                "sender_mode": "localos_for_partner",
                "sender_scope_type": "platform",
                "represented_business_id": business_id,
                "represented_business_name": "Весёлая расчёска",
                "generation_source": GENERATION_SOURCE,
            }),
            recipient_key(_text(row.get("lead_id"))), room_id, user_id,
        ),
    )
    for touch in touches:
        brief = {
            "evidence_id": candidate["evidence_id"],
            "source_url": candidate["source_url"],
            "channel_status": touch["channel_status"],
            "observation": candidate["observed_fact"],
            "problem_hypothesis": None,
            "relevance_bridge": candidate["bridge"],
            "generation_source": GENERATION_SOURCE,
            "generation_prompt_version": PROMPT_VERSION,
            "semantic_review_prompt_version": REVIEW_PROMPT_VERSION,
            "generation_rules_version": REPAIR_VERSION,
        }
        cur.execute(
            """
            INSERT INTO outreach_campaign_touches (
                id, campaign_id, sequence_index, channel, contact_point_id,
                sender_account_id, angle_type, scheduled_at, status, subject,
                generated_text, message_brief_json, quality_gate_json,
                strategy_fingerprint, strategy_json, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid,
                      %s, %s, 'draft', %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                str(uuid.uuid4()), campaign_id, touch["sequence_index"], touch["channel"],
                touch["contact_point_id"], touch["sender_account_id"] or "", touch["angle"],
                touch["scheduled_at"], touch["subject"], touch["text"], Json(brief),
                Json(touch["quality_gate"]), touch["strategy_fingerprint"], Json(touch["strategy"]),
            ),
        )
    record_campaign_event(
        cur,
        campaign_id,
        "campaign_preview_created",
        actor_id=user_id,
        payload={"version": version, "touch_count": 4, "source": REPAIR_VERSION},
    )
    if latest and latest.get("status") == "draft":
        cur.execute(
            """
            UPDATE outreach_campaigns
            SET status = 'cancelled', stop_reason = %s, updated_at = NOW()
            WHERE id = %s AND status = 'draft'
            """,
            (f"superseded_by_{REPAIR_VERSION}", latest.get("id")),
        )
    cur.execute("UPDATE sales_rooms SET campaign_id = %s WHERE id = %s", (campaign_id, room_id))
    return campaign_id, "created"


def _record_campaign_learning(cur, business_id: str, user_id: str, apply_changes: bool) -> int:
    cur.execute(
        """
        WITH current_campaigns AS (
            SELECT DISTINCT ON (workstream_id)
                   id, workstream_id, version, lead_id
            FROM outreach_campaigns
            WHERE business_id = %s
              AND status = 'draft'
              AND policy_json->>'generation_source' = %s
              AND EXISTS (
                  SELECT 1
                  FROM outreach_campaign_touches rules_touch
                  WHERE rules_touch.campaign_id = outreach_campaigns.id
                  GROUP BY rules_touch.campaign_id
                  HAVING COUNT(*) = 4
                     AND BOOL_AND(
                         rules_touch.message_brief_json->>'generation_rules_version' = %s
                     )
              )
            ORDER BY workstream_id, version DESC
        )
        SELECT current.id AS current_campaign_id,
               current.lead_id,
               l.name AS lead_name,
               STRING_AGG(previous_touch.generated_text, E'\n\n---\n\n' ORDER BY previous_touch.sequence_index) AS previous_text,
               STRING_AGG(current_touch.generated_text, E'\n\n---\n\n' ORDER BY current_touch.sequence_index) AS current_text
        FROM current_campaigns current
        JOIN prospectingleads l ON l.id = current.lead_id
        JOIN outreach_campaigns previous
          ON previous.workstream_id = current.workstream_id
         AND previous.version = current.version - 1
        JOIN outreach_campaign_touches previous_touch ON previous_touch.campaign_id = previous.id
        JOIN outreach_campaign_touches current_touch
          ON current_touch.campaign_id = current.id
         AND current_touch.sequence_index = previous_touch.sequence_index
        WHERE NOT EXISTS (
            SELECT 1 FROM ailearningevents event
            WHERE event.capability = 'outreach.sequence'
              AND event.metadata_json->>'current_campaign_id' = current.id::text
              AND event.metadata_json->>'rules_version' = %s
        )
        GROUP BY current.id, current.lead_id, l.name
        ORDER BY l.name
        """,
        (business_id, GENERATION_SOURCE, REPAIR_VERSION, REPAIR_VERSION),
    )
    rows = [dict(row) for row in cur.fetchall()]
    if not apply_changes:
        return len(rows)
    recorded = 0
    for row in rows:
        saved = record_ai_learning_event(
            capability="outreach.sequence",
            event_type="accepted",
            intent="partnership_outreach",
            user_id=user_id,
            business_id=business_id,
            accepted=True,
            edited_before_accept=True,
            prompt_key="veselaya_partner_sequence",
            prompt_version=REPAIR_VERSION,
            draft_text=_text(row.get("previous_text"))[:12000],
            final_text=_text(row.get("current_text"))[:12000],
            metadata={
                "lead_id": row.get("lead_id"),
                "lead_name": row.get("lead_name"),
                "current_campaign_id": row.get("current_campaign_id"),
                "rules_version": REPAIR_VERSION,
                "correction_type": "manual_product_correction",
                "negative_patterns": [
                    "LocalOS named in partner-facing copy",
                    "generic partnership offer",
                    "unnatural recipient-name declension",
                    "technical card category copied into recipient message",
                    "recipient benefit missing before CTA",
                ],
            },
            conn=cur.connection,
        )
        if saved:
            recorded += 1
    return recorded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", default=DEFAULT_BUSINESS_ID)
    parser.add_argument("--workstream-id")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.force and not args.workstream_id:
        parser.error("--force requires --workstream-id")

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE COALESCE(is_superadmin, FALSE) = TRUE ORDER BY created_at LIMIT 1"
        )
        user_row = cur.fetchone()
        if not user_row:
            raise RuntimeError("superadmin not found")
        user_id = _text(user_row.get("id"))
        cur.execute(
            """
            SELECT id FROM outreach_sender_profiles
            WHERE workstream_type = 'localos_sales' AND client_business_id IS NULL AND is_active = TRUE
            ORDER BY updated_at DESC LIMIT 1
            """
        )
        profile_row = cur.fetchone()
        if not profile_row:
            raise RuntimeError("platform sender profile not found")
        sender_profile_id = _text(profile_row.get("id"))
        cur.execute(
            """
            SELECT id FROM outreach_sender_accounts
            WHERE channel = 'email' AND LOWER(sender_identity) = LOWER(%s)
              AND scope_type = 'platform' AND status = 'connected'
            ORDER BY updated_at DESC LIMIT 1
            """,
            (PLATFORM_EMAIL,),
        )
        email_row = cur.fetchone()
        email_sender_id = _text(email_row.get("id")) if email_row else None

        contact_repairs = _repair_contacts(cur, args.business_id, args.apply)
        rows = _load_rows(cur, args.business_id)
        if args.workstream_id:
            rows = [row for row in rows if _text(row.get("workstream_id")) == args.workstream_id]
        results: list[dict[str, Any]] = []
        seen_workstreams: set[str] = set()
        for row in rows:
            workstream_id = _text(row.get("workstream_id"))
            if workstream_id in seen_workstreams:
                continue
            seen_workstreams.add(workstream_id)
            status = _normalized(row.get("workstream_status"))
            result: dict[str, Any] = {
                "lead": row.get("name"),
                "lead_id": row.get("lead_id"),
                "workstream_id": workstream_id,
                "status": status,
            }
            if status in TERMINAL_STATES:
                result["outcome"] = "excluded_terminal"
                results.append(result)
                continue
            if _suppressed(cur, args.business_id, _text(row.get("lead_id"))):
                result["outcome"] = "excluded_suppressed"
                results.append(result)
                continue
            category = _text(row.get("category"))
            if not category:
                result["room"] = "needs_evidence"
                result["campaign"] = "needs_evidence"
                result["outcome"] = "needs_evidence"
                results.append(result)
                continue
            proposal = _proposal(_text(row.get("name")), category)
            room_id, room_outcome = _repair_room(
                cur, row, proposal, args.business_id, user_id, args.apply, args.force
            )
            contacts = _choose_contacts(_load_contacts(cur, _text(row.get("lead_id"))), _text(row.get("name")))
            campaign_id, campaign_outcome = _create_campaign(
                cur, row, contacts, room_id, sender_profile_id, email_sender_id,
                user_id, args.business_id, args.apply, args.force,
            )
            result.update({
                "room": room_outcome,
                "room_id": room_id,
                "campaign": campaign_outcome,
                "campaign_id": campaign_id,
                "channels": [channel for channel, _contact in contacts],
                "outcome": campaign_outcome,
            })
            results.append(result)

        learning_events = _record_campaign_learning(cur, args.business_id, user_id, args.apply)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        summary: dict[str, int] = {}
        for item in results:
            key = _text(item.get("outcome")) or "unknown"
            summary[key] = summary.get(key, 0) + 1
        print(json.dumps({
            "dry_run": not args.apply,
            "business_id": args.business_id,
            "workstreams": len(results),
            "contact_repairs": contact_repairs,
            "learning_events": learning_events,
            "summary": summary,
            "results": results,
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
