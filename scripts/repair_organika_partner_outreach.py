#!/usr/bin/env python3
"""Rewrite Organika partner rooms and campaign drafts with concrete business offers."""

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


DEFAULT_BUSINESS_ID = "360b90ef-cf2b-4eb4-acd4-a8524e4600ae"
BUSINESS_NAME = "Органика"
BUSINESS_DESCRIPTION = "салон красоты и косметология Органика на проспекте Испытателей"
PLATFORM_EMAIL = "localosgo@gmail.com"
GENERATION_SOURCE = "manual_product_correction"
REPAIR_VERSION = "organika_partner_rules_v1"
TERMINAL_STATES = {
    "replied", "converted", "closed_lost", "not_relevant", "suppressed",
    "unsubscribed", "hard_no", "closed", "won", "lost", "archived",
}
BLOCKING_CAMPAIGN_STATES = {"approved", "active", "paused"}
OBSERVE_NAMES = {
    "borneo beauty",
    "naomi",
    "лак",
    "детский развлекательный автомат",
    "детский этаж трк «атмосфера»",
    "miller center: медицинские арендаторы",
    "мастерская по ремонту обуви",
    "мастерская по ремонту часов",
}


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _recipient_kind(name: str, category: str) -> str:
    normalized_name = _normalized(name)
    value = f"{normalized_name} {_normalized(category)}"
    if normalized_name in OBSERVE_NAMES:
        return "observe"
    if any(token in value for token in ("стомат", "медицин", "медцентр", "клиник")):
        return "medical_team"
    if (
        ("детск" in value and any(token in value for token in ("одежд", "магазин", "товар", "игруш", "обув")))
        or "товары для детей" in value
    ):
        return "child_retail"
    if any(token in value for token in (
        "центр развития", "дополнительное образование", "курсы иностранных языков",
        "обучение", "школ", "клуб для детей",
    )):
        return "child_education"
    if any(token in value for token in (
        "детская игротека", "детские развлечения", "детский театр", "семейный развлекательный",
        "кинотеатр", "досуг",
    )):
        return "family_entertainment"
    if any(token in value for token in ("магазин парфюмерии", "магазин косметики", "beauty/retail")):
        return "beauty_retail"
    if any(token in value for token in ("фитнес", "спортивн", "бассейн", "спортивное питание")):
        return "fitness"
    if any(token in value for token in ("туристическ", "турагент")):
        return "travel"
    if any(token in value for token in ("торгово-развлекательный", "торговый комплекс")):
        return "shopping_center"
    if any(token in value for token in ("бизнес-центр", "банк", "страховая компания")):
        return "employee_benefit"
    return "observe"


def _offer_data(name: str, category: str) -> dict[str, str]:
    kind = _recipient_kind(name, category)
    offers = {
        "child_education": {
            "summary": f"предложить семьям, которые ходят в {name}, детские стрижки, укладки и плетение перед событиями",
            "opening": (
                "У нас есть детские стрижки, укладки и плетение. "
                f"Хотим предложить семьям, которые ходят в {name}, полезный формат перед праздниками и выступлениями."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для родителей, чьи дети ходят в {name}, короткий текст о детских стрижках, "
                "укладках и плетении. Материал согласуем до публикации."
            ),
            "third": (
                f"Для детей, которые ходят в {name}, мы из салона Органика можем предложить два сценария: обычная детская стрижка "
                "или укладка и плетение перед событием."
            ),
        },
        "child_retail": {
            "summary": f"собрать для семей, которые покупают детские товары в {name}, сценарий подготовки ребёнка к событию",
            "opening": (
                f"{name} работает с товарами для детей, а у нас есть детские стрижки, укладки и плетение. "
                "Предлагаем связать это в один понятный сценарий перед праздником или фотосессией."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для {name} короткий материал: детский образ складывается из "
                "одежды и аккуратной стрижки или укладки. Текст и макет согласуем заранее."
            ),
            "third": (
                f"Для семей, которые приходят в {name}, мы из салона Органика можем предложить выбор между детской стрижкой и укладкой "
                "с плетением перед праздником."
            ),
        },
        "family_entertainment": {
            "summary": f"предложить семьям, которые приходят в {name}, детские укладки и плетение перед событием",
            "opening": (
                f"У нас есть детские стрижки, укладки и плетение. Хотим предложить семьям, которые приходят в {name}, "
                "полезный формат перед праздниками и семейными событиями."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для {name} короткий анонс детских укладок и плетения перед "
                "праздником. Материал согласуем заранее."
            ),
            "third": (
                f"Для семей, которые приходят в {name}, мы из салона Органика можем предложить два понятных варианта: детская стрижка "
                "или праздничная укладка с плетением."
            ),
        },
        "fitness": {
            "summary": f"предложить клиентам {name} спортивный или расслабляющий массаж рядом с тренировками",
            "opening": (
                "В Органике есть спортивный и расслабляющий массаж. "
                f"Хотим предложить клиентам {name} удобный формат ухода после тренировок."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для клиентов {name} короткое предложение о спортивном и "
                "расслабляющем массаже. Текст и условия согласуем заранее."
            ),
            "third": (
                f"Для клиентов {name} мы из салона Органика можем предложить два формата: спортивный или расслабляющий массаж."
            ),
        },
        "medical_team": {
            "summary": f"подготовить для сотрудников компании {name} предложение на стрижки, маникюр или массаж рядом с работой",
            "opening": (
                f"Хотим предложить сотрудникам компании {name} услуги Органики рядом с работой: стрижки, маникюр или массаж. "
                "Речь только о предложении для сотрудников, без рекомендаций пациентам."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для сотрудников компании {name} короткий список услуг и текст для внутреннего канала. "
                "Текст и конкретные условия согласуем заранее."
            ),
            "third": (
                f"Для сотрудников компании {name} мы из салона Органика можем предложить три направления рядом с работой: стрижки, "
                "маникюр и массаж."
            ),
        },
        "employee_benefit": {
            "summary": f"подготовить для сотрудников {name} предложение на услуги салона рядом с работой",
            "opening": (
                f"Хотим предложить сотрудникам {name} услуги Органики рядом с работой: стрижки, маникюр и массаж."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для сотрудников {name} короткий текст и перечень услуг. "
                "Материал для внутреннего канала и конкретные условия согласуем заранее."
            ),
            "third": (
                f"Для сотрудников {name} мы из салона Органика можем предложить три направления рядом с работой: стрижки, "
                "маникюр и массаж."
            ),
        },
        "shopping_center": {
            "summary": f"предложить посетителям и сотрудникам {name} услуги Органики рядом",
            "opening": (
                f"Хотим предложить посетителям и сотрудникам {name} услуги Органики рядом: стрижки, "
                "маникюр и массаж."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для каналов {name} короткий текст и макет о салоне рядом. "
                "Размещение и конкретные условия согласуем заранее."
            ),
            "third": (
                f"Для посетителей и сотрудников {name} мы из салона Органика можем предложить три направления: "
                "стрижки, маникюр и массаж."
            ),
        },
        "beauty_retail": {
            "summary": f"подготовить с {name} материал о домашнем уходе и профессиональных услугах Органики",
            "opening": (
                f"У {name} есть товары для домашнего ухода, а Органика оказывает профессиональные услуги. "
                "Предлагаем подготовить короткий полезный материал, который объясняет разницу этих сценариев."
            ),
            "implementation": (
                f"Мы из салона Органика можем вместе с {name} собрать памятку: когда достаточно домашнего ухода, "
                "а когда уместно обратиться к мастеру. Без медицинских обещаний и навязанных рекомендаций."
            ),
            "third": (
                f"Для аудитории {name} мы из салона Органика можем подготовить материал по уходу за волосами, ногтями "
                "или кожей с понятным разделением домашнего и профессионального ухода."
            ),
        },
        "travel": {
            "summary": f"подготовить для клиентов {name} чек-лист подготовки к поездке с услугами Органики",
            "opening": (
                f"Органика может помочь клиентам {name} подготовиться к поездке: сделать стрижку, укладку "
                "или маникюр заранее. Предлагаем собрать короткий совместный чек-лист."
            ),
            "implementation": (
                f"Мы из салона Органика можем подготовить для {name} короткий материал о планировании стрижки, укладки "
                "и маникюра перед поездкой."
            ),
            "third": (
                f"Для клиентов {name} мы из салона Органика можем собрать три пункта подготовки к поездке: стрижка, "
                "укладка и маникюр."
            ),
        },
    }
    if kind == "observe":
        return {
            "summary": "нужен подтверждённый формат сотрудничества",
            "opening": "",
            "implementation": "",
            "third": "",
        }
    return offers[kind]


def _proposal(name: str, category: str) -> dict[str, Any]:
    kind = _recipient_kind(name, category)
    if kind == "observe":
        return {
            "title": "Нужна проверка предложения",
            "body_text": (
                "Конкретное предложение пока не готовим. По имеющимся публичным данным не найден "
                "подтверждённый формат сотрудничества, который был бы полезен обеим сторонам. "
                "Нужен дополнительный факт или ручное решение до подготовки сообщения."
            ),
            "status": "needs_evidence",
            "source": REPAIR_VERSION,
            "recipient_kind": kind,
        }
    offer = _offer_data(name, category)
    return {
        "title": "Идея сотрудничества",
        "body_text": (
            f"Мы ваши соседи - {BUSINESS_DESCRIPTION}.\n\n"
            f"{offer['opening']}\n\n"
            f"{offer['implementation']}\n\n"
            "Если идея подходит, сначала согласуем один простой формат и только потом подготовим материалы."
        ),
        "status": "draft",
        "source": REPAIR_VERSION,
        "recipient_kind": kind,
    }


def _messages(name: str, category: str) -> list[dict[str, str]]:
    offer = _offer_data(name, category)
    if _recipient_kind(name, category) == "observe":
        return []
    return [
        {
            "angle": "signal",
            "text": (
                f"Здравствуйте! Мы ваши соседи - {BUSINESS_DESCRIPTION}. {offer['opening']} "
                "Не подскажете, с кем можно обсудить детали?"
            ),
        },
        {
            "angle": "matching_authority",
            "text": f"Здравствуйте! {offer['implementation']} Показать готовый вариант?",
        },
        {
            "angle": "proof",
            "text": f"Здравствуйте! {offer['third']} Прислать два возможных формата?",
        },
        {
            "angle": "respectful_close",
            "text": (
                f"Здравствуйте! Не хотим отвлекать команду {name}. Если предложение салона Органика сейчас "
                "неактуально, больше писать не будем. Вернуться к нему позже?"
            ),
        },
    ]


def _candidate(name: str, category: str, source_url: str, workstream_id: str) -> dict[str, Any]:
    offer = _offer_data(name, category)
    return {
        "id": f"organika-partner-{workstream_id}",
        "evidence_id": f"organika-partner-{workstream_id}",
        "evidence_kind": "service_compatibility",
        "evidence_status": "observed",
        "observed_fact": f"В публичной карточке {name} указана категория: {category}.",
        "bridge": offer["summary"],
        "relevance_to_offer": offer["summary"],
        "trust_statement": "Органика",
        "source_url": source_url or f"localos-doc://partner-card/{workstream_id}",
        "source_type": "public_business_card",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "freshness": "current_snapshot",
        "confidence": 0.9,
        "recipient": name,
        "next_step": "Уточнить ответственного и обсудить один конкретный формат",
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


def _repair_room(
    cur,
    row: dict[str, Any],
    proposal: dict[str, Any],
    user_id: str,
    apply_changes: bool,
    force_repair: bool = False,
) -> tuple[str | None, str]:
    room_id = _text(row.get("room_id"))
    if not room_id:
        return None, "needs_room"
    previous = row.get("proposal_json") if isinstance(row.get("proposal_json"), dict) else {}
    previous_body = _text(previous.get("body_text"))
    if (
        not force_repair
        and previous.get("source") == REPAIR_VERSION
        and previous_body == proposal["body_text"]
    ):
        return room_id, "current"
    if not apply_changes:
        return room_id, "would_repair"
    ensure_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=previous_body,
        author_name=BUSINESS_NAME,
        metadata={"source": "existing_before_organika_partner_rules_v1"},
    )
    create_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=proposal["body_text"],
        author_name=BUSINESS_NAME,
        author_contact="",
        metadata={"source": REPAIR_VERSION, "manual_reviewed": True},
    )
    room_json = row.get("room_json") if isinstance(row.get("room_json"), dict) else {}
    room_json = {**room_json, "proposal": proposal}
    cur.execute(
        "UPDATE sales_rooms SET proposal_json = %s, room_json = %s, updated_at = NOW() WHERE id = %s",
        (Json(proposal), Json(room_json), room_id),
    )
    needs_evidence = proposal.get("status") == "needs_evidence"
    record_ai_learning_event(
        capability="sales_room.partner_offer",
        event_type="rejected" if needs_evidence else "accepted",
        intent="partnership_outreach",
        user_id=user_id,
        business_id=DEFAULT_BUSINESS_ID,
        accepted=False if needs_evidence else True,
        rejected=True if needs_evidence else False,
        edited_before_accept=True,
        outcome="needs_evidence" if needs_evidence else "draft_rewritten",
        prompt_key="organika_partner_offer",
        prompt_version=REPAIR_VERSION,
        draft_text=previous_body[:6000],
        final_text=proposal["body_text"][:6000],
        metadata={
            "room_id": room_id,
            "lead_id": row.get("lead_id"),
            "recipient_kind": proposal.get("recipient_kind"),
            "reason": "manual_product_correction",
        },
        conn=cur.connection,
    )
    return room_id, "needs_evidence" if needs_evidence else "repaired"


def _create_campaign(
    cur,
    row: dict[str, Any],
    contacts: list[tuple[str, dict[str, Any]]],
    room_id: str | None,
    sender_profile_id: str,
    represented_profile_id: str,
    email_sender_id: str | None,
    user_id: str,
    apply_changes: bool,
    force_repair: bool = False,
) -> tuple[str | None, str]:
    kind = _recipient_kind(_text(row.get("name")), _text(row.get("category")))
    if kind == "observe":
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
            "represented_business_id": DEFAULT_BUSINESS_ID,
            "segment": kind,
            "signal_kind": "service_compatibility",
            "freshness": "current_snapshot",
            "bridge_type": "audience_and_service_compatibility",
            "offer_id": f"offer-{row.get('workstream_id')}",
            "offer": _offer_data(_text(row.get("name")), _text(row.get("category")))["summary"],
            "trust_strategy": "business_reputation",
            "trust_statement": BUSINESS_NAME,
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
            "subject": f"Идея для Органики и {row.get('name')}" if channel == "email" else None,
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
    previous_text = ""
    if latest:
        cur.execute(
            """
            SELECT STRING_AGG(generated_text, E'\n\n---\n\n' ORDER BY sequence_index) AS text
            FROM outreach_campaign_touches WHERE campaign_id = %s
            """,
            (latest.get("id"),),
        )
        previous_text = _text(dict(cur.fetchone() or {}).get("text"))
    cur.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM outreach_campaigns WHERE workstream_id = %s",
        (row.get("workstream_id"),),
    )
    version = int(dict(cur.fetchone() or {}).get("version") or 1)
    campaign_id = str(uuid.uuid4())
    offer_summary = _offer_data(_text(row.get("name")), _text(row.get("category")))["summary"]
    decision = {
        "schema_version": "outreach-decision-v2",
        "action": "write_now",
        "reason_codes": ["PARTNERSHIP_COMPATIBILITY_CONFIRMED", "MANUAL_PRODUCT_REVIEW"],
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }
    selected_offer = {
        "id": f"offer-{row.get('workstream_id')}",
        "text": offer_summary,
        "source": _text(row.get("source_url")) or f"localos-doc://partner-card/{row.get('workstream_id')}",
    }
    policy = {
        "stop_on_reply": True,
        "approval_scope": "whole_sequence",
        "sender_mode": "localos_for_partner",
        "sender_scope_type": "platform",
        "represented_business_id": DEFAULT_BUSINESS_ID,
        "represented_business_name": BUSINESS_NAME,
        "represented_sender_profile_id": represented_profile_id,
        "generation_source": GENERATION_SOURCE,
    }
    cur.execute(
        """
        INSERT INTO outreach_campaigns (
            id, workstream_id, lead_id, scope_type, business_id, sender_profile_id,
            version, status, sender_mode, selected_offer_json, trust_strategy,
            decision_snapshot_json, policy_json, recipient_key, room_id, created_by,
            created_at, updated_at
        ) VALUES (%s, %s, %s, 'business', %s, %s::uuid, %s, 'draft',
                  'localos_for_partner', %s, 'business_reputation', %s, %s, %s,
                  %s::uuid, %s, NOW(), NOW())
        """,
        (
            campaign_id, row.get("workstream_id"), row.get("lead_id"), DEFAULT_BUSINESS_ID,
            sender_profile_id, version, Json(selected_offer), Json(decision), Json(policy),
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
    final_text = "\n\n---\n\n".join(touch["text"] for touch in touches)
    record_ai_learning_event(
        capability="outreach.sequence",
        event_type="accepted",
        intent="partnership_outreach",
        user_id=user_id,
        business_id=DEFAULT_BUSINESS_ID,
        accepted=True,
        edited_before_accept=True,
        outcome="draft_rewritten",
        prompt_key="organika_partner_sequence",
        prompt_version=REPAIR_VERSION,
        draft_text=previous_text[:12000],
        final_text=final_text[:12000],
        metadata={
            "lead_id": row.get("lead_id"),
            "lead_name": row.get("name"),
            "current_campaign_id": campaign_id,
            "rules_version": REPAIR_VERSION,
            "recipient_kind": kind,
            "correction_type": "manual_product_correction",
            "negative_patterns": [
                "LocalOS or Alexander named in partner-facing copy",
                "technical card category copied into recipient message",
                "audit offered instead of partnership",
                "generic safe pilot without a concrete business format",
            ],
        },
        conn=cur.connection,
    )
    return campaign_id, "created"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", default=DEFAULT_BUSINESS_ID)
    parser.add_argument("--workstream-id")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.business_id != DEFAULT_BUSINESS_ID:
        parser.error("this repair policy is only approved for Organika")
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
        platform_profile = cur.fetchone()
        if not platform_profile:
            raise RuntimeError("platform sender profile not found")
        sender_profile_id = _text(platform_profile.get("id"))
        cur.execute(
            """
            SELECT id FROM outreach_sender_profiles
            WHERE client_business_id = %s AND workstream_type = 'client_partnership' AND is_active = TRUE
            ORDER BY updated_at DESC LIMIT 1
            """,
            (DEFAULT_BUSINESS_ID,),
        )
        represented_profile = cur.fetchone()
        if not represented_profile:
            raise RuntimeError("Organika represented sender profile not found")
        represented_profile_id = _text(represented_profile.get("id"))
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

        rows = _load_rows(cur, DEFAULT_BUSINESS_ID)
        if args.workstream_id:
            rows = [
                row for row in rows
                if _text(row.get("workstream_id")) == args.workstream_id
            ]
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
                "recipient_kind": _recipient_kind(
                    _text(row.get("name")), _text(row.get("category"))
                ),
                "status": status,
            }
            if status in TERMINAL_STATES:
                result["outcome"] = "excluded_terminal"
                results.append(result)
                continue
            if _suppressed(cur, DEFAULT_BUSINESS_ID, _text(row.get("lead_id"))):
                result["outcome"] = "excluded_suppressed"
                results.append(result)
                continue
            category = _text(row.get("category"))
            if not category:
                result["outcome"] = "needs_evidence"
                results.append(result)
                continue
            proposal = _proposal(_text(row.get("name")), category)
            room_id, room_outcome = _repair_room(
                cur, row, proposal, user_id, args.apply, args.force
            )
            contacts = _choose_contacts(
                _load_contacts(cur, _text(row.get("lead_id"))),
                _text(row.get("name")),
            )
            campaign_id, campaign_outcome = _create_campaign(
                cur,
                row,
                contacts,
                room_id,
                sender_profile_id,
                represented_profile_id,
                email_sender_id,
                user_id,
                args.apply,
                args.force,
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
            "business_id": DEFAULT_BUSINESS_ID,
            "workstreams": len(results),
            "summary": summary,
            "by_kind": by_kind,
            "results": results,
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
