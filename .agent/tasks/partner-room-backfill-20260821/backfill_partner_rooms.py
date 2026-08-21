from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from psycopg2.extras import Json, RealDictCursor

from api.admin_prospecting import _prepare_partnership_sales_room
from pg_db_utils import get_db_connection


BUSINESS_ID = "cb674174-8b3d-41a3-8277-525c849935f2"
USER_ID = "a453a8b3-3b26-4c4e-81e3-1b973d4b8755"
DOCUMENT_ID = "1iTcLcZMPIFr8vaEAYJD_bL1Zjqox6Kfyadg0nc7jOXg"

TITLE_TO_LEAD_NAME = {
    "Спортивный клуб Gymfusion (Кабриоль)": "Спортивный клуб Gymfusion",
}

MISSING_LEADS = {
    "Лидер Спорт": {
        "category": "Фитнес-клуб",
        "address": "ТРК «Гранд Каньон», 3 этаж",
        "city": "Санкт-Петербург",
        "source_suffix": "lider-sport",
    },
    "МХК «Спартак СПб»": {
        "category": "Хоккейный клуб",
        "address": "Территория комплекса «Гранд Каньон»",
        "city": "Санкт-Петербург",
        "source_suffix": "mhk-spartak-spb",
    },
}

TERMINAL_NAMES = {
    "Lounge-студия DIAMII Beauty",
    "UME",
    "White Warriors",
}


def normalize_lead_name(title: str) -> str:
    return TITLE_TO_LEAD_NAME.get(title, title)


def load_records(path: Path) -> tuple[list[dict], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    if len(records) != 56:
        raise RuntimeError(f"Expected 56 records, got {len(records)}")
    revision_id = str(payload.get("source_revision_id") or "")
    return records, revision_id


def load_scoped_row(cur, lead_name: str) -> dict:
    cur.execute(
        """
        SELECT
            l.id AS lead_id,
            l.name,
            l.status AS lead_status,
            l.pipeline_status AS lead_pipeline_status,
            l.partnership_stage,
            l.disqualification_reason,
            l.disqualification_comment,
            w.id AS workstream_id,
            w.status AS workstream_status,
            w.lifecycle_status,
            w.status_reason,
            w.next_step,
            w.selected_channel,
            w.last_contact_at,
            w.last_contact_channel,
            w.last_contact_comment,
            r.id AS room_id,
            r.slug,
            r.status AS room_status,
            r.visibility,
            r.created_at AS room_created_at,
            (
                SELECT COUNT(*)
                FROM sales_room_messages m
                WHERE m.room_id = r.id
                  AND m.direction = 'outbound'
            ) AS outbound_count
        FROM lead_workstreams w
        JOIN prospectingleads l ON l.id = w.lead_id
        LEFT JOIN sales_rooms r ON r.workstream_id = w.id
        WHERE w.client_business_id = %s
          AND w.workstream_type = 'client_partnership'
          AND LOWER(l.name) = LOWER(%s)
        ORDER BY w.created_at ASC
        LIMIT 1
        """,
        (BUSINESS_ID, lead_name),
    )
    row = cur.fetchone()
    return dict(row) if row else {}


def build_snapshot(records: list[dict]) -> dict:
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        rows = []
        for record in records:
            title = str(record.get("title") or "").strip()
            lead_name = normalize_lead_name(title)
            row = load_scoped_row(cur, lead_name)
            rows.append({
                "title": title,
                "lead_name": lead_name,
                "body_text": str(record.get("body_text") or ""),
                "before": row or None,
            })
        return {
            "business_id": BUSINESS_ID,
            "document_id": DOCUMENT_ID,
            "records": rows,
        }
    finally:
        conn.close()


def ensure_missing_leads() -> list[str]:
    created = []
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        for lead_name, spec in MISSING_LEADS.items():
            if load_scoped_row(cur, lead_name):
                continue
            lead_id = str(uuid.uuid4())
            workstream_id = str(uuid.uuid4())
            dedupe_key = f"{BUSINESS_ID}:partnership_outreach:{lead_name.lower()}"
            source_external_id = f"google_doc:{DOCUMENT_ID}:manual-backfill-{spec['source_suffix']}"
            cur.execute(
                """
                INSERT INTO prospectingleads (
                    id, name, address, city, category, source, source_external_id,
                    source_kind, source_provider, dedupe_key, status, pipeline_status,
                    business_id, intent, partnership_stage, created_by,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, 'google_doc_partnership_import', %s,
                    'google_doc', 'google_docs', %s, 'proposal_draft_ready', 'contacted',
                    %s, 'partnership_outreach', 'proposal_draft_ready', %s,
                    NOW(), NOW()
                )
                """,
                (
                    lead_id,
                    lead_name,
                    spec["address"],
                    spec["city"],
                    spec["category"],
                    source_external_id,
                    dedupe_key,
                    BUSINESS_ID,
                    USER_ID,
                ),
            )
            cur.execute(
                """
                INSERT INTO lead_workstreams (
                    id, lead_id, workstream_type, client_business_id, status,
                    selected_channel, created_by, lifecycle_status, status_reason,
                    next_step, created_at, updated_at, state_changed_at
                ) VALUES (
                    %s, %s, 'client_partnership', %s, 'contacted',
                    'manual', %s, 'waiting_reply',
                    'Первое сообщение подтверждено пользователем и внесено из Google Docs',
                    'Ожидать ответ партнёра', NOW(), NOW(), NOW()
                )
                """,
                (workstream_id, lead_id, BUSINESS_ID, USER_ID),
            )
            created.append(lead_name)
        conn.commit()
        return created
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_missing_rooms(records: list[dict]) -> list[str]:
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        before = {}
        missing = []
        for record in records:
            title = str(record.get("title") or "").strip()
            lead_name = normalize_lead_name(title)
            row = load_scoped_row(cur, lead_name)
            if not row:
                raise RuntimeError(f"Scoped lead missing after ensure step: {lead_name}")
            if lead_name in TERMINAL_NAMES:
                before[lead_name] = row
            if not row.get("room_id"):
                missing.append((lead_name, row))
    finally:
        conn.close()

    created = []
    for lead_name, row in missing:
        result = _prepare_partnership_sales_room(
            lead_id=str(row.get("lead_id") or ""),
            business_id=BUSINESS_ID,
            user_id=USER_ID,
            data_mode="template",
            channel="manual",
            reuse_existing=False,
            workstream_id=str(row.get("workstream_id") or ""),
        )
        if not result.get("success"):
            raise RuntimeError(f"Room creation failed for {lead_name}: {result}")
        created.append(lead_name)

    if before:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            for lead_name, row in before.items():
                cur.execute(
                    """
                    UPDATE prospectingleads
                    SET status = %s,
                        pipeline_status = %s,
                        partnership_stage = %s,
                        disqualification_reason = %s,
                        disqualification_comment = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        row.get("lead_status"),
                        row.get("lead_pipeline_status"),
                        row.get("partnership_stage"),
                        row.get("disqualification_reason"),
                        row.get("disqualification_comment"),
                        row.get("lead_id"),
                    ),
                )
                cur.execute(
                    """
                    UPDATE lead_workstreams
                    SET status = %s,
                        lifecycle_status = %s,
                        status_reason = %s,
                        next_step = %s,
                        selected_channel = %s,
                        last_contact_at = %s,
                        last_contact_channel = %s,
                        last_contact_comment = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        row.get("workstream_status"),
                        row.get("lifecycle_status"),
                        row.get("status_reason"),
                        row.get("next_step"),
                        row.get("selected_channel"),
                        row.get("last_contact_at"),
                        row.get("last_contact_channel"),
                        row.get("last_contact_comment"),
                        row.get("workstream_id"),
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return created


def backfill_messages(records: list[dict], revision_id: str) -> dict:
    conn = get_db_connection()
    inserted = []
    skipped = []
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        for record in records:
            title = str(record.get("title") or "").strip()
            lead_name = normalize_lead_name(title)
            body_text = str(record.get("body_text") or "").strip()
            row = load_scoped_row(cur, lead_name)
            room_id = str(row.get("room_id") or "")
            if not room_id:
                raise RuntimeError(f"Room missing before message backfill: {lead_name}")
            cur.execute(
                """
                SELECT id
                FROM sales_room_messages
                WHERE room_id = %s
                  AND direction = 'outbound'
                  AND body_text = %s
                LIMIT 1
                """,
                (room_id, body_text),
            )
            if cur.fetchone():
                skipped.append(lead_name)
                continue
            message_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO sales_room_messages (
                    id, room_id, author_type, author_name, author_contact,
                    body_text, attachments_json, direction, source_channel,
                    provider_event_id, campaign_id, campaign_touch_id,
                    delivery_status, occurred_at, created_at
                ) VALUES (
                    %s, %s, 'owner', 'Александр Демьянов', '',
                    %s, %s, 'outbound', 'manual',
                    NULL, NULL, NULL, 'sent', NULL,
                    COALESCE(%s, NOW()) + INTERVAL '1 second'
                )
                """,
                (
                    message_id,
                    room_id,
                    body_text,
                    Json([]),
                    row.get("room_created_at"),
                ),
            )
            cur.execute(
                """
                INSERT INTO sales_room_events (
                    id, room_id, event_type, metadata_json, created_at
                ) VALUES (
                    %s, %s, 'outbound_message_backfilled', %s, NOW()
                )
                """,
                (
                    str(uuid.uuid4()),
                    room_id,
                    Json({
                        "message_id": message_id,
                        "source": "google_docs",
                        "source_document_id": DOCUMENT_ID,
                        "source_revision_id": revision_id,
                        "confirmed_sent_by_user": True,
                        "send_time_unknown": True,
                    }),
                ),
            )
            inserted.append(lead_name)
        conn.commit()
        return {"inserted": inserted, "skipped": skipped}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify(records: list[dict]) -> dict:
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        rows = []
        for record in records:
            title = str(record.get("title") or "").strip()
            lead_name = normalize_lead_name(title)
            row = load_scoped_row(cur, lead_name)
            cur.execute(
                """
                SELECT direction, source_channel, delivery_status, body_text
                FROM sales_room_messages
                WHERE room_id = %s
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (row.get("room_id"),),
            )
            first_message = cur.fetchone() or {}
            expected_body = str(record.get("body_text") or "").strip()
            rows.append({
                "title": title,
                "lead_name": lead_name,
                "room_id": row.get("room_id"),
                "slug": row.get("slug"),
                "room_status": row.get("room_status"),
                "visibility": row.get("visibility"),
                "outbound_count": int(row.get("outbound_count") or 0),
                "workstream_status": row.get("workstream_status"),
                "first_message_direction": first_message.get("direction"),
                "first_message_source_channel": first_message.get("source_channel"),
                "first_message_delivery_status": first_message.get("delivery_status"),
                "first_message_matches_source": first_message.get("body_text") == expected_body,
            })
        return {
            "count": len(rows),
            "with_room": sum(1 for row in rows if row.get("room_id")),
            "with_outbound": sum(1 for row in rows if row.get("outbound_count", 0) > 0),
            "shared": sum(1 for row in rows if row.get("visibility") == "shared"),
            "private": sum(1 for row in rows if row.get("visibility") == "private"),
            "first_message_matches_source": sum(
                1 for row in rows if row.get("first_message_matches_source")
            ),
            "first_message_is_outbound": sum(
                1 for row in rows if row.get("first_message_direction") == "outbound"
            ),
            "terminal_statuses": {
                row["lead_name"]: row.get("workstream_status")
                for row in rows
                if row["lead_name"] in TERMINAL_NAMES
            },
            "rows": rows,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    records, revision_id = load_records(Path(args.messages))
    if args.verify:
        print(json.dumps({"mode": "verify", "after": verify(records)}, ensure_ascii=False, default=str))
        return
    before = build_snapshot(records)
    if not args.apply:
        print(json.dumps({"mode": "dry-run", "before": before}, ensure_ascii=False, default=str))
        return
    created_leads = ensure_missing_leads()
    created_rooms = create_missing_rooms(records)
    message_result = backfill_messages(records, revision_id)
    after = verify(records)
    print(json.dumps({
        "mode": "apply",
        "created_leads": created_leads,
        "created_rooms": created_rooms,
        "messages": message_result,
        "after": after,
    }, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
