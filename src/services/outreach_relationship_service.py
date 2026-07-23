"""Relationship memory and sales-room integration for Outreach v2."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from psycopg2.extras import Json

from services.sales_room_helpers import make_sales_room_url


POSITIVE_CLASSIFICATIONS = {"interested", "question", "human_unknown"}
ROOM_INVITATION_CLASSIFICATIONS = {"interested", "question"}
NEGATIVE_CLASSIFICATIONS = {"not_interested", "unsubscribe", "complaint"}


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _slug_base(value: Any) -> str:
    slug = re.sub(r"[^a-zа-яё0-9]+", "-", _text(value).lower(), flags=re.IGNORECASE).strip("-")
    return slug[:72] or "partnership-room"


def _unique_slug(cursor: Any, name: Any) -> str:
    base = _slug_base(name)
    candidate = f"{base}-{uuid.uuid4().hex[:8]}"
    cursor.execute("SELECT 1 FROM sales_rooms WHERE slug = %s", (candidate,))
    return f"{candidate}-{uuid.uuid4().hex[:4]}" if cursor.fetchone() else candidate


def build_relationship_delta(raw_reply: str, classification: str) -> dict[str, Any]:
    normalized = _text(raw_reply)
    lowered = normalized.lower()
    proposed_updates = []
    next_step = "Ответить получателю вручную"
    stage = "engaged" if classification in POSITIVE_CLASSIFICATIONS else "new"
    do_not_call = False
    follow_up_after = None
    if classification == "interested":
        next_step = "Уточнить удобный формат знакомства и следующий шаг"
    elif classification == "question":
        next_step = "Ответить на вопрос и предложить один следующий шаг"
    elif classification in NEGATIVE_CLASSIFICATIONS:
        stage = "lost"
        next_step = "Не продолжать аутрич"
        do_not_call = classification in {"unsubscribe", "complaint"}
    if any(marker in lowered for marker in ("напишите позже", "вернитесь позже", "свяжитесь позже")):
        if "завтра" in lowered:
            follow_up_after = datetime.now(timezone.utc) + timedelta(days=1)
        elif "через неделю" in lowered:
            follow_up_after = datetime.now(timezone.utc) + timedelta(days=7)
        proposed_updates.append({
            "type": "follow_up_after",
            "value": follow_up_after.isoformat() if follow_up_after else None,
            "status": "confirmed_from_explicit_reply" if follow_up_after else "needs_confirmation",
            "source_text": normalized,
        })
        next_step = "Подтвердить дату следующего контакта"
    preferred_channel = None
    for channel, markers in {
        "telegram": (
            "пишите в телеграм", "пишите в telegram", "лучше в телеграм",
            "лучше в telegram", "лучше пишите в телеграм", "лучше пишите в telegram",
        ),
        "email": ("пишите на почту", "лучше по почте", "лучше на email", "лучше пишите на почту"),
        "whatsapp": ("пишите в whatsapp", "пишите в ватсап", "лучше пишите в whatsapp"),
    }.items():
        if any(marker in lowered for marker in markers):
            preferred_channel = channel
            proposed_updates.append({
                "type": "preferred_channel",
                "value": channel,
                "status": "confirmed_from_explicit_reply",
                "source_text": normalized,
            })
            break
    return {
        "negotiation_stage": stage,
        "next_step": next_step,
        "do_not_call": do_not_call,
        "preferred_channel": preferred_channel,
        "follow_up_after": follow_up_after,
        "proposed_updates": proposed_updates,
        "summary": normalized[:1000],
        "confidence": 1.0 if classification not in {"human_unknown"} else 0.6,
    }


def build_room_preview(preview: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Build the private workspace projection without persisting it."""
    sender_mode = _text(preview.get("sender_mode"))
    represented_business_name = _text(
        preview.get("represented_business_name")
        or context.get("client_business_name")
        or context.get("represented_business_name")
    )
    lead_name = _text(context.get("lead_name")) or "потенциальный партнёр"
    selected_offer_text = _text((preview.get("selected_offer") or {}).get("text"))
    if sender_mode in {"partner_business", "localos_for_partner"}:
        companies = (
            f'У "{represented_business_name}" и "{lead_name}"'
            if represented_business_name
            else f'У бизнеса и "{lead_name}"'
        )
        proposal_title = "Идея сотрудничества"
        proposal_body = selected_offer_text or (
            "Кажется, у компаний есть общая локальная аудитория.\n\n"
            f"{companies} могут пересекаться люди, которые живут или бывают в одном районе.\n\n"
            "Предлагаем выбрать простой способ, чтобы познакомить эту аудиторию с двумя полезными местами рядом. "
            "Для начала можно запустить небольшой совместный пилот и оценить результат.\n\n"
            "Возможные форматы собраны ниже."
        )
    else:
        proposal_title = "Предложение LocalOS"
        proposal_body = _text((preview.get("selected_offer") or {}).get("text"))
    return {
        "visibility": "private",
        "status": "prepared",
        "schema_version": "outreach-room-v2",
        "lead": {
            "id": preview.get("lead_id"),
            "name": context.get("lead_name"),
            "city": context.get("city"),
            "category": context.get("category"),
            "source_url": context.get("source_url"),
        },
        "represented_business": {
            "id": preview.get("represented_business_id"),
            "name": preview.get("represented_business_name"),
        },
        "sender_mode": preview.get("sender_mode"),
        "decision": preview.get("decision") or {},
        "evidence": preview.get("evidence") or [],
        "offer": preview.get("selected_offer") or {},
        "trust": preview.get("selected_trust") or {},
        "proposal": {
            "title": proposal_title,
            "body_text": proposal_body,
        },
        "open_questions": [],
        "next_step": "Дождаться ответа на первое касание",
        "invitation_draft": None,
    }


def upsert_relationship_from_reply(
    cursor: Any,
    *,
    workstream_id: str,
    lead_id: str,
    scope_type: str,
    business_id: str | None,
    raw_reply: str,
    classification: str,
    provider_event_id: str | None,
) -> dict[str, Any]:
    delta = build_relationship_delta(raw_reply, classification)
    cursor.execute(
        """
        INSERT INTO lead_relationship_states (
            id, workstream_id, lead_id, scope_type, business_id,
            preferred_channel, follow_up_after, do_not_call, summary, next_step,
            negotiation_stage, proposed_updates_json, provenance_json,
            confidence, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
        ON CONFLICT (workstream_id) DO UPDATE
        SET preferred_channel = COALESCE(EXCLUDED.preferred_channel, lead_relationship_states.preferred_channel),
            follow_up_after = COALESCE(EXCLUDED.follow_up_after, lead_relationship_states.follow_up_after),
            do_not_call = lead_relationship_states.do_not_call OR EXCLUDED.do_not_call,
            summary = EXCLUDED.summary,
            next_step = EXCLUDED.next_step,
            negotiation_stage = EXCLUDED.negotiation_stage,
            proposed_updates_json = EXCLUDED.proposed_updates_json,
            provenance_json = lead_relationship_states.provenance_json || EXCLUDED.provenance_json,
            confidence = EXCLUDED.confidence,
            updated_at = NOW()
        RETURNING *
        """,
        (
            str(uuid.uuid4()), workstream_id, lead_id, scope_type, business_id,
            delta.get("preferred_channel"), delta.get("follow_up_after"),
            delta.get("do_not_call"), delta.get("summary"),
            delta.get("next_step"), delta.get("negotiation_stage"),
            Json(delta.get("proposed_updates") or []),
            Json({
                "last_reply": {
                    "provider_event_id": provider_event_id,
                    "classification": classification,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
            }),
            delta.get("confidence"),
        ),
    )
    row = cursor.fetchone()
    return dict(row) if row else delta


def prepare_private_room(
    cursor: Any,
    *,
    campaign_id: str,
    preview: dict[str, Any],
    context: dict[str, Any],
    user_id: str,
) -> dict[str, Any] | None:
    workstream_id = _text(preview.get("workstream_id"))
    owner_business_id = _text(context.get("client_business_id") or context.get("lead_business_id"))
    if not workstream_id or not owner_business_id:
        return None
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        (f"outreach-room:{workstream_id}",),
    )
    cursor.execute(
        "SELECT * FROM sales_rooms WHERE workstream_id = %s ORDER BY created_at ASC LIMIT 1 FOR UPDATE",
        (workstream_id,),
    )
    row = cursor.fetchone()
    existing = dict(row) if row else {}
    room_id = _text(existing.get("id")) or str(uuid.uuid4())
    slug = _text(existing.get("slug")) or _unique_slug(cursor, context.get("lead_name"))
    room_json = existing.get("room_json") if isinstance(existing.get("room_json"), dict) else {}
    generated = build_room_preview(preview, context)
    generated["invitation_draft"] = room_json.get("invitation_draft")
    generated["public_url"] = make_sales_room_url(slug)
    merged_room_json = {**room_json, **generated}
    if existing:
        cursor.execute(
            """
            UPDATE sales_rooms
            SET campaign_id = %s, room_json = %s,
                match_json = COALESCE(NULLIF(%s, '{}'::jsonb), match_json),
                status = CASE WHEN status IN ('won', 'lost', 'archived') THEN status ELSE 'prepared' END,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                campaign_id, Json(_json_safe(merged_room_json)),
                Json(_json_safe(context.get("partnership_match") or {})), room_id,
            ),
        )
    else:
        mode = "partner_search" if _text(context.get("workstream_type")) == "client_partnership" else "client_search"
        cursor.execute(
            """
            INSERT INTO sales_rooms (
                id, slug, business_id, mode, lead_id, workstream_id, campaign_id,
                data_mode, match_json, proposal_json, room_json, status, visibility,
                created_by, created_at, updated_at
            ) VALUES (
                %s, %s, %s::uuid, %s, %s, %s, %s, 'outreach_v2', %s, %s, %s,
                'prepared', 'private', NULLIF(%s, '')::uuid, NOW(), NOW()
            )
            RETURNING *
            """,
            (
                room_id, slug, owner_business_id, mode, preview.get("lead_id"),
                workstream_id, campaign_id,
                Json(_json_safe(context.get("partnership_match") or {})),
                Json(_json_safe(generated.get("proposal") or {})),
                Json(_json_safe(merged_room_json)), user_id,
            ),
        )
    saved = cursor.fetchone()
    cursor.execute("UPDATE outreach_campaigns SET room_id = %s WHERE id = %s", (room_id, campaign_id))
    cursor.execute(
        """
        INSERT INTO sales_room_events (id, room_id, event_type, metadata_json, created_at)
        VALUES (%s, %s, 'room_prepared', %s, NOW())
        """,
        (str(uuid.uuid4()), room_id, Json({"campaign_id": campaign_id, "workstream_id": workstream_id})),
    )
    result = dict(saved) if saved else {"id": room_id, "slug": slug}
    result["public_url"] = make_sales_room_url(slug)
    return result


def mirror_inbound_to_room(
    cursor: Any,
    *,
    campaign_id: str,
    touch_id: str,
    channel: str,
    provider_event_id: str | None,
    raw_reply: str,
    occurred_at: Any,
) -> None:
    cursor.execute("SELECT room_id FROM outreach_campaigns WHERE id = %s", (campaign_id,))
    row = cursor.fetchone()
    room_id = row.get("room_id") if row and hasattr(row, "get") else row[0] if row else None
    if not room_id:
        return
    cursor.execute(
        """
        INSERT INTO sales_room_messages (
            id, room_id, author_type, body_text, direction, source_channel,
            provider_event_id, campaign_id, campaign_touch_id, delivery_status,
            occurred_at, created_at
        ) VALUES (
            %s, %s, 'recipient', %s, 'inbound', %s, NULLIF(%s, ''),
            %s, %s, 'received', COALESCE(%s, NOW()), NOW()
        )
        ON CONFLICT DO NOTHING
        """,
        (
            str(uuid.uuid4()), room_id, _text(raw_reply), channel,
            provider_event_id or "", campaign_id, touch_id, occurred_at,
        ),
    )
    cursor.execute(
        """
        INSERT INTO sales_room_events (id, room_id, event_type, metadata_json, created_at)
        VALUES (%s, %s, 'message_mirrored', %s, NOW())
        """,
        (
            str(uuid.uuid4()), room_id,
            Json({"campaign_id": campaign_id, "touch_id": touch_id, "channel": channel}),
        ),
    )


def mark_room_ready_after_positive_reply(
    cursor: Any,
    *,
    campaign_id: str,
    represented_business_name: str | None,
) -> dict[str, Any] | None:
    cursor.execute("SELECT room_id FROM outreach_campaigns WHERE id = %s", (campaign_id,))
    row = cursor.fetchone()
    room_id = row.get("room_id") if row and hasattr(row, "get") else row[0] if row else None
    if not room_id:
        return None
    cursor.execute("SELECT id, slug, room_json FROM sales_rooms WHERE id = %s FOR UPDATE", (room_id,))
    room_row = cursor.fetchone()
    if not room_row:
        return None
    room = dict(room_row)
    room_json = room.get("room_json") if isinstance(room.get("room_json"), dict) else {}
    invitation_text = (
        "Спасибо за ответ. Я подготовил цифровую комнату, чтобы не потерять детали: "
        "там собраны идея сотрудничества, основания matching и следующий шаг."
    )
    if represented_business_name:
        invitation_text += f" Комната подготовлена для знакомства с {represented_business_name}."
    room_json["invitation_draft"] = {
        "status": "draft",
        "text": invitation_text,
        "room_url": make_sales_room_url(_text(room.get("slug"))),
        "approval_required": True,
    }
    room_json["next_step"] = "Проверить и подтвердить приглашение в комнату"
    cursor.execute(
        """
        UPDATE sales_rooms
        SET visibility = 'ready_to_share', status = 'engaged', room_json = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, slug, visibility, status, room_json
        """,
        (Json(room_json), room_id),
    )
    updated = cursor.fetchone()
    cursor.execute(
        """
        INSERT INTO sales_room_events (id, room_id, event_type, metadata_json, created_at)
        VALUES (%s, %s, 'invitation_drafted', %s, NOW())
        """,
        (str(uuid.uuid4()), room_id, Json({"campaign_id": campaign_id})),
    )
    return dict(updated) if updated else None


def approve_room_invitation(cursor: Any, *, campaign_id: str, actor_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT room.id, room.slug, room.room_json
        FROM outreach_campaigns campaign
        JOIN sales_rooms room ON room.id = campaign.room_id
        WHERE campaign.id = %s
        FOR UPDATE
        """,
        (campaign_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise LookupError("Campaign room not found")
    room = dict(row)
    room_json = room.get("room_json") if isinstance(room.get("room_json"), dict) else {}
    invitation = room_json.get("invitation_draft") if isinstance(room_json.get("invitation_draft"), dict) else {}
    if not invitation:
        raise ValueError("Room invitation draft is not ready")
    invitation["status"] = "approved"
    invitation["approved_at"] = datetime.now(timezone.utc).isoformat()
    invitation["approved_by"] = actor_id
    room_json["invitation_draft"] = invitation
    cursor.execute(
        """
        UPDATE sales_rooms
        SET visibility = 'shared', room_json = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, slug, visibility, status, room_json
        """,
        (Json(room_json), room.get("id")),
    )
    updated = dict(cursor.fetchone())
    cursor.execute(
        """
        INSERT INTO sales_room_events (id, room_id, event_type, metadata_json, created_at)
        VALUES (%s, %s, 'invitation_approved', %s, NOW())
        """,
        (str(uuid.uuid4()), room.get("id"), Json({"campaign_id": campaign_id, "actor_id": actor_id})),
    )
    updated["public_url"] = make_sales_room_url(_text(updated.get("slug")))
    return updated
