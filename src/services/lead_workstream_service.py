"""Shared lead context model for LocalOS sales and client partnerships."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

LOCALOS_SALES = "localos_sales"
CLIENT_PARTNERSHIP = "client_partnership"
WORKSTREAM_TYPES = {LOCALOS_SALES, CLIENT_PARTNERSHIP}


def normalize_workstream_type(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    aliases = {
        "localos": LOCALOS_SALES,
        "localos_sales": LOCALOS_SALES,
        "client": CLIENT_PARTNERSHIP,
        "partner": CLIENT_PARTNERSHIP,
        "client_partnership": CLIENT_PARTNERSHIP,
        "partnership": CLIENT_PARTNERSHIP,
        "partnership_outreach": CLIENT_PARTNERSHIP,
        "client_outreach": LOCALOS_SALES,
    }
    return aliases.get(normalized)


def legacy_workstream_type(lead: dict[str, Any]) -> str:
    intent = str(lead.get("intent") or "client_outreach").strip().lower()
    return CLIENT_PARTNERSHIP if intent in {"partnership", "partnership_outreach"} else LOCALOS_SALES


def legacy_workstream(lead: dict[str, Any]) -> dict[str, Any]:
    workstream_type = legacy_workstream_type(lead)
    client_business_id = lead.get("business_id") if workstream_type == CLIENT_PARTNERSHIP else None
    client_business_name = lead.get("client_business_name") if workstream_type == CLIENT_PARTNERSHIP else None
    return {
        "id": None,
        "lead_id": lead.get("id"),
        "workstream_type": workstream_type,
        "client_business_id": client_business_id,
        "client_business_name": client_business_name,
        "status": lead.get("pipeline_status") or "unprocessed",
        "selected_channel": lead.get("selected_channel"),
        "next_action_at": lead.get("next_action_at"),
        "last_contact_at": lead.get("last_contact_at"),
        "last_contact_channel": lead.get("last_contact_channel"),
        "last_contact_comment": lead.get("last_contact_comment"),
        "room": None,
        "drafts_count": 0,
        "legacy": True,
    }


def _recipient_available(lead: dict[str, Any], channel: str) -> bool:
    normalized = str(channel or "").strip().lower()
    if normalized == "manual":
        return True
    if normalized == "telegram":
        return bool(str(lead.get("telegram_url") or "").strip())
    if normalized == "whatsapp":
        return bool(str(lead.get("whatsapp_url") or "").strip())
    if normalized == "email":
        return bool(str(lead.get("email") or "").strip())
    if normalized == "phone":
        return bool(str(lead.get("phone") or "").strip())
    return False


def build_channel_state(lead: dict[str, Any], workstream: dict[str, Any]) -> dict[str, Any]:
    channel = str(workstream.get("selected_channel") or "").strip().lower()
    if not channel:
        return {
            "code": "choose_channel",
            "label": "Канал не выбран",
            "recipient_available": False,
            "delivery_mode": "manual",
        }
    available = _recipient_available(lead, channel)
    if not available:
        return {
            "code": "missing_recipient",
            "label": "Нет контакта получателя",
            "channel": channel,
            "recipient_available": False,
            "delivery_mode": "manual",
        }
    return {
        "code": "manual_ready" if channel != "telegram" else "provider_or_manual",
        "label": "Готово к ручной отправке" if channel != "telegram" else "Контакт найден",
        "channel": channel,
        "recipient_available": True,
        "delivery_mode": "provider_or_manual" if channel == "telegram" else "manual",
    }


def build_room_state(workstream: dict[str, Any]) -> dict[str, Any]:
    room = workstream.get("room") if isinstance(workstream.get("room"), dict) else None
    if not room:
        return {"code": "missing", "label": "Не создана", "url": None}
    status = str(room.get("status") or "draft").strip().lower()
    labels = {
        "draft": "Готовится",
        "invitation_ready": "Готова",
        "ready": "Готова",
        "sent": "Отправлена",
        "active": "Есть активность",
        "viewed": "Есть активность",
    }
    return {
        "code": status,
        "label": labels.get(status, "Готова"),
        "url": room.get("public_url"),
    }


def build_next_action(lead: dict[str, Any], workstream: dict[str, Any]) -> dict[str, Any]:
    status = str(workstream.get("status") or "unprocessed").strip().lower()
    enrichment = workstream.get("enrichment_state")
    enrichment_status = ""
    if isinstance(enrichment, dict):
        enrichment_status = str(enrichment.get("status") or "").strip().lower()
    readiness = workstream.get("message_readiness")
    readiness_code = ""
    if isinstance(readiness, dict):
        readiness_code = str(readiness.get("code") or "").strip().lower()
    channel_state = build_channel_state(lead, workstream)
    room_state = build_room_state(workstream)
    if status in {"replied", "responded"}:
        return {"code": "record_result", "label": "Зафиксировать результат"}
    if status in {"contacted", "waiting_reply", "second_message_sent", "sent", "delivered"}:
        return {"code": "wait_or_follow_up", "label": "Проверить ответ"}
    if enrichment_status in {"queued", "collecting", "verifying", "researching", "drafting"}:
        return {"code": "prepare_message", "label": "Проверяем контакты"}
    if readiness_code == "needs_facts":
        return {"code": "complete_facts", "label": "Добавить факты"}
    if readiness_code == "needs_contact":
        return {"code": "find_contact", "label": "Найти контакт"}
    if readiness_code in {"ready", "review_required"}:
        return {"code": "review_message", "label": "Проверить письмо"}
    if channel_state["code"] in {"choose_channel", "missing_recipient"}:
        return {"code": "find_contact", "label": "Найти контакт"}
    if room_state["code"] == "missing":
        return {"code": "prepare_room", "label": "Подготовить комнату"}
    return {"code": "review_message", "label": "Проверить сообщение"}


def lead_kind(workstreams: Iterable[dict[str, Any]]) -> str:
    types = {str(item.get("workstream_type") or "") for item in workstreams}
    if LOCALOS_SALES in types and CLIENT_PARTNERSHIP in types:
        return "both"
    if CLIENT_PARTNERSHIP in types:
        return "partner"
    return "localos"


def _room_public_url(slug: Any) -> str | None:
    normalized = str(slug or "").strip()
    if not normalized:
        return None
    return f"https://localos.pro/room/{normalized}"


def attach_workstreams(conn, leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from psycopg2.extras import RealDictCursor

    lead_ids = [str(lead.get("id") or "").strip() for lead in leads]
    lead_ids = [lead_id for lead_id in lead_ids if lead_id]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if lead_ids:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT
                    ws.id, ws.lead_id, ws.workstream_type, ws.client_business_id,
                    client_business.name AS client_business_name,
                    client_business.address AS client_business_address,
                    ws.status, ws.selected_channel, ws.next_action_at,
                    ws.selected_contact_point_id,
                    ws.last_contact_at, ws.last_contact_channel, ws.last_contact_comment,
                    ws.created_at, ws.updated_at,
                    room.id AS room_id, room.status AS room_status, room.slug AS room_slug,
                    room.mode AS room_mode, room.updated_at AS room_updated_at,
                    COALESCE(draft_stats.drafts_count, 0)::INT AS drafts_count,
                    research.id AS research_id, research.score AS research_score,
                    research.qualification_stage AS research_stage,
                    research.signal_label AS research_signal_label,
                    research.score_breakdown AS research_score_breakdown,
                    research.why_now AS research_why_now,
                    research.signals_json AS research_signals,
                    research.sources_json AS research_sources,
                    research.contact_evidence_json AS research_contact_evidence,
                    research.suggested_opener AS research_suggested_opener,
                    research.opener_source_url AS research_opener_source_url,
                    research.limitations_json AS research_limitations,
                    research.message_brief_json AS research_message_brief,
                    research.message_readiness_json AS research_message_readiness,
                    research.researched_at AS research_researched_at
                    , contacts.contact_points AS contact_points
                    , contacts.contacts_count AS contacts_count
                    , contacts.verified_contacts_count AS verified_contacts_count
                    , selected_contact.contact_point AS selected_contact
                    , enrichment.id AS enrichment_id
                    , enrichment.status AS enrichment_status
                    , enrichment.current_phase AS enrichment_phase
                    , enrichment.readiness_json AS enrichment_readiness
                    , enrichment.error_message AS enrichment_error
                    , enrichment.updated_at AS enrichment_updated_at
                FROM lead_workstreams ws
                LEFT JOIN businesses client_business ON client_business.id = ws.client_business_id
                LEFT JOIN LATERAL (
                    SELECT sr.id, sr.status, sr.slug, sr.mode, sr.updated_at
                    FROM sales_rooms sr
                    WHERE sr.workstream_id = ws.id
                       OR (
                           sr.workstream_id IS NULL
                           AND sr.lead_id = ws.lead_id
                           AND (
                               (ws.workstream_type = 'client_partnership' AND sr.mode = 'partner_search'
                                    AND sr.business_id::text = ws.client_business_id)
                               OR (ws.workstream_type = 'localos_sales' AND sr.mode = 'client_search')
                           )
                       )
                    ORDER BY sr.updated_at DESC NULLS LAST, sr.created_at DESC
                    LIMIT 1
                ) room ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS drafts_count
                    FROM outreachmessagedrafts d
                    WHERE d.workstream_id = ws.id
                       OR (d.workstream_id IS NULL AND d.lead_id = ws.lead_id)
                ) draft_stats ON TRUE
                LEFT JOIN LATERAL (
                    SELECT r.*
                    FROM lead_workstream_research r
                    WHERE r.workstream_id = ws.id
                    ORDER BY r.researched_at DESC, r.created_at DESC
                    LIMIT 1
                ) research ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        COALESCE(
                            JSONB_AGG(
                                JSONB_BUILD_OBJECT(
                                    'id', cp.id,
                                    'type', cp.contact_type,
                                    'value', cp.value,
                                    'owner_type', cp.owner_type,
                                    'person_name', cp.person_name,
                                    'role_title', cp.role_title,
                                    'source_url', cp.source_url,
                                    'source_type', cp.source_type,
                                    'provider', cp.provider,
                                    'confidence', cp.confidence,
                                    'verification_status', cp.verification_status,
                                    'observed_at', cp.observed_at,
                                    'verified_at', cp.verified_at,
                                    'stale_after', cp.stale_after
                                )
                                ORDER BY
                                    CASE cp.verification_status
                                        WHEN 'verified' THEN 0 WHEN 'confirmed_source' THEN 1 ELSE 2
                                    END,
                                    cp.confidence DESC,
                                    cp.updated_at DESC
                            ),
                            '[]'::jsonb
                        ) AS contact_points,
                        COUNT(*) FILTER (WHERE cp.contact_type <> 'website')::INT AS contacts_count,
                        COUNT(*) FILTER (
                            WHERE cp.contact_type <> 'website'
                              AND cp.verification_status IN ('verified', 'confirmed_source')
                              AND (cp.stale_after IS NULL OR cp.stale_after > NOW())
                        )::INT AS verified_contacts_count
                    FROM lead_contact_points cp
                    WHERE cp.lead_id = ws.lead_id
                ) contacts ON TRUE
                LEFT JOIN LATERAL (
                    SELECT JSONB_BUILD_OBJECT(
                        'id', cp.id,
                        'type', cp.contact_type,
                        'value', cp.value,
                        'owner_type', cp.owner_type,
                        'person_name', cp.person_name,
                        'role_title', cp.role_title,
                        'source_url', cp.source_url,
                        'source_type', cp.source_type,
                        'provider', cp.provider,
                        'confidence', cp.confidence,
                        'verification_status', cp.verification_status,
                        'observed_at', cp.observed_at,
                        'verified_at', cp.verified_at,
                        'stale_after', cp.stale_after
                    ) AS contact_point
                    FROM lead_contact_points cp
                    WHERE cp.id = ws.selected_contact_point_id
                    LIMIT 1
                ) selected_contact ON TRUE
                LEFT JOIN LATERAL (
                    SELECT job.*
                    FROM lead_enrichment_jobs job
                    WHERE job.workstream_id = ws.id
                    ORDER BY job.created_at DESC
                    LIMIT 1
                ) enrichment ON TRUE
                WHERE ws.lead_id = ANY(%s)
                ORDER BY ws.created_at ASC
                """,
                (lead_ids,),
            )
            for row in cur.fetchall() or []:
                payload = dict(row)
                if payload.get("room_id"):
                    payload["room"] = {
                        "id": payload.pop("room_id"),
                        "status": payload.pop("room_status"),
                        "mode": payload.pop("room_mode"),
                        "updated_at": payload.pop("room_updated_at"),
                        "public_url": _room_public_url(payload.pop("room_slug")),
                    }
                else:
                    for key in ("room_id", "room_status", "room_mode", "room_updated_at", "room_slug"):
                        payload.pop(key, None)
                    payload["room"] = None
                payload["legacy"] = False
                if payload.get("research_id"):
                    researched_at = payload.pop("research_researched_at")
                    stale = False
                    if researched_at and hasattr(researched_at, "tzinfo"):
                        aware_researched_at = researched_at
                        if aware_researched_at.tzinfo is None:
                            aware_researched_at = aware_researched_at.replace(tzinfo=timezone.utc)
                        stale = aware_researched_at < datetime.now(timezone.utc) - timedelta(days=90)
                    payload["research"] = {
                        "id": payload.pop("research_id"),
                        "score": payload.pop("research_score"),
                        "qualification_stage": payload.pop("research_stage"),
                        "signal_label": payload.pop("research_signal_label"),
                        "score_breakdown": payload.pop("research_score_breakdown") or {},
                        "why_now": payload.pop("research_why_now"),
                        "signals": payload.pop("research_signals") or [],
                        "sources": payload.pop("research_sources") or [],
                        "contact_evidence": payload.pop("research_contact_evidence") or [],
                        "suggested_opener": payload.pop("research_suggested_opener"),
                        "opener_source_url": payload.pop("research_opener_source_url"),
                        "limitations": payload.pop("research_limitations") or [],
                        "message_brief": payload.pop("research_message_brief") or {},
                        "message_readiness": payload.pop("research_message_readiness") or {},
                        "researched_at": researched_at,
                        "stale": stale,
                    }
                else:
                    for key in (
                        "research_id", "research_score", "research_stage", "research_signal_label",
                        "research_score_breakdown", "research_why_now", "research_signals",
                        "research_sources", "research_contact_evidence", "research_suggested_opener",
                        "research_opener_source_url", "research_limitations", "research_message_brief",
                        "research_message_readiness",
                        "research_researched_at",
                    ):
                        payload.pop(key, None)
                    payload["research"] = None
                payload["contact_points"] = payload.get("contact_points") or []
                payload["contact_summary"] = {
                    "found": int(payload.pop("contacts_count") or 0),
                    "verified": int(payload.pop("verified_contacts_count") or 0),
                }
                payload["selected_recipient"] = payload.pop("selected_contact", None)
                if payload.get("enrichment_id"):
                    payload["enrichment_state"] = {
                        "id": str(payload.pop("enrichment_id")),
                        "status": payload.pop("enrichment_status"),
                        "phase": payload.pop("enrichment_phase"),
                        "error": payload.pop("enrichment_error"),
                        "updated_at": payload.pop("enrichment_updated_at"),
                    }
                    payload["message_readiness"] = payload.pop("enrichment_readiness") or {}
                else:
                    for key in (
                        "enrichment_id", "enrichment_status", "enrichment_phase",
                        "enrichment_error", "enrichment_updated_at",
                    ):
                        payload.pop(key, None)
                    payload.pop("enrichment_readiness", None)
                    payload["enrichment_state"] = None
                    payload["message_readiness"] = {
                        "code": "needs_contact",
                        "label": "Нужен контакт",
                        "missing": ["Запустите проверку контактов"],
                    }
                grouped[str(payload.get("lead_id") or "")].append(payload)
        except Exception:
            conn.rollback()

        try:
            cur.execute(
                """
                SELECT lead_id, match_json
                FROM partnershipleadartifacts
                WHERE lead_id = ANY(%s)
                """,
                (lead_ids,),
            )
            for row in cur.fetchall() or []:
                match_json = row.get("match_json") if isinstance(row.get("match_json"), dict) else {}
                score = match_json.get("match_score")
                for workstream in grouped.get(str(row.get("lead_id") or ""), []):
                    if workstream.get("workstream_type") == CLIENT_PARTNERSHIP:
                        workstream["service_compatibility_score"] = score
        except Exception:
            conn.rollback()

    result: list[dict[str, Any]] = []
    for raw_lead in leads:
        lead = dict(raw_lead)
        lead_id = str(lead.get("id") or "")
        workstreams = grouped.get(lead_id) or [legacy_workstream(lead)]
        serialized: list[dict[str, Any]] = []
        for raw_workstream in workstreams:
            workstream = dict(raw_workstream)
            workstream["channel_state"] = build_channel_state(lead, workstream)
            workstream["room_state"] = build_room_state(workstream)
            workstream["next_action"] = build_next_action(lead, workstream)
            serialized.append(workstream)
        lead["workstreams"] = serialized
        lead["lead_kind"] = lead_kind(serialized)
        lead["client_business_name"] = next(
            (
                item.get("client_business_name")
                for item in serialized
                if item.get("workstream_type") == CLIENT_PARTNERSHIP and item.get("client_business_name")
            ),
            lead.get("client_business_name"),
        )
        primary = serialized[0]
        lead["next_action"] = primary.get("next_action")
        lead["channel_state"] = primary.get("channel_state")
        lead["room_state"] = primary.get("room_state")
        result.append(lead)
    try:
        from services.knowledge_graph_service import attach_lead_knowledge_signals, knowledge_layer_enabled

        if knowledge_layer_enabled():
            return attach_lead_knowledge_signals(conn, result)
    except Exception:
        conn.rollback()
    return result


def create_workstream(
    conn,
    *,
    lead_id: str,
    workstream_type: str,
    client_business_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    from psycopg2.extras import RealDictCursor

    normalized_type = normalize_workstream_type(workstream_type)
    if normalized_type not in WORKSTREAM_TYPES:
        raise ValueError("Unsupported workstream_type")
    if normalized_type == CLIENT_PARTNERSHIP and not client_business_id:
        raise ValueError("client_business_id is required for client partnership")
    if normalized_type == LOCALOS_SALES:
        client_business_id = None

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM prospectingleads WHERE id = %s LIMIT 1", (lead_id,))
    if not cur.fetchone():
        raise LookupError("Lead not found")
    if client_business_id:
        cur.execute("SELECT id FROM businesses WHERE id = %s LIMIT 1", (client_business_id,))
        if not cur.fetchone():
            raise LookupError("Client business not found")

    if normalized_type == LOCALOS_SALES:
        cur.execute(
            """
            SELECT * FROM lead_workstreams
            WHERE lead_id = %s AND workstream_type = 'localos_sales'
            LIMIT 1
            """,
            (lead_id,),
        )
    else:
        cur.execute(
            """
            SELECT * FROM lead_workstreams
            WHERE lead_id = %s AND workstream_type = 'client_partnership'
              AND client_business_id = %s
            LIMIT 1
            """,
            (lead_id, client_business_id),
        )
    existing = cur.fetchone()
    if existing:
        payload = dict(existing)
        payload["reused"] = True
        return payload

    workstream_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO lead_workstreams (
            id, lead_id, workstream_type, client_business_id, status, created_by,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, NULLIF(%s, ''), 'unprocessed', NULLIF(%s, ''),
            NOW(), NOW()
        )
        RETURNING *
        """,
        (workstream_id, lead_id, normalized_type, client_business_id or "", actor_id or ""),
    )
    payload = dict(cur.fetchone())
    from services.contact_intelligence_service import enqueue_enrichment_job

    enrichment_job = enqueue_enrichment_job(cur, workstream_id)
    payload["enrichment_job_id"] = str(enrichment_job.get("id"))
    payload["reused"] = False
    return payload


def resolve_workstream(
    conn,
    *,
    lead_id: str,
    workstream_id: str | None,
    expected_type: str | None = None,
    client_business_id: str | None = None,
) -> dict[str, Any]:
    from psycopg2.extras import RealDictCursor

    cur = conn.cursor(cursor_factory=RealDictCursor)
    params: list[Any] = [lead_id]
    where = ["ws.lead_id = %s"]
    if workstream_id:
        where.append("ws.id = %s")
        params.append(workstream_id)
    normalized_type = normalize_workstream_type(expected_type)
    if normalized_type:
        where.append("ws.workstream_type = %s")
        params.append(normalized_type)
    if client_business_id:
        where.append("ws.client_business_id = %s")
        params.append(client_business_id)
    cur.execute(
        f"""
        SELECT ws.*, b.name AS client_business_name
        FROM lead_workstreams ws
        LEFT JOIN businesses b ON b.id = ws.client_business_id
        WHERE {' AND '.join(where)}
        ORDER BY ws.created_at ASC
        """,
        tuple(params),
    )
    rows = [dict(row) for row in cur.fetchall() or []]
    if not rows:
        raise LookupError("Lead workstream not found")
    if not workstream_id and len(rows) > 1:
        raise ValueError("workstream_id is required for a lead with multiple workstreams")
    return rows[0]


def update_workstream(
    conn,
    *,
    workstream_id: str,
    status: str | None = None,
    selected_channel: str | None = None,
    next_action_at: Any = None,
    last_contact: bool = False,
    last_contact_comment: str | None = None,
) -> dict[str, Any]:
    from psycopg2.extras import RealDictCursor

    assignments = ["updated_at = NOW()"]
    params: list[Any] = []
    if status:
        assignments.append("status = %s")
        params.append(status)
    if selected_channel is not None:
        assignments.append("selected_channel = %s")
        params.append(selected_channel or None)
    if next_action_at is not None:
        assignments.append("next_action_at = %s")
        params.append(next_action_at)
    if last_contact:
        assignments.append("last_contact_at = NOW()")
        assignments.append("last_contact_channel = COALESCE(%s, selected_channel)")
        params.append(selected_channel or None)
        assignments.append("last_contact_comment = %s")
        params.append(last_contact_comment)
    params.append(workstream_id)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        f"""
        UPDATE lead_workstreams
        SET {', '.join(assignments)}
        WHERE id = %s
        RETURNING *
        """,
        tuple(params),
    )
    row = cur.fetchone()
    if not row:
        raise LookupError("Lead workstream not found")
    return dict(row)
