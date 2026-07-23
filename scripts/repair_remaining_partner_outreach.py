#!/usr/bin/env python3
"""Prepare evidence-bound partner rooms and draft sequences for Novamed, Oliver and Shansik."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate_path in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate_path not in sys.path:
        sys.path.insert(0, candidate_path)

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
from scripts.repair_veselaya_partner_outreach import (  # noqa: E402
    _choose_contacts,
    _load_contacts,
    _load_rows,
    _normalized,
    _suppressed,
    _text,
)


PLATFORM_EMAIL = "localosgo@gmail.com"
GENERATION_SOURCE = "manual_product_correction"
REPAIR_VERSION = "remaining_partner_rules_v2"
TERMINAL_STATES = {
    "replied", "converted", "closed_lost", "not_relevant", "suppressed",
    "unsubscribed", "hard_no", "closed", "won", "lost", "archived",
}
BLOCKING_CAMPAIGN_STATES = {"approved", "active", "paused"}

BUSINESSES: dict[str, dict[str, str]] = {
    "38a11c0e-6eea-4fdc-90d6-66f21af9adce": {
        "policy": "novamed",
        "name": "Новамед",
        "genitive": "Новамеда",
        "voice": "медицинский центр и косметология Новамед на Лукинской улице",
        "address": "Москва, Лукинская улица, 16",
    },
    "533c1300-8a54-43a8-aa1f-69a8ed9c24ba": {
        "policy": "oliver",
        "name": "Оливер",
        "genitive": "Оливера",
        "voice": "салон красоты Оливер на улице Савушкина",
        "address": "Санкт-Петербург, улица Савушкина, 127",
    },
    "17ff72b6-a542-5fac-b67c-f710ee4fc828": {
        "policy": "shansik",
        "name": "Шансик",
        "genitive": "Шансика",
        "voice": "детская танцевальная студия Шансик на улице Радищева",
        "address": "Санкт-Петербург, Пушкин, улица Радищева, 22",
    },
    "46bb9a2f-bd03-5930-9644-76315016d471": {
        "policy": "shansik",
        "name": "Шансик",
        "genitive": "Шансика",
        "voice": "детская танцевальная студия Шансик на Кедринской улице",
        "address": "Санкт-Петербург, Пушкин, Кедринская улица, 12",
    },
    "12c19fd1-e1a3-51f5-9980-eb75f0a5234a": {
        "policy": "shansik",
        "name": "Шансик",
        "genitive": "Шансика",
        "voice": "детская танцевальная студия Шансик на Церковной улице",
        "address": "Санкт-Петербург, Пушкин, Церковная улица, 27",
    },
    "72e5811d-bdda-5ec7-ad74-5f728fb6c11d": {
        "policy": "shansik",
        "name": "Шансик",
        "genitive": "Шансика",
        "voice": "детская танцевальная студия Шансик на Новоизмайловском проспекте",
        "address": "Санкт-Петербург, Новоизмайловский проспект, 101",
    },
}


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _recipient_kind(policy: str, name: str, category: str) -> str:
    value = f"{_normalized(name)} {_normalized(category)}"
    if policy == "novamed":
        if "жилой комплекс" in value:
            return "residential"
        if "агентство недвижимости" in value:
            return "real_estate"
        if any(token in value for token in (
            "детск", "образован", "курс", "мастер-класс", "музыкальн",
            "творческ", "ментальн", "школ",
        )) and not any(token in value for token in ("клиник", "стомат", "поликлиник")):
            return "family_education"
        if any(token in value for token in ("фитнес", "спортивн", "тренаж")):
            return "fitness_team"
        return "observe"
    if policy == "oliver":
        if "жилой комплекс" in value:
            return "residential"
        if "стомат" in value:
            return "dental_team"
        if "магазин парфюмерии и косметики" in value:
            return "beauty_retail"
        if any(token in value for token in ("фитнес", "спортивн", "тренаж")):
            return "fitness"
        if any(token in value for token in ("фотоуслуг", "фотостуд")):
            return "photo"
        if any(token in value for token in ("организация мероприятий", "товары для праздника", "пиротех")):
            return "event"
        return "observe"
    if any(token in value for token in (
        "стомат", "поликлиник", "психиатр", "социальная реабилитация",
    )):
        return "observe"
    if "школа танцев" in value:
        return "observe"
    if any(token in value for token in ("фотоуслуг", "фотостуд", "видеосъём")):
        return "photo"
    if any(token in value for token in (
        "детский сад", "центр развития", "клуб для детей", "частная школа",
        "дополнительное образование", "музыкальное образование", "курсы иностранных",
        "логопед", "дефектолог", "культурный центр", "клуб досуга", "мастер-класс",
    )):
        return "child_education"
    if any(token in value for token in (
        "детский магазин", "детские игрушки", "детской одежды", "будущих мам",
        "детские коляски", "канцтовар", "спортивная одежда",
    )):
        return "child_retail"
    if any(token in value for token in ("спортивн", "фитнес", "велотрек", "роллердром")):
        return "sport"
    if any(token in value for token in ("организация мероприятий", "детских праздников", "банкетный зал")):
        return "family_event"
    return "observe"


def _offer(policy: str, kind: str, name: str) -> dict[str, str]:
    offers: dict[tuple[str, str], dict[str, str]] = {
        ("novamed", "residential"): {
            "summary": f"предложить жителям {name} специальные условия на выбранные услуги Новамеда",
            "opening": f"Хотим предложить жителям {name} специальные условия на выбранные услуги Новамеда.",
            "implementation": f"Новамед может подготовить для {name} короткий текст с перечнем услуг и условиями для жителей. Размещение согласуем заранее.",
            "third": "Можно начать с одного понятного предложения для жителей и оценить интерес без передачи контактов.",
        },
        ("novamed", "real_estate"): {
            "summary": f"подготовить для клиентов {name} локальное предложение на услуги Новамеда",
            "opening": f"Хотим предложить клиентам {name}, которые живут или переезжают в район, специальные условия на выбранные услуги Новамеда.",
            "implementation": f"Новамед может подготовить для {name} короткую памятку о медицинских и косметологических услугах рядом. Конкретные условия согласуем заранее.",
            "third": "Можно начать с одного предложения для новых жителей района без передачи персональных данных.",
        },
        ("novamed", "family_education"): {
            "summary": f"предложить родителям и сотрудникам {name} специальные условия на выбранные услуги Новамеда",
            "opening": f"Хотим предложить родителям и сотрудникам {name} специальные условия на выбранные услуги Новамеда рядом.",
            "implementation": f"Новамед может подготовить для {name} короткий текст с перечнем услуг и условиями. Никаких медицинских рекомендаций от вашей команды не потребуется.",
            "third": "Можно начать с одного предложения и опубликовать его только после согласования текста и условий.",
        },
        ("novamed", "fitness_team"): {
            "summary": f"предложить сотрудникам {name} специальные условия на выбранные услуги Новамеда",
            "opening": f"Хотим предложить сотрудникам {name} специальные условия на выбранные услуги Новамеда рядом.",
            "implementation": f"Новамед может подготовить для команды {name} короткий перечень услуг и условия. Это предложение только для сотрудников, без рекомендаций клиентам клуба.",
            "third": "Можно начать с одного предложения для команды и оценить интерес без обмена клиентскими контактами.",
        },
        ("oliver", "residential"): {
            "summary": f"предложить жителям {name} особые условия на услуги салона Оливер",
            "opening": f"Хотим предложить жителям {name} особые условия на услуги салона Оливер рядом.",
            "implementation": f"Оливер может подготовить для {name} короткий текст и макет для каналов ЖК или общих зон. Условия и размещение согласуем заранее.",
            "third": "Можно начать с одного предложения для жителей: стрижка, маникюр или массаж на выбор.",
        },
        ("oliver", "dental_team"): {
            "summary": f"предложить сотрудникам {name} услуги салона Оливер рядом с работой",
            "opening": f"Хотим предложить сотрудникам {name} услуги салона Оливер рядом с работой: стрижки, маникюр или массаж.",
            "implementation": f"Оливер может подготовить для команды {name} короткое предложение для внутреннего канала. Речь только о сотрудниках, без рекомендаций пациентам.",
            "third": "Можно начать с одного предложения для команды и заранее согласовать текст и условия.",
        },
        ("oliver", "beauty_retail"): {
            "summary": f"собрать с {name} полезный материал о домашнем и профессиональном уходе",
            "opening": f"У {name} есть товары для домашнего ухода, а Оливер оказывает профессиональные услуги. Предлагаем собрать короткий полезный материал для общей аудитории.",
            "implementation": f"Оливер может вместе с {name} подготовить памятку: когда достаточно домашнего ухода, а когда стоит записаться к мастеру.",
            "third": "Можно выбрать одну тему - волосы, ногти или уход за лицом - и проверить интерес аудитории.",
        },
        ("oliver", "fitness"): {
            "summary": f"предложить клиентам {name} массаж и уход после тренировок",
            "opening": f"В Оливере есть массаж и уходовые услуги. Хотим предложить клиентам {name} удобный формат восстановления после тренировок.",
            "implementation": f"Оливер может подготовить для {name} короткое предложение о массаже рядом. Текст и условия согласуем заранее.",
            "third": "Можно начать с одного формата - расслабляющего массажа после тренировок - и оценить интерес.",
        },
        ("oliver", "photo"): {
            "summary": f"предложить клиентам {name} макияж и укладку перед съёмкой",
            "opening": f"В Оливере можно сделать макияж и укладку перед съёмкой. Хотим предложить клиентам {name} удобный совместный формат.",
            "implementation": f"Оливер может подготовить для {name} короткое предложение о макияже и укладке перед фотосессией. Условия согласуем заранее.",
            "third": "Можно начать с одного пакета подготовки к съёмке и проверить интерес без сложной интеграции.",
        },
        ("oliver", "event"): {
            "summary": f"предложить клиентам {name} макияж и укладку перед событием",
            "opening": f"В Оливере можно сделать макияж и укладку перед праздником. Хотим предложить клиентам {name} понятный совместный формат подготовки к событию.",
            "implementation": f"Оливер может подготовить для {name} короткий текст о макияже и укладке перед мероприятием. Условия согласуем заранее.",
            "third": "Можно начать с одного сценария подготовки к празднику и оценить интерес клиентов.",
        },
        ("shansik", "child_education"): {
            "summary": f"пригласить детей из {name} на пробное занятие по танцам и акробатике",
            "opening": f"Хотим пригласить детей из {name} на пробное занятие по танцам и акробатике в Шансике.",
            "implementation": f"Шансик может подготовить для родителей из {name} короткое приглашение и отдельно обсудить выездной танцевальный мастер-класс.",
            "third": "Можно начать с одного пробного занятия или небольшого мастер-класса для детей.",
        },
        ("shansik", "child_retail"): {
            "summary": f"предложить семьям, которые приходят в {name}, пробное занятие в Шансике",
            "opening": f"Хотим предложить семьям, которые приходят в {name}, пробное занятие по танцам и акробатике в Шансике.",
            "implementation": f"Шансик может подготовить для {name} короткое приглашение для родителей. Текст, макет и условия согласуем заранее.",
            "third": "Можно начать с одного предложения для семей и оценить интерес без передачи контактов.",
        },
        ("shansik", "photo"): {
            "summary": f"обсудить с {name} танцевальную фотосессию для учеников Шансика",
            "opening": f"Хотим обсудить с {name} танцевальную фотосессию для учеников Шансика.",
            "implementation": f"Шансик может собрать одну группу, а {name} - предложить формат съёмки. Все условия для родителей согласуем заранее.",
            "third": "Можно начать с одной небольшой съёмки и посмотреть, интересен ли формат семьям.",
        },
        ("shansik", "sport"): {
            "summary": f"провести с {name} совместное открытое занятие для детей",
            "opening": f"Хотим предложить {name} совместное открытое занятие для детей: соединить ваш спортивный формат с танцами или акробатикой Шансика.",
            "implementation": f"Шансик может подготовить короткий сценарий совместного занятия с {name}. Возраст, нагрузку и роли тренеров согласуем заранее.",
            "third": "Можно начать с одного открытого занятия без абонементов и обязательств для семей.",
        },
        ("shansik", "family_event"): {
            "summary": f"провести танцевальный мастер-класс на семейном событии {name}",
            "opening": f"Хотим предложить небольшой танцевальный мастер-класс для семейного события в {name}.",
            "implementation": f"Шансик может подготовить короткую программу для детей, а с {name} заранее согласовать площадку, возраст и длительность.",
            "third": "Можно начать с одного мастер-класса и оценить отклик семей.",
        },
    }
    return offers.get((policy, kind), {
        "summary": "нужен подтверждённый формат сотрудничества",
        "opening": "",
        "implementation": "",
        "third": "",
    })


def _proposal(config: dict[str, str], name: str, category: str) -> dict[str, Any]:
    kind = _recipient_kind(config["policy"], name, category)
    offer = _offer(config["policy"], kind, name)
    if kind == "observe":
        return {
            "title": "Нужна проверка предложения",
            "body_text": (
                "Конкретное предложение пока не готовим. По имеющимся публичным данным не найден "
                "достаточно сильный и безопасный формат сотрудничества. Нужен дополнительный факт "
                "или ручное решение до подготовки сообщения."
            ),
            "status": "needs_evidence",
            "source": REPAIR_VERSION,
            "recipient_kind": kind,
        }
    return {
        "title": "Идея сотрудничества",
        "body_text": (
            f"Мы ваши соседи - {config['voice']}.\n\n"
            f"{offer['opening']}\n\n{offer['implementation']}\n\n"
            "Если идея подходит, сначала согласуем один простой формат и только потом подготовим материалы."
        ),
        "status": "draft",
        "source": REPAIR_VERSION,
        "recipient_kind": kind,
    }


def _messages(config: dict[str, str], name: str, category: str) -> list[dict[str, str]]:
    kind = _recipient_kind(config["policy"], name, category)
    if kind == "observe":
        return []
    offer = _offer(config["policy"], kind, name)
    third_detail = offer["third"]
    if third_detail.startswith("Можно начать"):
        third = f"{config['name']} предлагает {name} начать{third_detail[len('Можно начать') :]}"
    else:
        third = f"{config['name']} предлагает {name}: {third_detail[0].lower()}{third_detail[1:]}"
    return [
        {
            "angle": "signal",
            "text": (
                f"Здравствуйте! Мы ваши соседи - {config['voice']}. {offer['opening']} "
                "Не подскажете, с кем можно обсудить детали?"
            ),
        },
        {"angle": "matching_authority", "text": f"Здравствуйте! {offer['implementation']} Показать готовый вариант?"},
        {"angle": "proof", "text": f"Здравствуйте! {third} Прислать короткий план?"},
        {
            "angle": "respectful_close",
            "text": (
                f"Здравствуйте! Не хотим отвлекать команду {name}. Если предложение от {config['genitive']} "
                "сейчас неактуально, больше писать не будем. Вернуться к нему позже?"
            ),
        },
    ]


def _candidate(config: dict[str, str], row: dict[str, Any]) -> dict[str, Any]:
    name = _text(row.get("name"))
    category = _text(row.get("category"))
    kind = _recipient_kind(config["policy"], name, category)
    offer = _offer(config["policy"], kind, name)
    source_url = _text(row.get("source_url")) or f"localos-doc://partner-card/{row.get('workstream_id')}"
    return {
        "id": f"partner-{row.get('workstream_id')}",
        "evidence_id": f"partner-{row.get('workstream_id')}",
        "evidence_kind": "service_compatibility",
        "evidence_status": "observed",
        "observed_fact": f"В публичной карточке {name} указана категория: {category}.",
        "bridge": offer["summary"],
        "relevance_to_offer": offer["summary"],
        "trust_statement": config["name"],
        "source_url": source_url,
        "source_type": "public_business_card",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "freshness": "current_snapshot",
        "confidence": 0.9,
        "recipient": name,
        "next_step": "Уточнить ответственного и обсудить один конкретный формат",
    }


def _manual_gate(text_value: str, candidate: dict[str, Any], channel: str, angle: str) -> dict[str, Any]:
    gate = _quality_gate(
        text_value,
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


def _latest_campaign(cur, workstream_id: str) -> dict[str, Any]:
    cur.execute(
        "SELECT * FROM outreach_campaigns WHERE workstream_id=%s ORDER BY version DESC,created_at DESC LIMIT 1",
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
               BOOL_AND(message_brief_json->>'generation_rules_version'=%s) AS current_rules,
               BOOL_AND(COALESCE((quality_gate_json->>'passed')::boolean,FALSE)) AS quality_passed
        FROM outreach_campaign_touches WHERE campaign_id=%s
        """,
        (REPAIR_VERSION, campaign.get("id")),
    )
    row = dict(cur.fetchone() or {})
    return int(row.get("count") or 0) == 4 and bool(row.get("current_rules")) and bool(row.get("quality_passed"))


def _repair_room(
    cur,
    row: dict[str, Any],
    config: dict[str, str],
    proposal: dict[str, Any],
    business_id: str,
    user_id: str,
    apply_changes: bool,
    force_repair: bool,
) -> tuple[str | None, str]:
    room_id = _text(row.get("room_id"))
    previous = row.get("proposal_json") if isinstance(row.get("proposal_json"), dict) else {}
    previous_body = _text(previous.get("body_text"))
    if room_id and not force_repair and previous.get("source") == REPAIR_VERSION and previous_body == proposal["body_text"]:
        return room_id, "current"
    if not apply_changes:
        return room_id or "dry-run-new-room", "would_repair" if room_id else "would_create"
    if room_id:
        ensure_sales_room_proposal_version(
            cur,
            room_id=room_id,
            body_text=previous_body,
            author_name=config["name"],
            metadata={"source": f"existing_before_{REPAIR_VERSION}"},
        )
        create_sales_room_proposal_version(
            cur,
            room_id=room_id,
            body_text=proposal["body_text"],
            author_name=config["name"],
            author_contact="",
            metadata={"source": REPAIR_VERSION, "manual_reviewed": True},
        )
        room_json = row.get("room_json") if isinstance(row.get("room_json"), dict) else {}
        room_json = {**room_json, "proposal": proposal}
        cur.execute(
            "UPDATE sales_rooms SET proposal_json=%s,room_json=%s,updated_at=NOW() WHERE id=%s",
            (Json(proposal), Json(room_json), room_id),
        )
        outcome = "needs_evidence" if proposal["status"] == "needs_evidence" else "repaired"
    else:
        room_id = str(uuid.uuid4())
        slug = f"room-{room_id[:12]}"
        preview = {
            "lead_id": row.get("lead_id"),
            "sender_mode": "localos_for_partner",
            "represented_business_id": business_id,
            "represented_business_name": config["name"],
            "decision": {"action": "needs_evidence" if proposal["status"] == "needs_evidence" else "write_now"},
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
                "client_business_name": config["name"],
            },
        )
        room_json["proposal"] = proposal
        cur.execute(
            """
            INSERT INTO sales_rooms (
                id,slug,business_id,mode,lead_id,workstream_id,data_mode,match_json,
                proposal_json,room_json,status,visibility,created_by,created_at,updated_at
            ) VALUES (%s,%s,%s::uuid,'partner_search',%s,%s,'outreach_v2',%s,%s,%s,
                      'prepared','private',%s::uuid,NOW(),NOW())
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
            author_name=config["name"],
            author_contact="",
            metadata={"source": REPAIR_VERSION, "manual_reviewed": True},
        )
        outcome = "needs_evidence" if proposal["status"] == "needs_evidence" else "created"
    record_ai_learning_event(
        capability="sales_room.partner_offer",
        event_type="rejected" if proposal["status"] == "needs_evidence" else "accepted",
        intent="partnership_outreach",
        user_id=user_id,
        business_id=business_id,
        accepted=proposal["status"] != "needs_evidence",
        rejected=proposal["status"] == "needs_evidence",
        edited_before_accept=True,
        outcome="needs_evidence" if proposal["status"] == "needs_evidence" else "draft_rewritten",
        prompt_key=f"{config['policy']}_partner_offer",
        prompt_version=REPAIR_VERSION,
        draft_text=previous_body[:6000],
        final_text=proposal["body_text"][:6000],
        metadata={"room_id": room_id, "lead_id": row.get("lead_id"), "recipient_kind": proposal["recipient_kind"]},
        conn=cur.connection,
    )
    return room_id, outcome


def _create_campaign(
    cur,
    row: dict[str, Any],
    config: dict[str, str],
    contacts: list[tuple[str, dict[str, Any]]],
    room_id: str | None,
    sender_profile_id: str,
    represented_profile_id: str | None,
    email_sender_id: str | None,
    user_id: str,
    business_id: str,
    apply_changes: bool,
    force_repair: bool,
) -> tuple[str | None, str]:
    name = _text(row.get("name"))
    category = _text(row.get("category"))
    kind = _recipient_kind(config["policy"], name, category)
    if kind == "observe":
        latest = _latest_campaign(cur, _text(row.get("workstream_id")))
        if latest.get("status") in BLOCKING_CAMPAIGN_STATES:
            return None, f"blocked_existing_{latest.get('status')}"
        if apply_changes and latest.get("status") == "draft":
            cur.execute(
                """
                UPDATE outreach_campaigns
                SET status='cancelled',stop_reason=%s,updated_at=NOW()
                WHERE id=%s AND status='draft'
                """,
                (f"needs_evidence_by_{REPAIR_VERSION}", latest.get("id")),
            )
        return None, "needs_evidence"
    latest = _latest_campaign(cur, _text(row.get("workstream_id")))
    if latest.get("status") in BLOCKING_CAMPAIGN_STATES:
        return None, f"blocked_existing_{latest.get('status')}"
    if not force_repair and _campaign_is_current(cur, latest):
        return _text(latest.get("id")), "current"
    if not contacts:
        return None, "needs_contact"
    if not room_id:
        return None, "needs_room"
    candidate = _candidate(config, row)
    messages = _messages(config, name, category)
    touches: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        channel, contact = contacts[index % len(contacts)]
        channel_status = "permission_required" if channel in {"email", "telegram"} else "manual"
        sender_account_id = email_sender_id if channel == "email" else None
        if channel == "telegram":
            channel_status = "connect_required"
        gate = _manual_gate(message["text"], candidate, channel, message["angle"])
        if not gate.get("passed"):
            raise ValueError(f"quality gate failed for {name} touch {index}: {gate.get('reason_codes')}")
        strategy = {
            "workstream_type": "client_partnership",
            "sender_mode": "localos_for_partner",
            "represented_business_id": business_id,
            "segment": kind,
            "signal_kind": "service_compatibility",
            "freshness": "current_snapshot",
            "bridge_type": "audience_and_service_compatibility",
            "offer_id": f"offer-{row.get('workstream_id')}",
            "offer": _offer(config["policy"], kind, name)["summary"],
            "trust_strategy": "business_reputation",
            "trust_statement": config["name"],
            "cta": candidate["next_step"],
            "channel": channel,
            "sequence_index": index,
            "day_offset": (0, 3, 7, 12)[index],
            "angle": message["angle"],
        }
        touches.append({
            "sequence_index": index,
            "channel": channel,
            "contact_point_id": _text(contact.get("id")),
            "sender_account_id": sender_account_id,
            "angle": message["angle"],
            "scheduled_at": datetime.now(timezone.utc) + timedelta(days=(0, 3, 7, 12)[index]),
            "subject": f"Идея сотрудничества: {config['name']} и {name}" if channel == "email" else None,
            "text": message["text"],
            "channel_status": channel_status,
            "quality_gate": gate,
            "strategy": strategy,
            "strategy_fingerprint": strategy_fingerprint(strategy),
        })
    aggregate = _aggregate_quality_gate(touches)
    if not aggregate.get("passed") or int(aggregate.get("total_score") or 0) < 15:
        raise ValueError(f"campaign quality gate failed for {name}: {aggregate}")
    if not apply_changes:
        return "dry-run-campaign", "would_create"
    previous_text = ""
    if latest:
        cur.execute(
            "SELECT STRING_AGG(generated_text,E'\n\n---\n\n' ORDER BY sequence_index) AS text FROM outreach_campaign_touches WHERE campaign_id=%s",
            (latest.get("id"),),
        )
        previous_text = _text(dict(cur.fetchone() or {}).get("text"))
    cur.execute(
        "SELECT COALESCE(MAX(version),0)+1 AS version FROM outreach_campaigns WHERE workstream_id=%s",
        (row.get("workstream_id"),),
    )
    version = int(dict(cur.fetchone() or {}).get("version") or 1)
    campaign_id = str(uuid.uuid4())
    offer_summary = _offer(config["policy"], kind, name)["summary"]
    decision = {
        "schema_version": "outreach-decision-v2",
        "action": "write_now",
        "reason_codes": ["PARTNERSHIP_COMPATIBILITY_CONFIRMED", "MANUAL_PRODUCT_REVIEW"],
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }
    policy_json: dict[str, Any] = {
        "stop_on_reply": True,
        "approval_scope": "whole_sequence",
        "sender_mode": "localos_for_partner",
        "sender_scope_type": "platform",
        "represented_business_id": business_id,
        "represented_business_name": config["name"],
        "generation_source": GENERATION_SOURCE,
    }
    if represented_profile_id:
        policy_json["represented_sender_profile_id"] = represented_profile_id
    cur.execute(
        """
        INSERT INTO outreach_campaigns (
            id,workstream_id,lead_id,scope_type,business_id,sender_profile_id,version,status,
            sender_mode,selected_offer_json,trust_strategy,decision_snapshot_json,policy_json,
            recipient_key,room_id,created_by,created_at,updated_at
        ) VALUES (%s,%s,%s,'business',%s,%s::uuid,%s,'draft','localos_for_partner',%s,
                  'business_reputation',%s,%s,%s,%s::uuid,%s,NOW(),NOW())
        """,
        (
            campaign_id, row.get("workstream_id"), row.get("lead_id"), business_id,
            sender_profile_id, version,
            Json({"id": f"offer-{row.get('workstream_id')}", "text": offer_summary, "source": candidate["source_url"]}),
            Json(decision), Json(policy_json), recipient_key(_text(row.get("lead_id"))), room_id, user_id,
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
                id,campaign_id,sequence_index,channel,contact_point_id,sender_account_id,
                angle_type,scheduled_at,status,subject,generated_text,message_brief_json,
                quality_gate_json,strategy_fingerprint,strategy_json,created_at,updated_at
            ) VALUES (%s,%s,%s,%s,NULLIF(%s,'')::uuid,NULLIF(%s,'')::uuid,%s,%s,'draft',
                      %s,%s,%s,%s,%s,%s,NOW(),NOW())
            """,
            (
                str(uuid.uuid4()), campaign_id, touch["sequence_index"], touch["channel"],
                touch["contact_point_id"], touch["sender_account_id"] or "", touch["angle"],
                touch["scheduled_at"], touch["subject"], touch["text"], Json(brief),
                Json(touch["quality_gate"]), touch["strategy_fingerprint"], Json(touch["strategy"]),
            ),
        )
    record_campaign_event(
        cur, campaign_id, "campaign_preview_created", actor_id=user_id,
        payload={"version": version, "touch_count": 4, "source": REPAIR_VERSION},
    )
    if latest and latest.get("status") == "draft":
        cur.execute(
            "UPDATE outreach_campaigns SET status='cancelled',stop_reason=%s,updated_at=NOW() WHERE id=%s AND status='draft'",
            (f"superseded_by_{REPAIR_VERSION}", latest.get("id")),
        )
    cur.execute("UPDATE sales_rooms SET campaign_id=%s WHERE id=%s", (campaign_id, room_id))
    final_text = "\n\n---\n\n".join(touch["text"] for touch in touches)
    record_ai_learning_event(
        capability="outreach.sequence",
        event_type="accepted",
        intent="partnership_outreach",
        user_id=user_id,
        business_id=business_id,
        accepted=True,
        edited_before_accept=True,
        outcome="draft_rewritten",
        prompt_key=f"{config['policy']}_partner_sequence",
        prompt_version=REPAIR_VERSION,
        draft_text=previous_text[:12000],
        final_text=final_text[:12000],
        metadata={
            "lead_id": row.get("lead_id"), "lead_name": name,
            "current_campaign_id": campaign_id, "rules_version": REPAIR_VERSION,
            "recipient_kind": kind, "correction_type": "manual_product_correction",
        },
        conn=cur.connection,
    )
    return campaign_id, "created"


def _sender_context(cur, business_id: str) -> tuple[str, str | None, str | None, str]:
    cur.execute("SELECT id FROM users WHERE COALESCE(is_superadmin,FALSE)=TRUE ORDER BY created_at LIMIT 1")
    user = cur.fetchone()
    if not user:
        raise RuntimeError("superadmin not found")
    user_id = _text(user.get("id"))
    cur.execute(
        """
        SELECT id FROM outreach_sender_profiles
        WHERE workstream_type='localos_sales' AND client_business_id IS NULL AND is_active=TRUE
        ORDER BY updated_at DESC LIMIT 1
        """
    )
    platform = cur.fetchone()
    if not platform:
        raise RuntimeError("platform sender profile not found")
    cur.execute(
        """
        SELECT id FROM outreach_sender_profiles
        WHERE client_business_id=%s AND workstream_type='client_partnership' AND is_active=TRUE
        ORDER BY updated_at DESC LIMIT 1
        """,
        (business_id,),
    )
    represented = cur.fetchone()
    cur.execute(
        """
        SELECT id FROM outreach_sender_accounts
        WHERE channel='email' AND LOWER(sender_identity)=LOWER(%s)
          AND scope_type='platform' AND status='connected'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (PLATFORM_EMAIL,),
    )
    email = cur.fetchone()
    return (
        _text(platform.get("id")),
        _text(represented.get("id")) if represented else None,
        _text(email.get("id")) if email else None,
        user_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", required=True, choices=sorted(BUSINESSES))
    parser.add_argument("--workstream-id")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.force and not args.workstream_id:
        parser.error("--force requires --workstream-id")
    business_id = args.business_id
    config = BUSINESSES[business_id]
    conn = _connect()
    try:
        cur = conn.cursor()
        sender_profile_id, represented_profile_id, email_sender_id, user_id = _sender_context(cur, business_id)
        rows = _load_rows(cur, business_id)
        if args.workstream_id:
            rows = [row for row in rows if _text(row.get("workstream_id")) == args.workstream_id]
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            workstream_id = _text(row.get("workstream_id"))
            if workstream_id in seen:
                continue
            seen.add(workstream_id)
            status = _normalized(row.get("workstream_status"))
            kind = _recipient_kind(config["policy"], _text(row.get("name")), _text(row.get("category")))
            result: dict[str, Any] = {
                "lead": row.get("name"), "lead_id": row.get("lead_id"),
                "workstream_id": workstream_id, "recipient_kind": kind, "status": status,
            }
            if status in TERMINAL_STATES:
                result["outcome"] = "excluded_terminal"
                results.append(result)
                continue
            if _suppressed(cur, business_id, _text(row.get("lead_id"))):
                result["outcome"] = "excluded_suppressed"
                results.append(result)
                continue
            proposal = _proposal(config, _text(row.get("name")), _text(row.get("category")))
            room_id, room_outcome = _repair_room(
                cur, row, config, proposal, business_id, user_id, args.apply, args.force,
            )
            contacts = _choose_contacts(_load_contacts(cur, _text(row.get("lead_id"))), _text(row.get("name")))
            campaign_id, campaign_outcome = _create_campaign(
                cur, row, config, contacts, room_id, sender_profile_id,
                represented_profile_id, email_sender_id, user_id, business_id,
                args.apply, args.force,
            )
            result.update({
                "room": room_outcome, "room_id": room_id,
                "campaign": campaign_outcome, "campaign_id": campaign_id,
                "channels": [channel for channel, _contact in contacts],
                "outcome": campaign_outcome,
            })
            results.append(result)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        summary: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        for item in results:
            outcome = _text(item.get("outcome")) or "unknown"
            kind = _text(item.get("recipient_kind")) or "unknown"
            summary[outcome] = summary.get(outcome, 0) + 1
            by_kind[kind] = by_kind.get(kind, 0) + 1
        print(json.dumps({
            "dry_run": not args.apply,
            "business_id": business_id,
            "business": config["name"],
            "workstreams": len(results),
            "summary": summary,
            "by_kind": by_kind,
            "results": results,
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
