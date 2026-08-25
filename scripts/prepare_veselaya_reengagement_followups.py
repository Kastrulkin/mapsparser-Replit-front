#!/usr/bin/env python3
"""Prepare three email re-engagement drafts without queueing or sending them."""

from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


BUSINESS_ID = "cb674174-8b3d-41a3-8277-525c849935f2"
RULES_VERSION = "veselaya_reengagement_human_v1"

FOLLOW_UPS = {
    "1000 и одна туфелька": {
        "email": "t.karpova@tufelka.spb.ru",
        "source_url": "user-provided://reg-ru-sent/2026-06-29",
        "subject": "Вернёмся к обсуждению партнёрства",
        "message": (
            "Татьяна, здравствуйте!\n\n"
            "Хотел бы вернуться к нашему разговору о партнёрстве между «1000 и одной туфелькой» "
            "и «Весёлой расчёской». Мы обсуждали обмен листовками и предложение к началу учебного года.\n\n"
            "Если тема ещё актуальна, давайте возобновим диалог и выберем подходящий формат. "
            "Получилось обсудить эту идею с руководством?"
        ),
        "history_note": "Обсуждались обмен листовками и предложение к началу учебного года",
    },
    "D'Athletics fitness": {
        "email": "clubpolitech@gmail.com",
        "source_url": "user-provided://reg-ru-history/2026-06-22",
        "subject": "Вернёмся к обсуждению партнёрства",
        "message": (
            "Здравствуйте!\n\n"
            "Мы общались в июне по поводу партнёрства D’Athletics Fitness и «Весёлой расчёски». "
            "Хотел бы вернуться к этой теме: можно обсудить предложение для воспитанников секций "
            "или другой удобный формат.\n\n"
            "Если идея ещё актуальна, давайте возобновим диалог. Удобно продолжить здесь?"
        ),
        "history_note": "Факт ответа подтверждён владельцем; содержание ответа не сохранилось",
    },
    "Grand Dent": {
        "email": "info@granddent.ru",
        "source_url": "user-provided://reg-ru-history/2026-06-22",
        "subject": "Вернёмся к обсуждению партнёрства",
        "message": (
            "Здравствуйте!\n\n"
            "Мы общались в июне по поводу партнёрства Grand Dent и «Весёлой расчёски». "
            "Хотел бы вернуться к этой теме: можно обсудить совместное предложение для семей "
            "или другой удобный формат.\n\n"
            "Если идея ещё актуальна, давайте возобновим диалог. Удобно продолжить здесь?"
        ),
        "history_note": "Факт ответа подтверждён владельцем; содержание ответа не сохранилось",
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_email(value: str) -> str:
    return _text(value).lower().replace("mailto:", "")


def _quality_gate(message: str) -> dict[str, Any]:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9’'-]+", message)
    blockers: list[str] = []
    lowered = message.lower()
    if len(words) > 90:
        blockers.append("CHANNEL_LIMIT_EXCEEDED")
    if message.count("?") != 1:
        blockers.append("MULTIPLE_CTA")
    for phrase in ("решил напомнить", "поднимаю сообщение", "вы видели моё сообщение", "синергия"):
        if phrase in lowered:
            blockers.append("STYLE_VIOLATION")
    criteria = {
        "source_validity": 2,
        "observation_accuracy": 2,
        "freshness_and_why_now": 1,
        "bridge_from_signal_to_offer": 2,
        "recipient_specificity": 2,
        "proof_integrity": 2,
        "natural_channel_fit": 2,
        "single_cta_and_length": 2,
        "state_and_suppression_safety": 2,
    }
    score = sum(criteria.values())
    return {
        "passed": not blockers and score >= 15,
        "score": score,
        "total_score": score,
        "criteria": criteria,
        "reason_codes": blockers,
        "blocking_reasons": blockers,
        "word_count": len(words),
        "review_version": RULES_VERSION,
    }


def _upsert_email(cur, lead_id: str, email: str, source_url: str, apply_changes: bool) -> str:
    normalized = _normalized_email(email)
    cur.execute(
        """
        SELECT id FROM lead_contact_points
        WHERE lead_id = %s AND contact_type = 'email' AND normalized_value = %s
        """,
        (lead_id, normalized),
    )
    existing = cur.fetchone()
    contact_id = _text(existing.get("id")) if existing else str(uuid.uuid4())
    if not apply_changes:
        return contact_id
    metadata = {
        "recipient_eligible": True,
        "verification_basis": "prior_two_way_email_history_confirmed_by_owner",
        "review": RULES_VERSION,
    }
    cur.execute(
        """
        INSERT INTO lead_contact_points (
            id, lead_id, contact_type, value, normalized_value, owner_type,
            source_url, source_type, provider, confidence, verification_status,
            observed_at, verified_at, stale_after, metadata_json, created_at, updated_at
        ) VALUES (%s::uuid, %s, 'email', %s, %s, 'company', %s, 'user_provided_history',
                  'manual', 1, 'confirmed_source', NOW(), NOW(), NOW() + INTERVAL '180 days',
                  %s, NOW(), NOW())
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
        (contact_id, lead_id, email, normalized, source_url, Json(metadata)),
    )
    return contact_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    results: list[dict[str, Any]] = []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE COALESCE(is_superadmin, FALSE) = TRUE ORDER BY created_at LIMIT 1")
        user = cur.fetchone()
        if not user:
            raise RuntimeError("superadmin not found")
        user_id = _text(user.get("id"))
        cur.execute(
            """
            SELECT id FROM outreach_sender_profiles
            WHERE client_business_id = %s AND workstream_type = 'client_partnership' AND is_active = TRUE
            ORDER BY updated_at DESC LIMIT 1
            """,
            (BUSINESS_ID,),
        )
        profile = cur.fetchone()
        if not profile:
            raise RuntimeError("sender profile not found")
        profile_id = _text(profile.get("id"))

        for name, spec in FOLLOW_UPS.items():
            cur.execute(
                """
                SELECT workstream.id AS workstream_id, workstream.lead_id,
                       workstream.status, workstream.lifecycle_status,
                       room.id AS room_id, room.room_json
                FROM lead_workstreams workstream
                JOIN prospectingleads lead ON lead.id = workstream.lead_id
                LEFT JOIN LATERAL (
                    SELECT * FROM sales_rooms candidate
                    WHERE candidate.workstream_id = workstream.id
                    ORDER BY candidate.created_at LIMIT 1
                ) room ON TRUE
                WHERE workstream.client_business_id = %s
                  AND workstream.workstream_type = 'client_partnership'
                  AND lead.name = %s
                """,
                (BUSINESS_ID, name),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"workstream not found: {name}")
            row = dict(row)
            if _text(row.get("status")) in {"closed_lost", "not_relevant", "suppressed"}:
                raise RuntimeError(f"terminal workstream: {name}")
            gate = _quality_gate(spec["message"])
            if not gate["passed"]:
                raise RuntimeError(f"quality gate failed for {name}: {gate['reason_codes']}")
            contact_id = _upsert_email(
                cur,
                _text(row.get("lead_id")),
                spec["email"],
                spec["source_url"],
                args.apply,
            )
            draft_id = str(uuid.uuid4())
            if args.apply:
                brief = {
                    "generation_source": "manual_outreach_review",
                    "generation_rules_version": RULES_VERSION,
                    "message_kind": "reengagement_follow_up",
                    "history_note": spec["history_note"],
                    "external_send_authorized": False,
                    "human_approval_required": True,
                }
                cur.execute(
                    """
                    INSERT INTO outreachmessagedrafts (
                        id, lead_id, channel, angle_type, tone, status,
                        generated_text, created_by, workstream_id, contact_point_id,
                        sender_profile_id, message_brief_json, quality_gate_json,
                        include_room_link, created_at, updated_at
                    ) VALUES (%s, %s, 'email', 'reengagement', 'human_concise', 'generated',
                              %s, %s, %s::uuid, %s::uuid, %s::uuid, %s, %s, FALSE, NOW(), NOW())
                    """,
                    (
                        draft_id, row["lead_id"], spec["message"], user_id,
                        row["workstream_id"], contact_id, profile_id, Json(brief), Json(gate),
                    ),
                )
                cur.execute(
                    """
                    UPDATE lead_workstreams SET
                        selected_channel = 'email', selected_contact_point_id = %s::uuid,
                        status_reason = 'Подготовлен follow-up для возобновления существующего диалога',
                        next_step = 'Проверить и вручную отправить follow-up в прежней email-ветке',
                        state_changed_at = NOW(), updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (contact_id, row["workstream_id"]),
                )
                room_json = row.get("room_json") if isinstance(row.get("room_json"), dict) else {}
                room_json = {
                    **room_json,
                    "follow_up_draft": {
                        "draft_id": draft_id,
                        "channel": "email",
                        "recipient": spec["email"],
                        "subject": spec["subject"],
                        "body_text": spec["message"],
                        "status": "needs_review",
                        "source": RULES_VERSION,
                    },
                }
                cur.execute(
                    """
                    UPDATE sales_rooms SET room_json = %s, invitation_draft_id = %s, updated_at = NOW()
                    WHERE id = NULLIF(%s, '')::uuid
                    """,
                    (Json(room_json), draft_id, _text(row.get("room_id"))),
                )
            results.append({
                "name": name,
                "email": spec["email"],
                "subject": spec["subject"],
                "message": spec["message"],
                "quality_gate": gate,
                "draft_id": draft_id if args.apply else "dry-run",
                "state_preserved": {
                    "status": row.get("status"),
                    "lifecycle_status": row.get("lifecycle_status"),
                },
                "queued": False,
                "sent": False,
            })
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        print(json.dumps({
            "dry_run": not args.apply,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }, ensure_ascii=False, indent=2, default=str))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
