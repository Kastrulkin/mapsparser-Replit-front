#!/usr/bin/env python3
"""Create deterministic, synthetic fixtures for LocalOS journey staging."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from psycopg2.extras import Json

from auth_system import create_user
from database_manager import DatabaseManager, get_db_connection


FIXTURE_NAMESPACE = uuid.UUID("e48b07f6-e923-4d6d-9a70-b1de982d2f11")
OWNER_EMAIL = "owner@localos-e2e.invalid"
ADMIN_EMAIL = "admin@localos-e2e.invalid"
FIXTURE_PASSWORD = "LocalOS-E2E-2026!"
FLOWS = ("maps", "influencer", "partnership", "content", "automation")
OWNER_BUSINESS_NAME = "[E2E] Салон Север"


def fixture_id(label: str) -> str:
    return str(uuid.uuid5(FIXTURE_NAMESPACE, label))


def ensure_user(email: str, name: str, *, superadmin: bool = False) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE lower(email) = lower(%s)", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user_id = str(row[0])
    else:
        created = create_user(
            email=email,
            password=FIXTURE_PASSWORD,
            name=name,
            personal_data_consent=True,
            is_verified=True,
        )
        if created.get("error"):
            raise RuntimeError(f"Could not create synthetic user: {created['error']}")
        user_id = str(created["id"])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET is_verified = TRUE, is_active = TRUE, is_superadmin = %s WHERE id = %s",
        (superadmin, user_id),
    )
    conn.commit()
    conn.close()
    return user_id


def ensure_business(owner_id: str, name: str, city: str) -> str:
    manager = DatabaseManager()
    cursor = manager.conn.cursor()
    cursor.execute(
        "SELECT id FROM businesses WHERE owner_id = %s AND name = %s LIMIT 1",
        (owner_id, name),
    )
    row = cursor.fetchone()
    if row:
        business_id = str(row[0])
    else:
        business_id = manager.create_business(
            name=name,
            description="Синтетический бизнес для изолированных E2E-тестов LocalOS.",
            industry="beauty",
            owner_id=owner_id,
            address=f"Тестовая улица, 1, {city}",
            city=city,
            country="RU",
            moderation_status="approved",
            entity_group="demo",
        )
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND lower(table_name) = 'businesses'
        """
    )
    available_columns = {column[0] for column in cursor.fetchall()}
    updates = []
    values = []
    for column, value in (
        ("subscription_tier", "starter"),
        ("subscription_status", "active"),
        ("moderation_status", "approved"),
        ("entity_group", "demo"),
    ):
        if column in available_columns:
            updates.append(f"{column} = %s")
            values.append(value)
    if updates:
        values.append(business_id)
        cursor.execute(
            f"UPDATE businesses SET {', '.join(updates)} WHERE id = %s",
            tuple(values),
        )
    manager.conn.commit()
    manager.close()
    return business_id


def opportunity(flow: str) -> dict[str, object]:
    content = {
        "maps": ("Исправить часы работы", "Карточка теряет клиентов из-за устаревшего расписания."),
        "influencer": ("Анна про район", "Локальный автор о местах и услугах рядом."),
        "partnership": ("Студия йоги рядом", "У бизнеса пересекается локальная аудитория."),
        "content": ("Как выбрать услугу впервые", "Тема основана на частом вопросе клиентов."),
        "automation": ("Разобрать новые отзывы", "LocalOS подготовит черновики, публикация останется ручной."),
    }
    title, summary = content[flow]
    return {
        "flow_type": flow,
        "entity_type": f"e2e_{flow}",
        "entity_id": fixture_id(f"entity:{flow}"),
        "title": title,
        "summary": summary,
        "reason": "Синтетический пример для проверки пользовательского пути.",
        "public_url": "",
        "message_excerpt": "",
        "metrics": {},
    }


def seed_owner_review(owner_id: str, business_id: str) -> None:
    review_id = fixture_id("owner-review:unanswered")
    draft_id = fixture_id("owner-review-draft:unanswered")
    review_text = "Спасибо мастеру за аккуратную работу. Подскажите, как записаться повторно?"
    draft_text = "Мария, спасибо за отзыв! Напишите нам в удобном канале, и мы подберём время для повторной записи."
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO externalbusinessreviews (
            id, business_id, source, external_review_id, rating, author_name, text,
            response_text, published_at, lang, raw_payload, is_current, last_seen_at
        ) VALUES (%s, %s, 'yandex', 'localos-e2e-review-1', 5, 'Мария Тестова', %s,
                  NULL, NOW() - INTERVAL '2 hours', 'ru', '{}', TRUE, NOW())
        ON CONFLICT (id) DO UPDATE SET
            business_id = EXCLUDED.business_id,
            response_text = NULL,
            is_current = TRUE,
            last_seen_at = NOW(),
            updated_at = NOW()
        """,
        (review_id, business_id, review_text),
    )
    cursor.execute(
        """
        INSERT INTO reviewreplydrafts (
            id, business_id, review_id, user_id, source, rating, author_name,
            review_text, generated_text, status, tone, prompt_key, prompt_version
        ) VALUES (%s, %s, %s, %s, 'yandex', 5, 'Мария Тестова', %s, %s,
                  'draft', 'professional', 'e2e_fixture', '1')
        ON CONFLICT (review_id) DO UPDATE SET
            business_id = EXCLUDED.business_id,
            user_id = EXCLUDED.user_id,
            review_text = EXCLUDED.review_text,
            generated_text = EXCLUDED.generated_text,
            status = 'draft',
            updated_at = NOW()
        """,
        (draft_id, business_id, review_id, owner_id, review_text, draft_text),
    )
    conn.commit()
    conn.close()


def seed_journeys() -> dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    tokens = {}
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    for flow in FLOWS:
        lead_id = fixture_id(f"lead:{flow}")
        journey_id = fixture_id(f"journey:{flow}")
        raw_token = f"localos-e2e-{flow}-{fixture_id(f'token:{flow}').replace('-', '')}"
        tokens[flow] = raw_token
        selected = opportunity(flow)
        preview = {
            "lead_name": f"[E2E] {flow.title()} Journey",
            "city": "Санкт-Петербург",
            "opportunities": [selected],
        }
        cursor.execute(
            """
            INSERT INTO prospectingleads (id, name, city, source, source_external_id, status, category)
            VALUES (%s, %s, %s, 'e2e_fixture', %s, 'new', 'synthetic')
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW()
            """,
            (lead_id, preview["lead_name"], preview["city"], f"e2e-{flow}"),
        )
        cursor.execute(
            """
            INSERT INTO lead_journeys (
                id, prospect_lead_id, source_offer_type, public_token_hash, source,
                preview_json, selected_flow, selected_entity_type, selected_entity_id,
                status, expires_at
            ) VALUES (%s, %s, 'lead_offer', %s, 'e2e_fixture', %s, %s, %s, %s, 'preview', %s)
            ON CONFLICT (id) DO UPDATE SET
                public_token_hash = EXCLUDED.public_token_hash,
                preview_json = EXCLUDED.preview_json,
                selected_flow = EXCLUDED.selected_flow,
                selected_entity_type = EXCLUDED.selected_entity_type,
                selected_entity_id = EXCLUDED.selected_entity_id,
                expires_at = EXCLUDED.expires_at,
                revoked_at = NULL
            """,
            (
                journey_id,
                lead_id,
                hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                Json(preview),
                flow,
                selected["entity_type"],
                selected["entity_id"],
                expires_at,
            ),
        )
    conn.commit()
    conn.close()
    return tokens


def main() -> None:
    owner_id = ensure_user(OWNER_EMAIL, "E2E Владелец")
    admin_id = ensure_user(ADMIN_EMAIL, "E2E Администратор", superadmin=True)
    business_id = ensure_business(owner_id, OWNER_BUSINESS_NAME, "Санкт-Петербург")
    second_business_id = ensure_business(owner_id, "[E2E] Салон Центр", "Санкт-Петербург")
    seed_owner_review(owner_id, business_id)
    tokens = seed_journeys()
    print(json.dumps({
        "synthetic_only": True,
        "owner_email": OWNER_EMAIL,
        "admin_email": ADMIN_EMAIL,
        "password": FIXTURE_PASSWORD,
        "owner_id": owner_id,
        "admin_id": admin_id,
        "business_id": business_id,
        "second_business_id": second_business_id,
        "journey_tokens": tokens,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
