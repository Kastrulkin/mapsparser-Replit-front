#!/usr/bin/env python3
"""Record one user-reported Estem Telegram send without dispatch or queue writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from api.prospecting.access_schema import (
    PIPELINE_CONTACTED,
    _apply_pipeline_transition,
    _record_lead_timeline_event,
)
from pg_db_utils import get_db_connection
from services.lead_workstream_service import update_workstream
from services.outreach_campaign_service import (
    change_campaign_status,
    record_campaign_event,
)
from services.outreach_safety_service import (
    recipient_key,
    record_learning_event,
    strategy_fingerprint,
)


LEAD_ID = "a759b6a9-0f88-40cb-9497-26f6bd3df922"
WORKSTREAM_ID = "a435bff8-8a92-45db-bb06-912206648e2d"
OLD_CAMPAIGN_ID = "b5bb2223-6890-4f8b-a6b2-71e714fdd773"
ACTOR_ID = "a453a8b3-3b26-4c4e-81e3-1b973d4b8755"
SENDER_PROFILE_ID = "6010b010-555a-4c95-adfd-a19a5db87644"
DIRECT_ROUTE = "https://t.me/clinicestem"
DIRECT_HANDLE = "@clinicestem"
EVIDENCE_URL = "https://t.me/estemclinic/2084"
SOURCE_CHANNEL_URL = "https://t.me/estemclinic"
RECORD_VERSION = "estem_user_reported_manual_send_v1"

BODY = """Здравствуйте!

Меня зовут Александр, основатель ЛокалОС.

Вижу, вы активно ведёте соцсети, например 2 августа на канале Эстем вышел разбор ботулинотерапии с тремя преимуществами.

Посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.

С ЛокалОС клиники управляют контентом сразу для Telegram, VK, Яндекс Карт и других площадок.
Некоторые подключают CRM и мы автоматически готовим посты из выполненных услуг - это экономит до нескольких часов в день для ответственного. От 1200 рублей в месяц.

Вам могло бы быть интересно так сэкономить время?"""

BODY_SHA256 = hashlib.sha256(BODY.encode("utf-8")).hexdigest()
CAMPAIGN_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:{LEAD_ID}:{RECORD_VERSION}:{BODY_SHA256}"))
TOUCH_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:{CAMPAIGN_ID}:touch:0"))
CONTACT_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:{LEAD_ID}:telegram:{DIRECT_ROUTE}"))


def _rows(cursor: Any, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def _snapshot(cursor: Any) -> dict[str, Any]:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "lead": _rows(cursor, "SELECT * FROM prospectingleads WHERE id=%s", (LEAD_ID,)),
        "workstream": _rows(cursor, "SELECT * FROM lead_workstreams WHERE id=%s", (WORKSTREAM_ID,)),
        "contacts": _rows(cursor, "SELECT * FROM lead_contact_points WHERE lead_id=%s ORDER BY created_at", (LEAD_ID,)),
        "campaigns": _rows(cursor, "SELECT * FROM outreach_campaigns WHERE workstream_id=%s ORDER BY version,created_at", (WORKSTREAM_ID,)),
        "touches": _rows(
            cursor,
            """SELECT t.* FROM outreach_campaign_touches t
               JOIN outreach_campaigns c ON c.id=t.campaign_id
               WHERE c.workstream_id=%s ORDER BY c.version,t.sequence_index""",
            (WORKSTREAM_ID,),
        ),
        "campaign_events": _rows(
            cursor,
            """SELECT e.* FROM outreach_campaign_events e
               JOIN outreach_campaigns c ON c.id=e.campaign_id
               WHERE c.workstream_id=%s ORDER BY e.created_at""",
            (WORKSTREAM_ID,),
        ),
        "learning_events": _rows(cursor, "SELECT * FROM outreach_learning_events WHERE workstream_type='localos_sales' AND campaign_id IN (SELECT id FROM outreach_campaigns WHERE workstream_id=%s) ORDER BY created_at", (WORKSTREAM_ID,)),
        "queue": _rows(
            cursor,
            """SELECT q.* FROM outreachsendqueue q
               JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
               JOIN outreach_campaigns c ON c.id=t.campaign_id
               WHERE c.workstream_id=%s ORDER BY q.created_at""",
            (WORKSTREAM_ID,),
        ),
        "inbound": _rows(cursor, "SELECT * FROM outreach_inbound_events WHERE workstream_id=%s ORDER BY created_at", (WORKSTREAM_ID,)),
        "suppressions": _rows(cursor, "SELECT * FROM outreach_suppressions WHERE workstream_id=%s OR lead_id=%s ORDER BY created_at", (WORKSTREAM_ID, LEAD_ID)),
        "timeline": _rows(cursor, "SELECT * FROM lead_timeline_events WHERE lead_id=%s ORDER BY created_at", (LEAD_ID,)),
    }


def _json_safe(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _preflight(cursor: Any) -> dict[str, Any]:
    cursor.execute(
        """SELECT l.*,ws.status AS ws_status,ws.lifecycle_status,ws.workstream_type,
                  ws.last_contact_at AS ws_last_contact_at
           FROM prospectingleads l JOIN lead_workstreams ws ON ws.lead_id=l.id
           WHERE l.id=%s AND ws.id=%s FOR UPDATE OF l,ws""",
        (LEAD_ID, WORKSTREAM_ID),
    )
    state = dict(cursor.fetchone() or {})
    if state.get("name") != "Эстем" or state.get("workstream_type") != "localos_sales":
        raise RuntimeError("identity_or_workstream_mismatch")

    cursor.execute(
        "SELECT id FROM users WHERE id=%s AND COALESCE(is_superadmin,FALSE) AND COALESCE(is_active,FALSE)",
        (ACTOR_ID,),
    )
    if not cursor.fetchone():
        raise RuntimeError("actor_not_active_superadmin")
    cursor.execute(
        """SELECT id FROM outreach_sender_profiles
           WHERE id=%s AND workstream_type='localos_sales' AND client_business_id IS NULL
             AND is_active=TRUE AND confirmed_at IS NOT NULL""",
        (SENDER_PROFILE_ID,),
    )
    if not cursor.fetchone():
        raise RuntimeError("confirmed_sender_profile_missing")

    cursor.execute(
        """SELECT evidence_json,researched_at,report_hash FROM lead_workstream_research
           WHERE workstream_id=%s ORDER BY researched_at DESC NULLS LAST,created_at DESC LIMIT 1""",
        (WORKSTREAM_ID,),
    )
    research = dict(cursor.fetchone() or {})
    evidence_text = json.dumps(research.get("evidence_json") or {}, ensure_ascii=False)
    if EVIDENCE_URL not in evidence_text or "ботулин" not in evidence_text.lower():
        raise RuntimeError("source_evidence_missing")

    cursor.execute(
        """SELECT COUNT(*) AS count FROM lead_contact_points
           WHERE lead_id<>%s AND contact_type='telegram' AND normalized_value=%s""",
        (LEAD_ID, DIRECT_ROUTE),
    )
    if int(dict(cursor.fetchone()).get("count") or 0):
        raise RuntimeError("direct_route_belongs_to_another_lead")

    cursor.execute(
        """SELECT
          (SELECT COUNT(*) FROM outreach_suppressions s
             WHERE (s.expires_at IS NULL OR s.expires_at>NOW())
               AND (s.lead_id=%s OR NULLIF(s.recipient_key,'')=%s)) AS suppressions,
          (SELECT COUNT(*) FROM outreach_inbound_events i WHERE i.lead_id=%s AND i.is_human) AS human_inbound,
          (SELECT COUNT(*) FROM outreach_campaign_touches t JOIN outreach_campaigns c ON c.id=t.campaign_id
             WHERE c.lead_id=%s AND t.status IN ('manual_sent','sent','delivered')) AS sent_touches,
          (SELECT COUNT(*) FROM outreachsendqueue q JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
             JOIN outreach_campaigns c ON c.id=t.campaign_id WHERE c.lead_id=%s
             AND q.delivery_status IN ('queued','retry','sending','paused')) AS live_queue,
          (SELECT COUNT(*) FROM outreach_campaigns c WHERE c.lead_id=%s
             AND c.status IN ('approved','active','paused')) AS active_campaigns""",
        (LEAD_ID, recipient_key(LEAD_ID), LEAD_ID, LEAD_ID, LEAD_ID, LEAD_ID),
    )
    safety = dict(cursor.fetchone())

    cursor.execute("SELECT * FROM outreach_campaigns WHERE id=%s", (CAMPAIGN_ID,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("SELECT * FROM outreach_campaign_touches WHERE id=%s AND campaign_id=%s", (TOUCH_ID, CAMPAIGN_ID))
        existing_touch = dict(cursor.fetchone() or {})
        if (
            existing_touch.get("generated_text") == BODY
            and existing_touch.get("status") == "manual_sent"
            and str((existing_touch.get("delivery_json") or {}).get("body_sha256") or "") == BODY_SHA256
        ):
            return {"idempotent": True, "state": state, "safety": safety, "research": research}
        raise RuntimeError("idempotency_key_conflict")

    if any(int(safety.get(key) or 0) for key in safety):
        raise RuntimeError(f"safety_blocked:{safety}")
    cursor.execute("SELECT id,version,status FROM outreach_campaigns WHERE workstream_id=%s ORDER BY version,created_at", (WORKSTREAM_ID,))
    campaigns = [dict(row) for row in cursor.fetchall()]
    if campaigns != [{"id": OLD_CAMPAIGN_ID, "version": 1, "status": "draft"}]:
        raise RuntimeError(f"unexpected_campaign_state:{campaigns}")
    return {"idempotent": False, "state": state, "safety": safety, "research": research}


def _readback(cursor: Any) -> dict[str, Any]:
    cursor.execute(
        """SELECT c.id,c.version,c.status,c.stop_reason,c.policy_json,
                  t.id AS touch_id,t.channel,t.status AS touch_status,t.contact_point_id,
                  t.generated_text,t.approved_text,t.delivery_json,t.message_brief_json,t.quality_gate_json
           FROM outreach_campaigns c JOIN outreach_campaign_touches t ON t.campaign_id=c.id
           WHERE c.id=%s AND t.id=%s""",
        (CAMPAIGN_ID, TOUCH_ID),
    )
    campaign = dict(cursor.fetchone() or {})
    cursor.execute("SELECT id,status,stop_reason FROM outreach_campaigns WHERE id=%s", (OLD_CAMPAIGN_ID,))
    old_campaign = dict(cursor.fetchone() or {})
    cursor.execute("SELECT id,contact_type,value,normalized_value,verification_status,metadata_json FROM lead_contact_points WHERE id=%s", (CONTACT_ID,))
    contact = dict(cursor.fetchone() or {})
    cursor.execute("SELECT status,pipeline_status,last_contact_at,last_contact_channel,last_contact_comment FROM prospectingleads WHERE id=%s", (LEAD_ID,))
    lead = dict(cursor.fetchone() or {})
    cursor.execute("SELECT status,lifecycle_status,selected_channel,selected_contact_point_id,last_contact_at,last_contact_channel,last_contact_comment,next_step FROM lead_workstreams WHERE id=%s", (WORKSTREAM_ID,))
    workstream = dict(cursor.fetchone() or {})
    cursor.execute(
        """SELECT COUNT(*) AS count FROM outreachsendqueue q
           JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
           JOIN outreach_campaigns c ON c.id=t.campaign_id WHERE c.workstream_id=%s""",
        (WORKSTREAM_ID,),
    )
    queue_count = int(dict(cursor.fetchone()).get("count") or 0)
    cursor.execute("SELECT COUNT(*) AS count FROM outreach_campaign_touches WHERE campaign_id=%s", (CAMPAIGN_ID,))
    touch_count = int(dict(cursor.fetchone()).get("count") or 0)
    return {
        "campaign": campaign,
        "old_campaign": old_campaign,
        "contact": contact,
        "lead": lead,
        "workstream": workstream,
        "queue_count": queue_count,
        "touch_count": touch_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    conn = get_db_connection()
    conn.set_session(isolation_level="SERIALIZABLE", autocommit=False)
    backup_path = None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        preflight = _preflight(cursor)
        if preflight["idempotent"]:
            readback = _readback(cursor)
            conn.rollback()
            print(_json_safe({
                "status": "idempotent_existing",
                "body_sha256": BODY_SHA256,
                "campaign_id": CAMPAIGN_ID,
                "touch_id": TOUCH_ID,
                "contact_id": CONTACT_ID,
                "readback": readback,
            }))
            return

        before = _snapshot(cursor)
        if not args.apply:
            conn.rollback()
            print(_json_safe({
                "status": "dry_run_ready",
                "body_sha256": BODY_SHA256,
                "campaign_id": CAMPAIGN_ID,
                "touch_id": TOUCH_ID,
                "contact_id": CONTACT_ID,
                "preflight": preflight,
                "before_counts": {key: len(value) for key, value in before.items() if isinstance(value, list)},
                "would_write": {"campaigns": 2, "touches": 5, "new_queue": 0, "new_sent_touch": 1},
            }))
            return

        if os.getenv("ESTEM_MANUAL_SUCCESS_APPROVED") != "yes":
            raise RuntimeError("explicit_apply_guard_missing")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = Path("/app/db_backups") / f"localos-estem-manual-success-{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=False)
        backup_path = backup_dir / "prewrite.json"
        backup_path.write_text(_json_safe(before), encoding="utf-8")
        (backup_dir / "manifest.json").write_text(_json_safe({
            "schema": "localos_estem_manual_success_backup_v1",
            "lead_id": LEAD_ID,
            "workstream_id": WORKSTREAM_ID,
            "body_sha256": BODY_SHA256,
            "campaign_id": CAMPAIGN_ID,
            "touch_id": TOUCH_ID,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")

        cursor.execute("SELECT clock_timestamp() AS occurred_at")
        occurred_at = dict(cursor.fetchone())["occurred_at"]
        note = "Пользователь сообщил об успешной ручной отправке в Telegram; точное время отправки не указано, сохранено время получения сообщения."

        cursor.execute(
            """INSERT INTO lead_contact_points (
                 id,lead_id,contact_type,value,normalized_value,owner_type,source_url,source_type,
                 provider,confidence,verification_status,observed_at,verified_at,metadata_json,created_at,updated_at
               ) VALUES (%s,%s,'telegram',%s,%s,'company',%s,'manual','user_reported',1.0,'verified',%s,%s,%s,%s,%s)
               ON CONFLICT (lead_id,contact_type,normalized_value) DO UPDATE SET
                 value=EXCLUDED.value,source_url=EXCLUDED.source_url,source_type=EXCLUDED.source_type,
                 provider=EXCLUDED.provider,confidence=EXCLUDED.confidence,verification_status=EXCLUDED.verification_status,
                 verified_at=EXCLUDED.verified_at,metadata_json=lead_contact_points.metadata_json || EXCLUDED.metadata_json,
                 updated_at=EXCLUDED.updated_at
               RETURNING id""",
            (
                CONTACT_ID, LEAD_ID, DIRECT_ROUTE, DIRECT_ROUTE, DIRECT_ROUTE,
                occurred_at, occurred_at, Json({
                    "user_reported": True,
                    "direct_messageability_verified": True,
                    "handle": DIRECT_HANDLE,
                    "record_version": RECORD_VERSION,
                    "distinct_from_public_source_channel": True,
                    "public_source_channel": SOURCE_CHANNEL_URL,
                    "evidence_url": EVIDENCE_URL,
                }), occurred_at, occurred_at,
            ),
        )
        actual_contact_id = str(dict(cursor.fetchone())["id"])
        if actual_contact_id != CONTACT_ID:
            raise RuntimeError(f"unexpected_existing_contact_id:{actual_contact_id}")

        cursor.execute("SELECT COALESCE(MAX(version),0)+1 AS version FROM outreach_campaigns WHERE workstream_id=%s", (WORKSTREAM_ID,))
        version = int(dict(cursor.fetchone())["version"])
        if version != 2:
            raise RuntimeError(f"unexpected_next_campaign_version:{version}")
        policy = {
            "stop_on_reply": True,
            "auto_queue_disabled": True,
            "record_only": True,
            "user_reported_manual_send": True,
            "exact_send_timestamp_available": False,
            "occurred_at_basis": "receipt_time",
            "remaining_touches": "not_persisted_no_exact_user_approved_copy",
            "record_version": RECORD_VERSION,
            "body_sha256": BODY_SHA256,
        }
        cursor.execute(
            """INSERT INTO outreach_campaigns (
                 id,workstream_id,lead_id,scope_type,business_id,sender_profile_id,version,status,
                 sender_mode,selected_offer_json,trust_strategy,decision_snapshot_json,policy_json,
                 recipient_key,created_by,created_at,updated_at,stop_reason
               ) VALUES (%s,%s,%s,'platform',NULL,%s,%s,'completed','localos',%s,'founder_story',%s,%s,%s,%s,%s,%s,%s)""",
            (
                CAMPAIGN_ID, WORKSTREAM_ID, LEAD_ID, SENDER_PROFILE_ID, version,
                Json({"status": "user_reported_sent", "text_preserved_verbatim": True}),
                Json({"action": "record_manual_success", "source": "user_reported", "record_version": RECORD_VERSION}),
                Json(policy), recipient_key(LEAD_ID), ACTOR_ID, occurred_at, occurred_at,
                "single_user_reported_touch_recorded_no_remaining_approved_drafts",
            ),
        )
        strategy = {
            "workstream_type": "localos_sales",
            "sender_mode": "localos",
            "channel": "telegram",
            "delivery_mode": "user_reported_manual",
            "angle": "content_operations",
            "source_url": EVIDENCE_URL,
            "recipient_route": DIRECT_ROUTE,
            "record_version": RECORD_VERSION,
        }
        delivery = {
            "manual_event": "sent",
            "source": "user_reported",
            "delivery_state": "user_reported_manual_sent",
            "occurred_at": occurred_at.isoformat(),
            "occurred_at_basis": "receipt_time_exact_send_timestamp_unavailable",
            "exact_send_timestamp_available": False,
            "provider_message_id": None,
            "route": DIRECT_ROUTE,
            "handle": DIRECT_HANDLE,
            "body_sha256": BODY_SHA256,
        }
        brief = {
            "channel_status": "manual_sent",
            "evidence_kind": "telegram_post",
            "source_url": EVIDENCE_URL,
            "source_channel_url": SOURCE_CHANNEL_URL,
            "observation": "2 августа в канале Эстем вышел разбор ботулинотерапии с тремя преимуществами.",
            "recipient_route": DIRECT_ROUTE,
            "recipient_handle": DIRECT_HANDLE,
            "direct_messageability_verified": True,
            "generation_source": "user_reported_manual_send",
            "user_reported": True,
            "text_preserved_verbatim": True,
            "body_sha256": BODY_SHA256,
            "occurred_at": occurred_at.isoformat(),
            "occurred_at_basis": "receipt_time_exact_send_timestamp_unavailable",
            "not_retroactively_approved_by_quality_gate": True,
        }
        gate = {
            "passed": False,
            "verdict": "revise",
            "total_score": 0,
            "max_score": 18,
            "reason_codes": ["USER_REPORTED_SENT_TEXT_RECORDED_VERBATIM"],
            "manual_event_record_only": True,
            "not_retroactive_approval": True,
        }
        cursor.execute(
            """INSERT INTO outreach_campaign_touches (
                 id,campaign_id,sequence_index,channel,contact_point_id,sender_account_id,
                 angle_type,scheduled_at,status,subject,generated_text,approved_text,
                 message_brief_json,quality_gate_json,delivery_json,strategy_fingerprint,strategy_json,
                 created_at,updated_at
               ) VALUES (%s,%s,0,'telegram',%s,NULL,'content_operations',%s,'manual_sent',NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                TOUCH_ID, CAMPAIGN_ID, CONTACT_ID, occurred_at, BODY, BODY,
                Json(brief), Json(gate), Json(delivery), strategy_fingerprint(strategy), Json(strategy),
                occurred_at, occurred_at,
            ),
        )
        record_campaign_event(
            cursor,
            CAMPAIGN_ID,
            "campaign_created_from_user_reported_manual_send",
            actor_id=ACTOR_ID,
            touch_id=TOUCH_ID,
            payload={
                "source": "user_reported",
                "record_version": RECORD_VERSION,
                "body_sha256": BODY_SHA256,
                "occurred_at": occurred_at.isoformat(),
                "occurred_at_basis": "receipt_time_exact_send_timestamp_unavailable",
                "remaining_touches_persisted": 0,
            },
        )
        record_campaign_event(
            cursor,
            CAMPAIGN_ID,
            "manual_sent",
            actor_id=ACTOR_ID,
            touch_id=TOUCH_ID,
            payload=delivery,
        )
        learning_id = record_learning_event(
            cursor,
            campaign={
                "id": CAMPAIGN_ID,
                "scope_type": "platform",
                "business_id": None,
                "workstream_type": "localos_sales",
            },
            touch={"id": TOUCH_ID, "strategy_fingerprint": strategy_fingerprint(strategy), "strategy_json": strategy},
            outcome_type="sent",
            payload={
                "source": "user_reported",
                "manual_event": "sent",
                "body_sha256": BODY_SHA256,
                "provider_message_id": None,
                "occurred_at_basis": "receipt_time_exact_send_timestamp_unavailable",
            },
            occurred_at=occurred_at,
        )

        change_campaign_status(cursor, OLD_CAMPAIGN_ID, "cancel", user_id=ACTOR_ID)
        superseded_reason = f"superseded_by_{CAMPAIGN_ID}"
        cursor.execute("UPDATE outreach_campaigns SET stop_reason=%s,updated_at=%s WHERE id=%s", (superseded_reason, occurred_at, OLD_CAMPAIGN_ID))
        record_campaign_event(
            cursor,
            OLD_CAMPAIGN_ID,
            "campaign_superseded",
            actor_id=ACTOR_ID,
            payload={"superseded_by": CAMPAIGN_ID, "reason": "user_reported_manual_send", "body_sha256": BODY_SHA256},
        )

        _apply_pipeline_transition(
            cursor,
            lead_id=LEAD_ID,
            pipeline_status=PIPELINE_CONTACTED,
            actor_id=ACTOR_ID,
            comment=note,
            last_contact_channel="telegram",
            last_contact_comment=note,
            set_last_contact_at=True,
        )
        update_workstream(
            conn,
            workstream_id=WORKSTREAM_ID,
            status="contacted",
            selected_channel="telegram",
            last_contact=True,
            last_contact_comment=note,
        )
        cursor.execute(
            """UPDATE lead_workstreams SET lifecycle_status='waiting_reply',status_reason=%s,
                      next_step=%s,selected_contact_point_id=%s,state_changed_at=%s,updated_at=%s
               WHERE id=%s""",
            (
                "user_reported_manual_sent",
                "Дождаться ответа; при ответе остановить дальнейшие касания",
                CONTACT_ID, occurred_at, occurred_at, WORKSTREAM_ID,
            ),
        )
        _record_lead_timeline_event(
            cursor,
            lead_id=LEAD_ID,
            workstream_id=WORKSTREAM_ID,
            event_type="manual_contact_marked",
            actor_id=ACTOR_ID,
            comment=note,
            payload={
                "channel": "telegram",
                "route": DIRECT_ROUTE,
                "handle": DIRECT_HANDLE,
                "campaign_id": CAMPAIGN_ID,
                "touch_id": TOUCH_ID,
                "source": "user_reported",
                "body_sha256": BODY_SHA256,
                "occurred_at": occurred_at.isoformat(),
                "occurred_at_basis": "receipt_time_exact_send_timestamp_unavailable",
            },
        )

        readback = _readback(cursor)
        if (
            readback["campaign"].get("status") != "completed"
            or readback["campaign"].get("touch_status") != "manual_sent"
            or readback["campaign"].get("generated_text") != BODY
            or readback["campaign"].get("approved_text") != BODY
            or readback["old_campaign"].get("status") != "cancelled"
            or readback["lead"].get("pipeline_status") != "contacted"
            or readback["workstream"].get("lifecycle_status") != "waiting_reply"
            or readback["queue_count"] != 0
            or readback["touch_count"] != 1
        ):
            raise RuntimeError(f"readback_guard_failed:{readback}")
        conn.commit()
        print(_json_safe({
            "status": "applied",
            "backup_path": str(backup_path),
            "body_sha256": BODY_SHA256,
            "campaign_id": CAMPAIGN_ID,
            "touch_id": TOUCH_ID,
            "contact_id": CONTACT_ID,
            "learning_event_id": learning_id,
            "occurred_at": occurred_at,
            "occurred_at_basis": "receipt_time_exact_send_timestamp_unavailable",
            "readback": readback,
            "deltas": {
                "campaigns_created": 1,
                "old_campaigns_cancelled": 1,
                "new_touches": 1,
                "manual_sent_touches": 1,
                "new_queue_rows": 0,
                "later_drafts_persisted": 0,
                "actual_sends": 0,
            },
        }))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
