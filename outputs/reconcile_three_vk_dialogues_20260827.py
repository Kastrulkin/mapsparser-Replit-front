#!/usr/bin/env python3
"""Reconcile three user-confirmed VK dialogue replies without dispatching anything."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from pg_db_utils import get_db_connection
from services.outreach_campaign_service import record_campaign_event
from services.outreach_relationship_service import upsert_relationship_from_reply
from services.outreach_safety_service import recipient_key, record_learning_event, strategy_fingerprint


ACTOR_ID = "a453a8b3-3b26-4c4e-81e3-1b973d4b8755"
SENDER_PROFILE_ID = "6010b010-555a-4c95-adfd-a19a5db87644"
NEXT_ACTION_AT = "2026-08-31T07:00:00+00:00"
RECORD_VERSION = "three_vk_active_dialogues_user_confirmed_20260827_v1"

ITEMS = [
    {
        "lead_id": "cabc5c8d-01fa-46d5-af44-9deef70db0a9",
        "workstream_id": "9d949e5b-029c-4d40-bcee-c32eaf7e0451",
        "name": "Intelligent Skin",
        "route": "https://vk.ru/intelligentskin",
        "contact_id": "e0754c12-4529-4b32-89c4-bbb09ff9a929",
        "inbound_provider_id": "manual-vk:intelligent-skin:license-objection:2026-08-26",
        "inbound": "добрый день! для рекламы косметологических услуг яндекс требует лицензии, скорее всего не получится",
        "classification": "question",
        "outbound": (
            "Пользователь вручную ответил в VK: пояснил, что предложенный маршрут не требует рекламного бюджета и включает "
            "работу с карточкой, локальными партнёрами и микроинфлюенсерами. Точный текст сообщения не сохранён."
        ),
        "text_exact": False,
        "next_step": "Проверить ответ Intelligent Skin на пояснение о безбюджетном привлечении",
    },
    {
        "lead_id": "329c6736-63c1-4fd5-8682-90e8d8ebe4dc",
        "workstream_id": "d35e19d3-0d1e-483e-b9db-59e29db79b1d",
        "name": "Новая Эра",
        "route": "https://vk.ru/new_era_cosm",
        "contact_id": "9f039193-0121-5293-87f6-b73472fd711b",
        "inbound_provider_id": "manual-vk:new-era:interested:2026-08-25",
        "inbound": "Да, заинтересовались",
        "classification": "interested",
        "outbound": """Спасибо за интерес!)

Я вручную перепроверил карточку «Новой Эры». Она живая: выходят новости, добавлены фотографии, подробно представлены услуги.

Но нашёл несколько несостыковок:

- в Картах и на сайтах указаны разные телефоны;
- одновременно работают два сайта с разными контактами и VK-сообществами;
- цены на некоторые одинаковые процедуры отличаются.

Здесь собрал аудит и порядок исправлений:
https://localos.pro/novaya-era-saint-petersburg-savushkina

Я бы начал с синхронизации телефонов, основного сайта и цен. Вы можете исправить это самостоятельно, а через неделю я повторно проверю карточку и напишу, что изменилось и что ещё осталось сделать.

Вы уже пробовали привлекать клиентов через локальных партнёров или микроинфлюенсеров?

Если да, напишите в двух словах, с кем и в каком формате работали. Я учту этот опыт и подберу новые варианты, чтобы не повторять то, что вы уже пробовали.""",
        "text_exact": True,
        "next_step": "Проверить ответ Новой Эры и при необходимости подобрать новые варианты партнёров и микроинфлюенсеров",
    },
    {
        "lead_id": "a7dc7911-2a00-45fa-8855-ec581ed63229",
        "workstream_id": "8c94cd77-0740-4fa1-9436-3d4932597512",
        "name": "Majesty",
        "route": "https://vk.ru/majestyclub",
        "contact_id": "ee8110b1-650b-4a43-8717-493623d05b62",
        "inbound_provider_id": "manual-vk:majesty:influencers-question:2026-08-26",
        "inbound": "Насчет местных инфлюенсеров интереснее. Расскажите",
        "classification": "question",
        "outbound": """Да, расскажу. Наша главная фишка — мы не покупаем рекламу у блогеров.

Мы подбираем локальных микроинфлюенсеров — обычных активных людей, которые живут или работают рядом, ходят в местные заведения и рассказывают о них своей аудитории.

С ними договариваемся на бартер и результат: например, человек приводит в Majesty 3–5 новых клиентов и получает бесплатную услугу. Денежного бюджета на размещение не требуется.

Есть ли у вас услуга, которую вы могли бы предложить в таком формате? Лучше с понятной себестоимостью и подходящую для первого знакомства с клиникой.""",
        "text_exact": True,
        "next_step": "Получить от Majesty услугу для бартера и подготовить 3–5 локальных микроинфлюенсеров",
    },
]


def _uuid(kind: str, item: dict[str, Any]) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:{RECORD_VERSION}:{item['lead_id']}:{kind}"))


def _rows(cursor: Any, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def _preflight(cursor: Any) -> None:
    cursor.execute(
        "SELECT id FROM users WHERE id=%s AND COALESCE(is_superadmin,FALSE) AND COALESCE(is_active,FALSE)",
        (ACTOR_ID,),
    )
    if not cursor.fetchone():
        raise RuntimeError("actor_not_active_superadmin")
    cursor.execute(
        "SELECT id FROM outreach_sender_profiles WHERE id=%s AND is_active=TRUE AND confirmed_at IS NOT NULL",
        (SENDER_PROFILE_ID,),
    )
    if not cursor.fetchone():
        raise RuntimeError("sender_profile_not_active")
    for item in ITEMS:
        cursor.execute(
            """SELECT lead.name,ws.workstream_type
               FROM prospectingleads lead JOIN lead_workstreams ws ON ws.lead_id=lead.id
               WHERE lead.id=%s AND ws.id=%s FOR UPDATE OF lead,ws""",
            (item["lead_id"], item["workstream_id"]),
        )
        row = dict(cursor.fetchone() or {})
        if row.get("name") != item["name"] or row.get("workstream_type") != "localos_sales":
            raise RuntimeError(f"identity_mismatch:{item['name']}:{row}")


def _ensure_contact(cursor: Any, item: dict[str, Any], occurred_at: datetime) -> str:
    cursor.execute(
        """SELECT id FROM lead_contact_points
           WHERE lead_id=%s AND contact_type='vk' AND normalized_value=%s""",
        (item["lead_id"], item["route"]),
    )
    existing = cursor.fetchone()
    if existing:
        return str(dict(existing)["id"])
    contact_id = _uuid("contact", item)
    cursor.execute(
        """INSERT INTO lead_contact_points (
             id,lead_id,contact_type,value,normalized_value,owner_type,source_url,source_type,
             provider,confidence,verification_status,observed_at,verified_at,metadata_json,created_at,updated_at
           ) VALUES (%s,%s,'vk',%s,%s,'company',%s,'manual','user_reported',1.0,'verified',%s,%s,%s,%s,%s)
           ON CONFLICT (lead_id,contact_type,normalized_value) DO UPDATE SET
             value=EXCLUDED.value,source_url=EXCLUDED.source_url,provider=EXCLUDED.provider,
             confidence=EXCLUDED.confidence,verification_status=EXCLUDED.verification_status,
             verified_at=EXCLUDED.verified_at,metadata_json=lead_contact_points.metadata_json || EXCLUDED.metadata_json,
             updated_at=EXCLUDED.updated_at
           RETURNING id""",
        (
            contact_id, item["lead_id"], item["route"], item["route"], item["route"],
            occurred_at, occurred_at, Json({"user_reported": True, "record_version": RECORD_VERSION}),
            occurred_at, occurred_at,
        ),
    )
    return str(dict(cursor.fetchone())["id"])


def _record_inbound(cursor: Any, item: dict[str, Any], occurred_at: datetime) -> None:
    inbound_id = _uuid("inbound", item)
    cursor.execute(
        """INSERT INTO outreach_inbound_events (
             id,campaign_id,touch_id,lead_id,workstream_id,sender_account_id,channel,provider_event_id,
             event_type,classification,is_human,stops_campaign,confidence,raw_payload_json,
             classified_by,occurred_at,created_at
           ) VALUES (%s,NULL,NULL,%s,%s,NULL,'vk',%s,'reply',%s,TRUE,TRUE,1.0,%s,'manual_user_reported',%s,NOW())
           ON CONFLICT DO NOTHING""",
        (
            inbound_id, item["lead_id"], item["workstream_id"], item["inbound_provider_id"],
            item["classification"], Json({"raw_reply": item["inbound"], "source": "user_reported"}), occurred_at,
        ),
    )
    upsert_relationship_from_reply(
        cursor,
        workstream_id=item["workstream_id"],
        lead_id=item["lead_id"],
        scope_type="business",
        business_id=None,
        raw_reply=item["inbound"],
        classification=item["classification"],
        provider_event_id=item["inbound_provider_id"],
    )


def _record_outbound(cursor: Any, item: dict[str, Any], contact_id: str, occurred_at: datetime) -> None:
    campaign_id = _uuid("campaign", item)
    touch_id = _uuid("touch", item)
    body = item["outbound"]
    body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    cursor.execute("SELECT id FROM outreach_campaigns WHERE id=%s", (campaign_id,))
    if cursor.fetchone():
        return
    cursor.execute(
        """UPDATE outreach_campaigns SET status='cancelled',stop_reason=%s,updated_at=NOW()
           WHERE workstream_id=%s AND status IN ('draft','approved','active','paused')""",
        (f"active_dialogue_reconciled:{RECORD_VERSION}", item["workstream_id"]),
    )
    cursor.execute(
        """UPDATE outreach_campaign_touches touch SET status='cancelled',preflight_reason='active_dialogue',updated_at=NOW()
           FROM outreach_campaigns campaign
           WHERE touch.campaign_id=campaign.id AND campaign.workstream_id=%s
             AND touch.status IN ('draft','approved','scheduled','queued','manual','awaiting_manual_send','manual_expired','needs_attention','paused')""",
        (item["workstream_id"],),
    )
    cursor.execute(
        """UPDATE outreachsendqueue SET delivery_status='cancelled',preflight_reason='active_dialogue',error_text=NULL,updated_at=NOW()
           WHERE workstream_id=%s AND delivery_status IN ('queued','retry','paused','sending')""",
        (item["workstream_id"],),
    )
    cursor.execute(
        "SELECT COALESCE(MAX(version),0)+1 AS version FROM outreach_campaigns WHERE workstream_id=%s",
        (item["workstream_id"],),
    )
    version = int(dict(cursor.fetchone())["version"])
    policy = {
        "record_only": True,
        "user_reported_manual_send": True,
        "external_dispatch_performed": False,
        "text_exact": item["text_exact"],
        "record_version": RECORD_VERSION,
        "body_sha256": body_sha256,
    }
    cursor.execute(
        """INSERT INTO outreach_campaigns (
             id,workstream_id,lead_id,scope_type,business_id,sender_profile_id,version,status,sender_mode,
             selected_offer_json,trust_strategy,decision_snapshot_json,policy_json,recipient_key,
             created_by,created_at,updated_at,stop_reason
           ) VALUES (%s,%s,%s,'platform',NULL,%s,%s,'completed','localos',%s,'founder_story',%s,%s,%s,%s,%s,%s,NULL)""",
        (
            campaign_id, item["workstream_id"], item["lead_id"], SENDER_PROFILE_ID, version,
            Json({"status": "user_reported_sent", "active_dialogue": True}),
            Json({"action": "record_active_dialogue_reply", "source": "user_reported"}),
            Json(policy), recipient_key(item["lead_id"]), ACTOR_ID, occurred_at, occurred_at,
        ),
    )
    strategy = {
        "workstream_type": "localos_sales",
        "sender_mode": "localos",
        "channel": "vk_manual",
        "delivery_mode": "user_reported_manual",
        "angle": "active_dialogue",
        "recipient_route": item["route"],
        "record_version": RECORD_VERSION,
    }
    delivery = {
        "manual_event": "sent",
        "source": "user_reported",
        "delivery_state": "user_reported_manual_sent",
        "occurred_at": occurred_at.isoformat(),
        "provider_message_id": None,
        "route": item["route"],
        "body_sha256": body_sha256,
        "text_exact": item["text_exact"],
        "record_version": RECORD_VERSION,
    }
    cursor.execute(
        """INSERT INTO outreach_campaign_touches (
             id,campaign_id,sequence_index,channel,contact_point_id,sender_account_id,angle_type,scheduled_at,
             status,subject,generated_text,approved_text,message_brief_json,quality_gate_json,delivery_json,
             strategy_fingerprint,strategy_json,created_at,updated_at
           ) VALUES (%s,%s,0,'vk_manual',%s,NULL,'active_dialogue',%s,'manual_sent',NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            touch_id, campaign_id, contact_id, occurred_at, body, body,
            Json({"channel_status": "manual_sent", "user_reported": True, "text_exact": item["text_exact"]}),
            Json({"passed": False, "manual_event_record_only": True, "reason_codes": ["USER_REPORTED_ACTIVE_DIALOGUE"]}),
            Json(delivery), strategy_fingerprint(strategy), Json(strategy), occurred_at, occurred_at,
        ),
    )
    record_campaign_event(
        cursor, campaign_id, "manual_sent", actor_id=ACTOR_ID, touch_id=touch_id,
        payload={**delivery, "active_dialogue": True},
    )
    record_learning_event(
        cursor,
        campaign={"id": campaign_id, "scope_type": "platform", "business_id": None, "workstream_type": "localos_sales"},
        touch={"id": touch_id, "strategy_fingerprint": strategy_fingerprint(strategy), "strategy_json": strategy},
        outcome_type="sent",
        payload={"source": "user_reported", "active_dialogue": True, "body_sha256": body_sha256},
        occurred_at=occurred_at,
    )
    cursor.execute(
        "SELECT id,room_id FROM sales_room_messages WHERE idempotency_key=%s",
        (f"outbound:{RECORD_VERSION}:{item['lead_id']}",),
    )
    if not cursor.fetchone():
        cursor.execute("SELECT id FROM sales_rooms WHERE workstream_id=%s ORDER BY created_at LIMIT 1", (item["workstream_id"],))
        room = cursor.fetchone()
        if room:
            room_id = str(dict(room)["id"])
            cursor.execute(
                """INSERT INTO sales_room_messages (
                     id,room_id,author_type,author_name,body_text,direction,source_channel,provider_event_id,
                     campaign_id,campaign_touch_id,delivery_status,occurred_at,idempotency_key,accepted_at,
                     processed_at,delivered_at,content_sha256,archive_status,content_retention_until,
                     metadata_retention_until,created_at
                   ) VALUES (%s,%s,'owner','Александр Демьянов',%s,'outbound','vk',%s,%s,%s,'sent',%s,%s,%s,%s,%s,%s,'pending',%s + INTERVAL '6 months',%s + INTERVAL '3 years',%s)""",
                (
                    _uuid("room_message", item), room_id, body, f"manual-user-reported:{touch_id}", campaign_id,
                    touch_id, occurred_at, f"outbound:{RECORD_VERSION}:{item['lead_id']}", occurred_at,
                    occurred_at, occurred_at, body_sha256, occurred_at, occurred_at, occurred_at,
                ),
            )


def _project_state(cursor: Any, item: dict[str, Any], contact_id: str, occurred_at: datetime) -> None:
    comment = f"Пользователь подтвердил ручную отправку ответа в VK; активный диалог. {item['next_step']}"
    cursor.execute(
        """UPDATE lead_workstreams SET status='replied',lifecycle_status='replied',status_reason=%s,
                  selected_channel='vk',selected_contact_point_id=%s,last_contact_at=%s,last_contact_channel='vk',
                  last_contact_comment=%s,next_action_at=%s,next_step=%s,state_changed_at=%s,updated_at=%s
           WHERE id=%s""",
        (
            item["classification"], contact_id, occurred_at, comment, NEXT_ACTION_AT,
            item["next_step"], occurred_at, occurred_at, item["workstream_id"],
        ),
    )
    cursor.execute(
        """UPDATE prospectingleads SET status='sent',pipeline_status='replied',selected_channel='vk',
                  last_contact_at=%s,last_contact_channel='vk',last_contact_comment=%s,
                  next_action_at=%s,updated_at=%s WHERE id=%s""",
        (occurred_at, comment, NEXT_ACTION_AT, occurred_at, item["lead_id"]),
    )
    cursor.execute(
        """INSERT INTO lead_timeline_events (id,lead_id,workstream_id,event_type,actor_id,comment,payload_json,created_at)
           VALUES (%s,%s,%s,'manual_dialogue_reply_sent',%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
        (
            _uuid("timeline", item), item["lead_id"], item["workstream_id"], ACTOR_ID, comment,
            Json({
                "channel": "vk", "recipient": item["route"], "source": "user_reported",
                "text_exact": item["text_exact"], "record_version": RECORD_VERSION,
                "next_action_at": NEXT_ACTION_AT,
            }), occurred_at,
        ),
    )


def _readback(cursor: Any) -> list[dict[str, Any]]:
    ids = [item["lead_id"] for item in ITEMS]
    return _rows(
        cursor,
        """SELECT lead.name,lead.pipeline_status,lead.last_contact_channel,lead.next_action_at,
                  ws.lifecycle_status,ws.next_step,
                  (SELECT COUNT(*) FROM outreach_campaign_touches touch JOIN outreach_campaigns campaign ON campaign.id=touch.campaign_id
                   WHERE campaign.lead_id=lead.id AND touch.status='manual_sent' AND touch.delivery_json->>'record_version'=%s) AS recorded_sends
           FROM prospectingleads lead JOIN lead_workstreams ws ON ws.lead_id=lead.id AND ws.workstream_type='localos_sales'
           WHERE lead.id=ANY(%s) ORDER BY lead.name""",
        (RECORD_VERSION, ids),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    conn = get_db_connection()
    conn.set_session(isolation_level="SERIALIZABLE", autocommit=False)
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        _preflight(cursor)
        if not args.apply:
            conn.rollback()
            print(json.dumps({"status": "dry_run_ready", "items": [x["name"] for x in ITEMS]}, ensure_ascii=False))
            return
        occurred_at = datetime.now(timezone.utc)
        for item in ITEMS:
            contact_id = _ensure_contact(cursor, item, occurred_at)
            _record_inbound(cursor, item, occurred_at)
            _record_outbound(cursor, item, contact_id, occurred_at)
            _project_state(cursor, item, contact_id, occurred_at)
        readback = _readback(cursor)
        if len(readback) != 3 or any(row.get("lifecycle_status") != "replied" or int(row.get("recorded_sends") or 0) != 1 for row in readback):
            raise RuntimeError(f"readback_guard_failed:{readback}")
        conn.commit()
        print(json.dumps({"status": "applied", "record_version": RECORD_VERSION, "readback": readback}, ensure_ascii=False, default=str, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
