#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from database_manager import DatabaseManager
from services.creator_promotion_service import (
    approve_campaign_terms,
    confirm_candidate_contact,
    prepare_candidate_outreach,
    update_campaign_terms,
)


CAMPAIGNS = [
    {
        "business_id": "edbd961a-273f-4f15-836e-33aacc0aa0e3",
        "campaign_id": "c35cd3ed-8a57-4ab4-8d58-bb0f65c19d9f",
        "client": "Riderra",
        "creators": [
            {
                "url": "https://www.instagram.com/mallukaz",
                "contact": "marianntreimann@gmail.com",
                "source_url": "https://www.modash.io/find-influencers/estonia/tallinn",
                "confirmed": False,
            },
            {
                "url": "https://www.instagram.com/helgekalde",
                "contact": "helge.kalde1@gmail.com",
                "source_url": "https://collabstr.com/helgekalde",
                "confirmed": False,
            },
            {
                "url": "https://t.me/janakristinaestonia",
                "contact": "yanaiter58@gmail.com",
                "source_url": "https://t.me/janakristinaestonia",
                "confirmed": False,
            },
        ],
    },
    {
        "business_id": "ab26362f-9d63-4025-b721-9a8cb29015ef",
        "campaign_id": "cc8a4f5d-814f-468a-858f-d5885e279bf0",
        "client": "Весёлая расчёска",
        "creators": [
            {
                "url": "https://t.me/mamy_piter",
                "contact": "https://t.me/mama_city_admin",
                "source_url": "https://t.me/mamy_piter",
                "confirmed": True,
            },
            {
                "url": "https://t.me/gokidspeterburg",
                "contact": "https://t.me/alex_admin_tg",
                "source_url": "https://t.me/gokidspeterburg",
                "confirmed": True,
            },
            {
                "url": "https://t.me/afishaspbmami",
                "contact": "https://t.me/afishaspbmamibot",
                "source_url": "https://t.me/afishaspbmami",
                "confirmed": True,
            },
        ],
    },
    {
        "business_id": "360b90ef-cf2b-4eb4-acd4-a8524e4600ae",
        "campaign_id": "5902e750-d1c5-41cc-b3ff-189283d17951",
        "client": "Органика",
        "creators": [
            {
                "url": "https://t.me/your_skin_care",
                "contact": "https://t.me/vareshka_84",
                "source_url": "https://t.me/your_skin_care",
                "confirmed": True,
            },
            {
                "url": "https://t.me/kdvmua",
                "contact": "kdvmua@gmail.com",
                "source_url": "https://t.me/kdvmua",
                "confirmed": True,
            },
            {
                "url": "https://t.me/kremom_po_litsu",
                "contact": "https://t.me/Eklllerchik",
                "source_url": "https://t.me/kremom_po_litsu",
                "confirmed": True,
            },
        ],
    },
]

STALE_URL = "https://t.me/semejnyjspb"


def _row(cursor: Any, campaign: dict[str, Any], creator: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT candidate.id AS candidate_id, candidate.creator_profile_id,
               profile.display_name, campaign.created_by
        FROM creator_campaign_candidates candidate
        JOIN creator_campaigns campaign ON campaign.id = candidate.campaign_id
        JOIN creator_profiles profile ON profile.id = candidate.creator_profile_id
        JOIN creator_channels channel ON channel.creator_profile_id = profile.id
        WHERE candidate.campaign_id = %s AND campaign.business_id = %s
          AND LOWER(RTRIM(channel.canonical_url, '/')) = LOWER(RTRIM(%s, '/'))
        LIMIT 1
        """,
        (campaign["campaign_id"], campaign["business_id"], creator["url"]),
    )
    result = cursor.fetchone()
    if not result:
        raise LookupError(f"В кампании {campaign['client']} не найден {creator['url']}")
    return dict(result)


def _actor(cursor: Any, campaign: dict[str, Any], selected: list[dict[str, Any]]) -> str:
    value = str(selected[0].get("created_by") or "").strip()
    if value:
        return value
    cursor.execute(
        """
        SELECT user_id FROM userbusinesses
        WHERE business_id = %s ORDER BY created_at LIMIT 1
        """,
        (campaign["business_id"],),
    )
    row = cursor.fetchone()
    if row and str(row.get("user_id") or "").strip():
        return str(row["user_id"])
    raise LookupError(f"Не найден владелец кампании {campaign['client']}")


def _upsert_contact(cursor: Any, creator: dict[str, Any], selected: dict[str, Any]) -> None:
    metadata = {
        "public_contacts": [{
            "type": "email" if "@" in creator["contact"] and not creator["contact"].startswith("http") else "telegram",
            "value": creator["contact"],
            "status": "public_profile_contact" if creator["confirmed"] else "cross_source_needs_confirmation",
            "source_url": creator["source_url"],
            "checked_at": "2026-08-24",
        }],
        "contact_source_url": creator["source_url"],
        "contact_status": "public_verified" if creator["confirmed"] else "public_unverified",
        "first_wave": True,
        "sender": "LocalOS",
    }
    cursor.execute(
        """
        INSERT INTO creator_commercial_profiles (
            id, creator_profile_id, preferred_contact, confirmation_status, metadata_json
        ) VALUES (%s, %s, %s, 'observed', %s)
        ON CONFLICT (creator_profile_id) DO UPDATE SET
            preferred_contact = EXCLUDED.preferred_contact,
            metadata_json = creator_commercial_profiles.metadata_json || EXCLUDED.metadata_json,
            updated_at = NOW()
        """,
        (str(uuid.uuid4()), selected["creator_profile_id"], creator["contact"], Json(metadata)),
    )


def _campaign_terms(campaign: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"Сбор условий авторов — {campaign['client']}",
        "goal": "Узнать актуальные условия автора и вернуться с конкретным брифом после сопоставления",
        "sender_mode": "localos_for_partner",
        "formats": ["нативная интеграция", "обзор", "UGC"],
        "offer": {
            "mode": "creator_terms_intake",
            "details": "LocalOS собирает форматы, цены, географию аудитории и свежие охваты; конкретный бизнес предлагается позже",
        },
        "budget": {"mode": "requires_creator_quote"},
        "period": {"mode": "after_creator_and_business_match"},
        "constraints": {
            "usage_rights": {"mode": "separate_manual_approval"},
            "disclosure": "Маркировка и юридические условия согласуются до публикации",
            "external_send_requires_manual_approval": True,
        },
    }


def run(*, apply: bool, prepare_ready: bool) -> dict[str, Any]:
    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    summary: dict[str, Any] = {"campaigns": [], "stale_removed": 0, "applied": apply, "external_messages_sent": 0}
    try:
        cursor.execute(
            """
            UPDATE creator_channels SET verification_status = 'mismatch',
                verification_note = 'Публичный профиль сменил название и тематику; исключён 2026-08-24',
                next_check_at = NOW() + INTERVAL '30 days', updated_at = NOW()
            WHERE LOWER(RTRIM(canonical_url, '/')) = LOWER(RTRIM(%s, '/'))
            RETURNING creator_profile_id
            """,
            (STALE_URL,),
        )
        stale_profiles = [str(row["creator_profile_id"]) for row in cursor.fetchall()]
        for stale_profile_id in stale_profiles:
            cursor.execute(
                """
                UPDATE creator_campaign_candidates SET status = 'removed', updated_at = NOW()
                WHERE creator_profile_id = %s AND status IN ('shortlisted', 'invitation_ready')
                """,
                (stale_profile_id,),
            )
            summary["stale_removed"] += cursor.rowcount

        for campaign in CAMPAIGNS:
            selected = [_row(cursor, campaign, creator) for creator in campaign["creators"]]
            actor_id = _actor(cursor, campaign, selected)
            candidate_ids = [str(item["candidate_id"]) for item in selected]
            cursor.execute(
                """
                UPDATE creator_campaign_candidates SET status = 'removed', updated_at = NOW()
                WHERE campaign_id = %s AND id NOT IN (%s, %s, %s)
                  AND status IN ('shortlisted', 'invitation_ready')
                """,
                (campaign["campaign_id"], *candidate_ids),
            )
            reserve_removed = cursor.rowcount
            cursor.execute(
                """
                UPDATE creator_campaign_candidates SET status = 'shortlisted', updated_at = NOW()
                WHERE campaign_id = %s AND id IN (%s, %s, %s) AND status = 'removed'
                """,
                (campaign["campaign_id"], *candidate_ids),
            )
            update_campaign_terms(
                cursor,
                business_id=campaign["business_id"],
                campaign_id=campaign["campaign_id"],
                payload=_campaign_terms(campaign),
            )
            approve_campaign_terms(
                cursor,
                business_id=campaign["business_id"],
                campaign_id=campaign["campaign_id"],
            )
            ready = 0
            review = 0
            contacts: list[dict[str, Any]] = []
            for creator, item in zip(campaign["creators"], selected):
                _upsert_contact(cursor, creator, item)
                if creator["confirmed"]:
                    confirm_candidate_contact(
                        cursor,
                        business_id=campaign["business_id"],
                        campaign_id=campaign["campaign_id"],
                        candidate_id=str(item["candidate_id"]),
                        user_id=actor_id,
                        payload={
                            "confirmed": True,
                            "confirmation_note": "Контакт указан в актуальном публичном профиле автора или площадки",
                            "confirmation_source_url": creator["source_url"],
                        },
                    )
                    if prepare_ready:
                        prepare_candidate_outreach(
                            cursor,
                            database.conn,
                            business_id=campaign["business_id"],
                            campaign_id=campaign["campaign_id"],
                            candidate_id=str(item["candidate_id"]),
                            user_id=actor_id,
                        )
                    ready += 1
                    state = "invitation_ready" if prepare_ready else "contact_confirmed"
                else:
                    review += 1
                    state = "contact_needs_confirmation"
                contacts.append({
                    "candidate_id": str(item["candidate_id"]),
                    "name": item["display_name"],
                    "contact": creator["contact"],
                    "state": state,
                })
            summary["campaigns"].append({
                "client": campaign["client"],
                "campaign_id": campaign["campaign_id"],
                "selected": len(selected),
                "ready": ready,
                "needs_contact_confirmation": review,
                "reserve_removed": reserve_removed,
                "contacts": contacts,
            })
        if apply:
            database.conn.commit()
        else:
            database.conn.rollback()
        return summary
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the approved LocalOS creator-intake first wave without sending messages")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--prepare-ready", action="store_true", help="Create internal leads/workstreams for confirmed contacts")
    arguments = parser.parse_args()
    result = run(apply=arguments.apply, prepare_ready=arguments.prepare_ready)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
