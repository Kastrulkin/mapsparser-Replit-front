#!/usr/bin/env python3
"""Prepare LocalOS sales rooms and deterministic founder-led draft sequences without AI calls."""

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
    _normalized,
    _text,
)


PLATFORM_EMAIL = "localosgo@gmail.com"
GENERATION_SOURCE = "manual_product_correction"
REPAIR_VERSION = "localos_sales_rules_v2"
DECISION_VERSION = "outreach-v2.1"
BUSINESS_NAME = "LocalOS"
SENDER_NAME = "Александр Демьянов"
SENDER_ROLE = "руководитель LocalOS"
TERMINAL_STATES = {
    "replied", "converted", "closed_lost", "not_relevant", "suppressed",
    "unsubscribed", "hard_no", "closed", "won", "lost", "archived",
}
BLOCKING_CAMPAIGN_STATES = {"approved", "active", "paused"}


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _valid_uuid(value: Any) -> bool:
    try:
        uuid.UUID(_text(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _load_rows(cur, workstream_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    filters = ["ws.workstream_type='localos_sales'"]
    params: list[Any] = []
    if workstream_id:
        filters.append("ws.id=%s")
        params.append(workstream_id)
    limit_sql = ""
    if limit:
        limit_sql = " LIMIT %s"
        params.append(max(1, limit))
    cur.execute(
        f"""
        SELECT ws.id AS workstream_id,ws.lead_id,ws.status AS workstream_status,
               ws.lifecycle_status,ws.last_contact_at AS workstream_last_contact_at,
               l.name,l.category,l.city,l.source_url,l.business_id AS lead_business_id,
               l.status AS lead_status,l.pipeline_status,l.last_contact_at AS lead_last_contact_at,
               sr.id AS room_id,sr.slug AS room_slug,sr.status AS room_status,
               sr.visibility AS room_visibility,sr.proposal_json,sr.room_json,sr.match_json,
               research.id AS research_id,research.evidence_json,
               research.personalization_candidates_json,research.selected_personalization_id,
               research.message_brief_json,research.message_readiness_json,
               research.outreach_decision_json
        FROM lead_workstreams ws
        JOIN prospectingleads l ON l.id=ws.lead_id
        LEFT JOIN sales_rooms sr ON sr.workstream_id=ws.id
        LEFT JOIN LATERAL (
            SELECT * FROM lead_workstream_research x
            WHERE x.workstream_id=ws.id
            ORDER BY x.researched_at DESC NULLS LAST,x.created_at DESC
            LIMIT 1
        ) research ON TRUE
        WHERE {' AND '.join(filters)}
        ORDER BY ws.updated_at ASC,ws.id
        {limit_sql}
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def _latest_campaign(cur, workstream_id: str) -> dict[str, Any]:
    cur.execute(
        "SELECT * FROM outreach_campaigns WHERE workstream_id=%s ORDER BY version DESC,created_at DESC LIMIT 1",
        (workstream_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else {}


def _has_blocking_campaign(cur, workstream_id: str) -> bool:
    cur.execute(
        "SELECT 1 FROM outreach_campaigns WHERE workstream_id=%s AND status=ANY(%s) LIMIT 1",
        (workstream_id, list(BLOCKING_CAMPAIGN_STATES)),
    )
    return bool(cur.fetchone())


def _suppressed(cur, lead_id: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM outreach_suppressions
        WHERE (expires_at IS NULL OR expires_at>NOW())
          AND (lead_id=%s OR NULLIF(recipient_key,'')=%s)
          AND scope_type IN ('platform','platform_safety')
        LIMIT 1
        """,
        (lead_id, recipient_key(lead_id)),
    )
    return bool(cur.fetchone())


def _blocked_reason(cur, row: dict[str, Any]) -> str | None:
    states = {
        _normalized(row.get("workstream_status")),
        _normalized(row.get("lifecycle_status")),
        _normalized(row.get("lead_status")),
        _normalized(row.get("pipeline_status")),
    }
    if states.intersection(TERMINAL_STATES):
        return "terminal_state"
    if _suppressed(cur, _text(row.get("lead_id"))):
        return "suppressed"
    if _has_blocking_campaign(cur, _text(row.get("workstream_id"))):
        return "campaign_already_active"
    latest = _latest_campaign(cur, _text(row.get("workstream_id")))
    if latest.get("last_reply_at") or _text(latest.get("stop_reason")) == "recipient_replied":
        return "recipient_replied"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for key in ("workstream_last_contact_at", "lead_last_contact_at"):
        value = row.get(key)
        if isinstance(value, datetime):
            current = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            if current.astimezone(timezone.utc) > cutoff:
                return "contact_cooldown"
    return None


def _evidence_date(item: dict[str, Any]) -> datetime:
    raw = _text(item.get("observed_at"))
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _usable_audit_evidence(item: dict[str, Any]) -> bool:
    if _text(item.get("kind")) != "map_issue":
        return False
    if _text(item.get("status")) not in {"observed", "approved"}:
        return False
    fact = _text(item.get("fact"))
    source_url = _text(item.get("source_url"))
    if not fact or not source_url:
        return False
    if re.search(r"Рейтинг\s*-\s*0[,\.]0", fact, flags=re.IGNORECASE):
        return False
    services_match = re.search(
        r"всего услуг\s*-\s*(\d+);\s*с ценой\s*-\s*(\d+)",
        fact,
        flags=re.IGNORECASE,
    )
    if services_match:
        total = int(services_match.group(1))
        priced = int(services_match.group(2))
        missing = max(0, total - priced)
        if total <= 0 or missing < 3 or (priced / total) > 0.8:
            return False
    rating_match = re.search(
        r"Рейтинг\s*-\s*([0-9]+(?:[,.][0-9]+)?);\s*публичных отзывов\s*-\s*(\d+)",
        fact,
        flags=re.IGNORECASE,
    )
    if rating_match:
        rating = float(rating_match.group(1).replace(",", "."))
        reviews = int(rating_match.group(2))
        if rating > 4.2 and reviews > 10:
            return False
    return True


def _select_evidence(row: dict[str, Any]) -> dict[str, Any] | None:
    evidence = row.get("evidence_json") if isinstance(row.get("evidence_json"), list) else []
    usable = [dict(item) for item in evidence if isinstance(item, dict) and _usable_audit_evidence(item)]
    if not usable:
        return None
    usable.sort(key=_evidence_date, reverse=True)
    return usable[0]


def _bridge_for_fact(fact: str) -> str:
    normalized = _normalized(fact)
    if "услуг" in normalized and "цен" in normalized:
        return "Можно предметно проверить, для каких услуг клиент видит цену прямо в карточке."
    if "рейтинг" in normalized or "отзыв" in normalized:
        return "Можно проверить темы отзывов, ответы бизнеса и то, как они влияют на выбор клиента."
    if "фото" in normalized:
        return "Можно проверить, достаточно ли фотографий, чтобы клиент понял услуги и атмосферу до визита."
    return "Можно предметно проверить этот участок карточки и выбрать первое изменение."


def _proposal(name: str, evidence: dict[str, Any] | None, state: str) -> dict[str, Any]:
    if state == "needs_evidence" or not evidence:
        return {
            "title": "Нужны факты из аудита",
            "body_text": (
                "Предложение пока не готовим. Не найден достаточно конкретный и проверяемый "
                "факт из карточки, отзывов или сайта. Нужен свежий аудит до подготовки текста."
            ),
            "status": "needs_evidence",
            "source": REPAIR_VERSION,
        }
    fact = _text(evidence.get("fact"))
    status = "needs_contact" if state == "needs_contact" else "draft"
    return {
        "title": "Как усилить карточку",
        "body_text": (
            f"{fact}\n\n"
            f"LocalOS может помочь усилить карточку {name}, чтобы клиенту было проще "
            "найти бизнес в онлайн-поиске, понять предложение и принять решение о визите.\n\n"
            "Первый шаг - короткий разбор с тремя наблюдениями и одним приоритетным действием."
        ),
        "status": status,
        "source": REPAIR_VERSION,
        "evidence_id": evidence.get("id"),
        "source_url": evidence.get("source_url"),
    }


def _messages(name: str, evidence: dict[str, Any], founder_story: str) -> list[dict[str, str]]:
    fact = _text(evidence.get("fact"))
    bridge = _bridge_for_fact(fact)
    return [
        {
            "angle": "signal",
            "text": (
                f"Здравствуйте! Я {SENDER_NAME}, {SENDER_ROLE}. Пишу по поводу карточки {name}. "
                f"{founder_story} {fact} {bridge} Могу прислать короткий разбор?"
            ),
        },
        {
            "angle": "founder_story",
            "text": (
                f"Здравствуйте! По карточке {name} могу показать не общий отчёт, а три приоритетных действия LocalOS: "
                "что поправить в карточке, услугах или работе с отзывами в первую очередь. Подготовить такой список?"
            ),
        },
        {
            "angle": "proof",
            "text": (
                f"Здравствуйте! Для карточки {name} уже есть открытый аудит LocalOS. В нём видны исходные данные, "
                "замечания и первое действие без автоматических изменений. Прислать ссылку?"
            ),
        },
        {
            "angle": "respectful_close",
            "text": (
                f"Здравствуйте! Не хочу отвлекать вашу команду. Если разбор карточки {name} от LocalOS сейчас неактуален, "
                "больше писать не буду. Вернуться к нему позже?"
            ),
        },
    ]


def _candidate(name: str, evidence: dict[str, Any]) -> dict[str, Any]:
    fact = _text(evidence.get("fact"))
    return {
        "id": evidence.get("id"),
        "evidence_id": evidence.get("id"),
        "evidence_kind": "map_issue",
        "evidence_status": "observed",
        "observed_fact": fact,
        "bridge": _bridge_for_fact(fact),
        "relevance_to_offer": _bridge_for_fact(fact),
        "trust_statement": "LocalOS",
        "source_url": evidence.get("source_url"),
        "source_type": "public_audit",
        "observed_at": evidence.get("observed_at"),
        "freshness": evidence.get("freshness") or "current_snapshot",
        "confidence": evidence.get("confidence") or 0.9,
        "recipient": name,
        "next_step": "Прислать короткий разбор",
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
    result = dict(cur.fetchone() or {})
    return int(result.get("count") or 0) == 4 and bool(result.get("current_rules")) and bool(result.get("quality_passed"))


def _set_research_state(
    cur,
    row: dict[str, Any],
    action: str,
    reason_code: str,
    apply_changes: bool,
) -> None:
    if not apply_changes or not row.get("research_id"):
        return
    decision = row.get("outreach_decision_json") if isinstance(row.get("outreach_decision_json"), dict) else {}
    decision = dict(decision)
    decision["version"] = DECISION_VERSION
    decision["action"] = action
    decision["calculated_at"] = datetime.now(timezone.utc).isoformat()
    decision["manual_review_version"] = REPAIR_VERSION
    decision["reason_codes"] = list(dict.fromkeys(list(decision.get("reason_codes") or []) + [reason_code]))
    readiness = {
        "code": action,
        "label": {
            "needs_contact": "Нужен контакт получателя",
            "needs_evidence": "Нужен конкретный факт из аудита",
            "needs_sender_setup": "Нужна настройка отправителя",
            "write_now": "Готово к проверке",
        }.get(action, action),
        "missing": [reason_code] if action != "write_now" else [],
        "reason_codes": [reason_code],
        "source": REPAIR_VERSION,
        "sender_mode": "localos",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    cur.execute(
        "UPDATE lead_workstream_research SET outreach_decision_json=%s,message_readiness_json=%s WHERE id=%s",
        (Json(decision), Json(readiness), row.get("research_id")),
    )


def _repair_room(
    cur,
    row: dict[str, Any],
    proposal: dict[str, Any],
    user_id: str,
    apply_changes: bool,
    force_repair: bool,
) -> tuple[str | None, str]:
    room_id = _text(row.get("room_id"))
    previous = row.get("proposal_json") if isinstance(row.get("proposal_json"), dict) else {}
    previous_body = _text(previous.get("body_text"))
    if room_id and not force_repair and previous.get("source") == REPAIR_VERSION and previous_body == proposal["body_text"]:
        return room_id, "current"
    lead_business_id = _text(row.get("lead_business_id"))
    if not room_id and not _valid_uuid(lead_business_id):
        return None, "unavailable_without_lead_business"
    if not apply_changes:
        return room_id or "dry-run-new-room", "would_repair" if room_id else "would_create"
    if room_id:
        ensure_sales_room_proposal_version(
            cur,
            room_id=room_id,
            body_text=previous_body,
            author_name=BUSINESS_NAME,
            metadata={"source": f"existing_before_{REPAIR_VERSION}"},
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
            "UPDATE sales_rooms SET proposal_json=%s,room_json=%s,updated_at=NOW() WHERE id=%s",
            (Json(proposal), Json(room_json), room_id),
        )
        return room_id, "repaired"
    room_id = str(uuid.uuid4())
    slug = f"room-{room_id[:12]}"
    preview = {
        "lead_id": row.get("lead_id"),
        "sender_mode": "localos",
        "decision": {"action": proposal.get("status")},
        "selected_offer": {"id": f"offer-{row.get('workstream_id')}", "text": proposal["body_text"]},
        "selected_trust": {"strategy": "founder_story"},
    }
    room_json = build_room_preview(
        preview,
        {
            "lead_name": row.get("name"),
            "category": row.get("category"),
            "city": row.get("city"),
            "source_url": row.get("source_url"),
            "lead_business_id": lead_business_id,
            "client_business_name": BUSINESS_NAME,
        },
    )
    room_json["proposal"] = proposal
    cur.execute(
        """
        INSERT INTO sales_rooms (
            id,slug,business_id,mode,lead_id,workstream_id,data_mode,match_json,
            proposal_json,room_json,status,visibility,created_by,created_at,updated_at
        ) VALUES (%s,%s,%s::uuid,'client_search',%s,%s,'outreach_v2',%s,%s,%s,
                  'prepared','private',%s::uuid,NOW(),NOW())
        """,
        (
            room_id, slug, lead_business_id, row.get("lead_id"), row.get("workstream_id"),
            Json({}), Json(proposal), Json(room_json), user_id,
        ),
    )
    create_sales_room_proposal_version(
        cur,
        room_id=room_id,
        body_text=proposal["body_text"],
        author_name=BUSINESS_NAME,
        author_contact="",
        metadata={"source": REPAIR_VERSION, "manual_reviewed": True},
    )
    return room_id, "created"


def _cancel_latest_draft(cur, row: dict[str, Any], reason: str, apply_changes: bool) -> None:
    if not apply_changes:
        return
    latest = _latest_campaign(cur, _text(row.get("workstream_id")))
    if latest.get("status") == "draft":
        cur.execute(
            "UPDATE outreach_campaigns SET status='cancelled',stop_reason=%s,updated_at=NOW() WHERE id=%s AND status='draft'",
            (reason, latest.get("id")),
        )


def _create_campaign(
    cur,
    row: dict[str, Any],
    evidence: dict[str, Any],
    contacts: list[tuple[str, dict[str, Any]]],
    room_id: str | None,
    sender_profile_id: str,
    email_sender_id: str | None,
    founder_story: str,
    user_id: str,
    apply_changes: bool,
    force_repair: bool,
) -> tuple[str | None, str]:
    latest = _latest_campaign(cur, _text(row.get("workstream_id")))
    if latest.get("status") in BLOCKING_CAMPAIGN_STATES:
        return None, f"blocked_existing_{latest.get('status')}"
    if not force_repair and _campaign_is_current(cur, latest):
        return _text(latest.get("id")), "current"
    if not contacts:
        return None, "needs_contact"
    candidate = _candidate(_text(row.get("name")), evidence)
    messages = _messages(_text(row.get("name")), evidence, founder_story)
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
            "workstream_type": "localos_sales",
            "sender_mode": "localos",
            "segment": row.get("category"),
            "signal_kind": "map_issue",
            "freshness": evidence.get("freshness") or "current_snapshot",
            "bridge_type": "audit_to_local_presence",
            "offer_id": f"offer-{row.get('workstream_id')}",
            "offer": "Короткий разбор: три наблюдения и один приоритетный шаг",
            "trust_strategy": "founder_story",
            "trust_statement": founder_story,
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
            "subject": f"Короткий разбор карточки {row.get('name')}" if channel == "email" else None,
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
    decision = row.get("outreach_decision_json") if isinstance(row.get("outreach_decision_json"), dict) else {}
    decision = {**decision, "action": "write_now", "manual_review_version": REPAIR_VERSION}
    selected_offer = {
        "id": f"offer-{row.get('workstream_id')}",
        "text": "Короткий разбор: три наблюдения и один приоритетный шаг",
        "source": "approved_sender_profile",
    }
    policy = {
        "stop_on_reply": True,
        "approval_scope": "whole_sequence",
        "sender_mode": "localos",
        "sender_scope_type": "platform",
        "generation_source": GENERATION_SOURCE,
    }
    cur.execute(
        """
        INSERT INTO outreach_campaigns (
            id,workstream_id,lead_id,scope_type,business_id,sender_profile_id,version,status,
            sender_mode,selected_offer_json,trust_strategy,decision_snapshot_json,policy_json,
            recipient_key,room_id,created_by,created_at,updated_at
        ) VALUES (%s,%s,%s,'platform',NULL,%s::uuid,%s,'draft','localos',%s,'founder_story',
                  %s,%s,%s,NULLIF(%s,'')::uuid,%s,NOW(),NOW())
        """,
        (
            campaign_id, row.get("workstream_id"), row.get("lead_id"), sender_profile_id,
            version, Json(selected_offer), Json(decision), Json(policy),
            recipient_key(_text(row.get("lead_id"))), room_id or "", user_id,
        ),
    )
    for touch in touches:
        brief = {
            "evidence_id": evidence.get("id"),
            "source_url": evidence.get("source_url"),
            "channel_status": touch["channel_status"],
            "observation": evidence.get("fact"),
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
    if room_id:
        cur.execute("UPDATE sales_rooms SET campaign_id=%s WHERE id=%s", (campaign_id, room_id))
    final_text = "\n\n---\n\n".join(touch["text"] for touch in touches)
    record_ai_learning_event(
        capability="outreach.sequence",
        event_type="accepted",
        intent="client_outreach",
        user_id=user_id,
        business_id=None,
        accepted=True,
        edited_before_accept=True,
        outcome="draft_rewritten",
        prompt_key="localos_sales_sequence",
        prompt_version=REPAIR_VERSION,
        draft_text=previous_text[:12000],
        final_text=final_text[:12000],
        metadata={
            "lead_id": row.get("lead_id"), "lead_name": row.get("name"),
            "current_campaign_id": campaign_id, "rules_version": REPAIR_VERSION,
            "correction_type": "manual_product_correction",
        },
        conn=cur.connection,
    )
    return campaign_id, "created"


def _sender_context(cur) -> tuple[str, str | None, str, str]:
    cur.execute("SELECT id FROM users WHERE COALESCE(is_superadmin,FALSE)=TRUE AND is_active=TRUE ORDER BY updated_at DESC LIMIT 1")
    user = cur.fetchone()
    if not user:
        raise RuntimeError("superadmin not found")
    cur.execute(
        """
        SELECT id,competence_story FROM outreach_sender_profiles
        WHERE workstream_type='localos_sales' AND client_business_id IS NULL AND is_active=TRUE
          AND confirmed_at IS NOT NULL
        ORDER BY updated_at DESC LIMIT 1
        """
    )
    profile = cur.fetchone()
    if not profile:
        raise RuntimeError("confirmed LocalOS sender profile not found")
    founder_story = _text(profile.get("competence_story"))
    if not founder_story:
        raise RuntimeError("LocalOS founder story is empty")
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
    return _text(profile.get("id")), _text(email.get("id")) if email else None, founder_story, _text(user.get("id"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workstream-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.force and not args.workstream_id:
        parser.error("--force requires --workstream-id")
    conn = _connect()
    try:
        cur = conn.cursor()
        sender_profile_id, email_sender_id, founder_story, user_id = _sender_context(cur)
        rows = _load_rows(cur, args.workstream_id, args.limit)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            workstream_id = _text(row.get("workstream_id"))
            if workstream_id in seen:
                continue
            seen.add(workstream_id)
            result: dict[str, Any] = {
                "lead": row.get("name"), "lead_id": row.get("lead_id"),
                "workstream_id": workstream_id,
            }
            blocked = _blocked_reason(cur, row)
            if blocked:
                result["outcome"] = blocked
                results.append(result)
                continue
            decision = row.get("outreach_decision_json") if isinstance(row.get("outreach_decision_json"), dict) else {}
            action = _text(decision.get("action")) if _text(decision.get("version")) == DECISION_VERSION else "needs_evidence"
            evidence = _select_evidence(row)
            contacts = _choose_contacts(_load_contacts(cur, _text(row.get("lead_id"))), _text(row.get("name")))
            if action == "write_now" and not evidence:
                action = "needs_evidence"
                _set_research_state(cur, row, action, "AUDIT_FACT_NOT_USABLE_FOR_OUTREACH", args.apply)
            elif action == "write_now" and not contacts:
                action = "needs_contact"
                _set_research_state(cur, row, action, "VALID_RECIPIENT_CONTACT_MISSING", args.apply)
            elif action == "observe":
                action = "needs_evidence"
            proposal = _proposal(_text(row.get("name")), evidence, action)
            room_id, room_outcome = _repair_room(
                cur, row, proposal, user_id, args.apply, args.force,
            )
            if action != "write_now":
                _cancel_latest_draft(cur, row, f"{action}_by_{REPAIR_VERSION}", args.apply)
                result.update({
                    "room": room_outcome, "room_id": room_id,
                    "campaign": action, "outcome": action,
                    "channels": [channel for channel, _contact in contacts],
                })
                results.append(result)
                continue
            campaign_id, campaign_outcome = _create_campaign(
                cur, row, evidence, contacts, room_id, sender_profile_id,
                email_sender_id, founder_story, user_id, args.apply, args.force,
            )
            if campaign_outcome in {"created", "current"}:
                _set_research_state(cur, row, "write_now", "MANUAL_PRODUCT_REVIEW", args.apply)
            result.update({
                "room": room_outcome, "room_id": room_id,
                "campaign": campaign_outcome, "campaign_id": campaign_id,
                "outcome": campaign_outcome,
                "channels": [channel for channel, _contact in contacts],
            })
            results.append(result)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        summary: dict[str, int] = {}
        room_summary: dict[str, int] = {}
        for item in results:
            outcome = _text(item.get("outcome")) or "unknown"
            room_outcome = _text(item.get("room")) or "none"
            summary[outcome] = summary.get(outcome, 0) + 1
            room_summary[room_outcome] = room_summary.get(room_outcome, 0) + 1
        print(json.dumps({
            "dry_run": not args.apply,
            "workstreams": len(results),
            "summary": summary,
            "rooms": room_summary,
            "results": results,
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
