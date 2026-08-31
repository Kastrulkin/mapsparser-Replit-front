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
OWNER_TELEGRAM_ID = "900000001"
ADMIN_EMAIL = "admin@localos-e2e.invalid"
FIXTURE_PASSWORD = "LocalOS-E2E-2026!"
FLOWS = ("maps", "influencer", "partnership", "content", "automation")
OWNER_BUSINESS_NAME = "[E2E] Салон Север"
OWNER_SECOND_BUSINESS_NAME = "[E2E] Салон Центр"
OWNER_NETWORK_NAME = "[E2E] Сеть салонов"
FOREIGN_EMAIL = "foreign@localos-e2e.invalid"
FOREIGN_BUSINESS_NAME = "[E2E] Чужая точка"
FOREIGN_NETWORK_NAME = "[E2E] Чужая сеть"


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


def ensure_network(owner_id: str, name: str, business_ids: tuple[str, ...]) -> str:
    network_id = fixture_id(f"network:{name}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO networks (id, owner_id, name, description, entity_group)
        VALUES (%s, %s, %s, 'Синтетическая сеть для изолированных E2E-тестов LocalOS.', 'demo')
        ON CONFLICT (id) DO UPDATE SET
            owner_id = EXCLUDED.owner_id,
            name = EXCLUDED.name,
            entity_group = 'demo',
            updated_at = NOW()
        """,
        (network_id, owner_id, name),
    )
    cursor.execute(
        "UPDATE businesses SET network_id = %s WHERE id = ANY(%s)",
        (network_id, list(business_ids)),
    )
    conn.commit()
    conn.close()
    return network_id


def opportunity(flow: str) -> dict[str, object]:
    content = {
        "maps": ("Исправить часы работы", "Карточка теряет клиентов из-за устаревшего расписания."),
        "influencer": ("Анна про район", "Локальный автор о местах и услугах рядом."),
        "partnership": ("Студия йоги рядом", "У бизнеса пересекается локальная аудитория."),
        "content": ("Как выбрать услугу впервые", "Тема основана на частом вопросе клиентов."),
        "automation": ("Разобрать новые отзывы", "LocalOS подготовит черновики, публикация останется ручной."),
    }
    title, summary = content[flow]
    entity_types = {
        "maps": "businessmaplink",
        "influencer": "creator_search",
        "partnership": "lead_workstream",
        "content": "contentplanitem",
        "automation": "automation_use_case",
    }
    entity_labels = {
        "maps": "map-link:owner",
        "influencer": "creator-search:owner",
        "partnership": "workstream:partnership",
        "content": "content-item:owner",
        "automation": "routine_control",
    }
    entity_id = entity_labels[flow] if flow == "automation" else fixture_id(entity_labels[flow])
    return {
        "flow_type": flow,
        "entity_type": entity_types[flow],
        "entity_id": entity_id,
        "title": title,
        "summary": summary,
        "reason": "Синтетический пример для проверки пользовательского пути.",
        "public_url": "",
        "message_excerpt": "",
        "metrics": {},
    }


def seed_domain_fixtures(owner_id: str, business_id: str) -> None:
    """Seed only synthetic records needed to prove each journey domain projection."""
    map_link_id = fixture_id("map-link:owner")
    search_id = fixture_id("creator-search:owner")
    creator_id = fixture_id("creator-profile:anna")
    channel_id = fixture_id("creator-channel:anna")
    result_id = fixture_id("creator-result:anna")
    content_plan_id = fixture_id("content-plan:owner")
    content_item_id = fixture_id("content-item:owner")
    blueprint_id = fixture_id("automation-blueprint:owner")
    blueprint_version_id = fixture_id("automation-blueprint-version:owner")
    today = datetime.now(timezone.utc).date()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businessmaplinks (id, user_id, business_id, url, map_type)
        VALUES (%s, %s, %s, 'https://yandex.ru/maps/org/localos_e2e_salon/100000001', 'yandex_maps')
        ON CONFLICT (id) DO UPDATE SET user_id = EXCLUDED.user_id,
            business_id = EXCLUDED.business_id, url = EXCLUDED.url, map_type = EXCLUDED.map_type
        """,
        (map_link_id, owner_id, business_id),
    )
    cursor.execute(
        """
        INSERT INTO creator_profiles (
            id, display_name, description, primary_city, primary_area,
            topics_json, verification_status, brand_safety_status, metadata_json
        ) VALUES (%s, 'Анна про район', 'Пишет о местах, сервисах и жизни района.',
                  'Санкт-Петербург', 'Петроградский', %s, 'verified', 'clear', %s)
        ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name,
            description = EXCLUDED.description, primary_city = EXCLUDED.primary_city,
            topics_json = EXCLUDED.topics_json, verification_status = 'verified', updated_at = NOW()
        """,
        (creator_id, Json(["красота", "места рядом"]), Json({"fixture": True})),
    )
    cursor.execute(
        """
        INSERT INTO creator_channels (
            id, creator_profile_id, platform, canonical_url, username, contactability,
            public_metrics_json, metadata_json, last_observed_at, verification_status, verified_at
        ) VALUES (%s, %s, 'telegram', 'https://t.me/localos_e2e_anna', 'localos_e2e_anna',
                  'public_contact', %s, %s, NOW(), 'verified', NOW())
        ON CONFLICT (id) DO UPDATE SET creator_profile_id = EXCLUDED.creator_profile_id,
            canonical_url = EXCLUDED.canonical_url, public_metrics_json = EXCLUDED.public_metrics_json,
            verification_status = 'verified', last_observed_at = NOW(), updated_at = NOW()
        """,
        (channel_id, creator_id, Json({"followers": 4200, "average_views": 1600}), Json({"fixture": True})),
    )
    cursor.execute(
        """
        INSERT INTO creator_search_jobs (
            id, business_id, created_by, status, phase, brief_json, progress_json, completed_at
        ) VALUES (%s, %s, %s, 'ready', 'ready', %s, %s, NOW())
        ON CONFLICT (id) DO UPDATE SET business_id = EXCLUDED.business_id,
            status = 'ready', phase = 'ready', brief_json = EXCLUDED.brief_json,
            progress_json = EXCLUDED.progress_json, completed_at = NOW(), updated_at = NOW()
        """,
        (search_id, business_id, owner_id, Json({"city": "Санкт-Петербург", "platforms": ["telegram"]}), Json({"found": 1})),
    )
    cursor.execute(
        """
        INSERT INTO creator_search_results (
            id, search_job_id, creator_profile_id, score, score_json, reasons_json,
            gates_json, result_group, shortlist_status
        ) VALUES (%s, %s, %s, 92, %s, %s, %s, 'best_fit', 'shortlisted')
        ON CONFLICT (id) DO UPDATE SET search_job_id = EXCLUDED.search_job_id,
            creator_profile_id = EXCLUDED.creator_profile_id, score = 92,
            shortlist_status = 'shortlisted', updated_at = NOW()
        """,
        (result_id, search_id, creator_id, Json({"local_fit": 96}), Json(["Рядом с бизнесом"]), Json({"public_data": True})),
    )
    cursor.execute(
        """
        INSERT INTO contentplans (
            id, business_id, scope_type, title, period_days, period_start, period_end,
            plan_status, generation_mode, input_snapshot_json, created_by
        ) VALUES (%s, %s, 'single_business', 'Первая публикация E2E', 30, %s, %s,
                  'draft', 'journey', %s, %s)
        ON CONFLICT (id) DO UPDATE SET business_id = EXCLUDED.business_id,
            period_start = EXCLUDED.period_start, period_end = EXCLUDED.period_end,
            plan_status = 'draft', updated_at = NOW()
        """,
        (content_plan_id, business_id, today, today + timedelta(days=29), Json({"fixture": True}), owner_id),
    )
    cursor.execute(
        """
        INSERT INTO contentplanitems (
            id, plan_id, business_id, scheduled_for, content_type, theme, goal,
            source_kind, source_ref, draft_text, status, metadata_json
        ) VALUES (%s, %s, %s, %s, 'news', 'Как выбрать услугу впервые',
                  'Помочь клиенту сделать выбор', 'e2e_fixture', 'journey:content', NULL, 'planned', %s)
        ON CONFLICT (id) DO UPDATE SET plan_id = EXCLUDED.plan_id,
            business_id = EXCLUDED.business_id, scheduled_for = EXCLUDED.scheduled_for,
            draft_text = NULL, status = 'planned', metadata_json = EXCLUDED.metadata_json,
            updated_at = NOW()
        """,
        (content_item_id, content_plan_id, business_id, today + timedelta(days=7), Json({"fixture": True})),
    )
    cursor.execute(
        """
        INSERT INTO agent_blueprints (
            id, business_id, name, category, description, status, created_by_user_id, metadata_json
        ) VALUES (%s, %s, 'Разобрать новые отзывы', 'reviews',
                  'Подготовить черновики без автопубликации.', 'draft', %s, %s)
        ON CONFLICT (id) DO UPDATE SET business_id = EXCLUDED.business_id,
            name = EXCLUDED.name, status = 'draft', metadata_json = EXCLUDED.metadata_json,
            updated_at = NOW()
        """,
        (blueprint_id, business_id, owner_id, Json({"fixture": True, "active_version_id": blueprint_version_id})),
    )
    cursor.execute(
        """
        INSERT INTO agent_blueprint_versions (
            id, blueprint_id, version_number, goal, inputs_schema_json, steps_json,
            capability_allowlist_json, approval_policy_json, output_schema_json,
            created_by_user_id, execution_mode, trigger
        ) VALUES (%s, %s, 1, 'Подготовить черновики ответов', %s, %s, %s, %s, %s, %s, 'manual', 'manual.run')
        ON CONFLICT (id) DO UPDATE SET goal = EXCLUDED.goal,
            approval_policy_json = EXCLUDED.approval_policy_json
        """,
        (blueprint_version_id, blueprint_id, Json({}), Json([]), Json([]), Json({"external_writes": "manual"}), Json({}), owner_id),
    )
    conn.commit()
    conn.close()


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


def seed_journeys(owner_id: str, business_id: str) -> dict[str, str]:
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
        if flow == "partnership":
            cursor.execute(
                """
                INSERT INTO lead_workstreams (
                    id, lead_id, workstream_type, client_business_id, status,
                    created_by, lifecycle_status, partnership_outcome_json
                ) VALUES (%s, %s, 'client_partnership', %s, 'unprocessed', %s, 'discovered', '{}')
                ON CONFLICT (id) DO UPDATE SET lead_id = EXCLUDED.lead_id,
                    client_business_id = EXCLUDED.client_business_id,
                    workstream_type = 'client_partnership', partnership_outcome_json = '{}',
                    partnership_launched_at = NULL, updated_at = NOW()
                """,
                (fixture_id("workstream:partnership"), lead_id, business_id, owner_id),
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
    foreign_owner_id = ensure_user(FOREIGN_EMAIL, "E2E Чужой владелец")
    business_id = ensure_business(owner_id, OWNER_BUSINESS_NAME, "Санкт-Петербург")
    second_business_id = ensure_business(owner_id, OWNER_SECOND_BUSINESS_NAME, "Санкт-Петербург")
    network_id = ensure_network(owner_id, OWNER_NETWORK_NAME, (business_id, second_business_id))
    foreign_business_id = ensure_business(foreign_owner_id, FOREIGN_BUSINESS_NAME, "Москва")
    foreign_network_id = ensure_network(foreign_owner_id, FOREIGN_NETWORK_NAME, (foreign_business_id,))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET telegram_id = %s WHERE id = %s", (OWNER_TELEGRAM_ID, owner_id))
    conn.commit()
    conn.close()
    seed_owner_review(owner_id, business_id)
    seed_domain_fixtures(owner_id, business_id)
    tokens = seed_journeys(owner_id, business_id)
    print(json.dumps({
        "synthetic_only": True,
        "owner_email": OWNER_EMAIL,
        "admin_email": ADMIN_EMAIL,
        "password": FIXTURE_PASSWORD,
        "owner_id": owner_id,
        "admin_id": admin_id,
        "business_id": business_id,
        "second_business_id": second_business_id,
        "network_id": network_id,
        "foreign_business_id": foreign_business_id,
        "foreign_network_id": foreign_network_id,
        "journey_tokens": tokens,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
