import os
from urllib.parse import urlparse
import uuid

import psycopg2
import pytest
from psycopg2.extras import Json, RealDictCursor

from services.creator_promotion_service import (
    add_deliverable,
    add_metric_snapshot,
    approve_campaign_terms,
    confirm_candidate_contact,
    create_campaign,
    create_collaboration,
    create_creator_room,
    enqueue_creator_search,
    load_campaign,
    load_creator_room,
    load_search_job,
    prepare_candidate_outreach,
    preview_candidate_outreach,
    process_creator_search_job,
    update_shortlist,
    upsert_manual_creator,
    verify_deliverable,
)
from services.creator_source_enrichment_service import enrich_creator_sources


pytestmark = pytest.mark.skipif(
    os.getenv("CREATOR_PROMOTION_INTEGRATION") != "1",
    reason="requires an isolated migrated PostgreSQL database",
)


def test_creator_promotion_end_to_end_on_postgres():
    connection = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    user_id = f"creator-test-user-{uuid.uuid4()}"
    business_id = f"creator-test-business-{uuid.uuid4()}"
    source_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    try:
        cursor.execute("INSERT INTO users (id, email, name) VALUES (%s, %s, 'Test')", (user_id, f"{user_id}@example.test"))
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, business_type, address, city, website) VALUES (%s, %s, 'Семейный салон', 'Салон', 'Приморский район', 'Санкт-Петербург', 'https://salon.example')",
            (business_id, user_id),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_sources (
                id, source_type, external_key, title, canonical_url, source_role,
                visibility, sensitivity_class, status, metadata_json
            ) VALUES (%s, 'telegram', %s, 'Мамы Приморского района', 'https://t.me/mamy_primorskogo',
                      'community', 'public', 'public', 'active', %s)
            """,
            (
                source_id,
                f"creator-test-{source_id}",
                Json({}),
            ),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_documents (
                id, source_id, external_id, document_type, content_text, content_hash,
                sensitivity_class, published_at
            ) VALUES (%s, %s, %s, 'telegram_message',
                      'Приморский район Санкт-Петербург родители дети детская стрижка обзор',
                      %s, 'public', NOW())
            """,
            (document_id, source_id, f"doc-{document_id}", f"hash-{document_id}"),
        )
        cursor.execute(
            "UPDATE knowledge_documents SET metadata_json = %s WHERE id = %s",
            (Json({"views": 5000, "reactions_total": 250, "forwards": 30}), document_id),
        )

        enrichment = enrich_creator_sources(cursor, source_ids=[source_id])
        assert enrichment["updated"] == 1
        assert enrichment["coverage"]["city"] == 1
        assert enrichment["coverage"]["area"] == 1
        assert enrichment["coverage"]["metrics"] == 1
        cursor.execute("SELECT metadata_json FROM knowledge_sources WHERE id = %s", (source_id,))
        source_metadata = cursor.fetchone()["metadata_json"]
        assert source_metadata["city"] == "Санкт-Петербург"
        assert source_metadata["area"] == "Приморский район"
        assert source_metadata["public_metrics"]["median_views"] == 5000

        queued = enqueue_creator_search(
            cursor,
            business_id=business_id,
            user_id=user_id,
            brief={
                "city": "Санкт-Петербург",
                "area": "Приморский район",
                "audience": "родители дети",
                "service": "детская стрижка",
                "formats": ["обзор"],
            },
        )
        assert queued["status"] == "created"
        search = process_creator_search_job(cursor, business_id=business_id, job_id=queued["id"])
        assert search["status"] == "ready"
        assert search["results"][0]["evidence"]

        upsert_manual_creator(
            cursor,
            business_id=business_id,
            payload={
                "search_job_id": search["id"],
                "display_name": "Проверенный локальный автор",
                "url": "https://instagram.com/local_creator_test",
                "city": "Санкт-Петербург",
                "topics": ["родители", "детская стрижка"],
                "formats": ["обзор"],
                "contactability": "advertising_contact",
                "preferred_contact": "https://t.me/local_creator_ads",
                "public_metrics": {"views": 2500, "reactions": 125},
                "evidence_items": [
                    {
                        "source_url": "https://example.test/local-creator-proof",
                        "summary": "Публичный профиль подтверждает город, тему и рекламный контакт",
                        "confidence": 0.9,
                    }
                ],
            },
        )
        search = load_search_job(cursor, business_id=business_id, job_id=search["id"])
        manual_result = next(item for item in search["results"] if item["display_name"] == "Проверенный локальный автор")
        assert manual_result["result_group"] != "insufficient_data"
        assert manual_result["evidence"][0]["source_url"] == "https://example.test/local-creator-proof"
        cursor.execute(
            "SELECT preferred_contact FROM creator_commercial_profiles WHERE creator_profile_id = %s",
            (manual_result["creator_profile_id"],),
        )
        assert cursor.fetchone()["preferred_contact"] == "https://t.me/local_creator_ads"

        search = update_shortlist(cursor, business_id=business_id, result_id=manual_result["id"], status="shortlisted")
        campaign = create_campaign(
            cursor,
            business_id=business_id,
            user_id=user_id,
            payload={
                "search_job_id": search["id"],
                "title": "Локальный обзор",
                "goal": "Обращения",
                "formats": ["обзор"],
                "offer": {"details": "Обзор после визита"},
                "budget": {"maximum": 15000, "currency": "RUB"},
                "period": {"description": "до 15 сентября"},
                "constraints": {"usage_rights": {"description": "репост 3 месяца"}},
            },
        )
        cursor.execute("SELECT COUNT(*) AS count FROM prospectingleads WHERE source_external_id = %s", (f"creator:{manual_result['creator_profile_id']}",))
        leads_before_preview = cursor.fetchone()["count"]
        preview = preview_candidate_outreach(
            cursor,
            business_id=business_id,
            campaign_id=campaign["id"],
            candidate_id=campaign["candidates"][0]["id"],
        )
        assert preview["requires_campaign_approval"] is True
        assert preview["writes_performed"] == 0
        assert "Проверенный локальный автор" in preview["message"]
        assert "Семейный салон" in preview["message"]
        assert preview["contact"]["status"] == "public_unverified"
        campaign = approve_campaign_terms(cursor, business_id=business_id, campaign_id=campaign["id"])
        with pytest.raises(ValueError, match="подтвердите принадлежность контакта"):
            prepare_candidate_outreach(
                cursor,
                connection,
                business_id=business_id,
                campaign_id=campaign["id"],
                candidate_id=campaign["candidates"][0]["id"],
                user_id=user_id,
            )
        confirmed_preview = confirm_candidate_contact(
            cursor,
            business_id=business_id,
            campaign_id=campaign["id"],
            candidate_id=campaign["candidates"][0]["id"],
            user_id=user_id,
            payload={
                "confirmed": True,
                "confirmation_note": "Контакт указан в публичном описании канала",
                "confirmation_source_url": "https://example.test/local-creator-proof",
            },
        )
        assert confirmed_preview["contact"]["status"] == "confirmed"
        cursor.execute(
            "SELECT score_snapshot_json->'contact_confirmation'->>'confirmed_by' AS confirmed_by FROM creator_campaign_candidates WHERE id = %s",
            (campaign["candidates"][0]["id"],),
        )
        assert cursor.fetchone()["confirmed_by"] == user_id
        cursor.execute(
            "SELECT confirmation_status FROM creator_commercial_profiles WHERE creator_profile_id = %s",
            (manual_result["creator_profile_id"],),
        )
        assert cursor.fetchone()["confirmation_status"] == "observed"
        cursor.execute("SELECT COUNT(*) AS count FROM prospectingleads WHERE source_external_id = %s", (f"creator:{manual_result['creator_profile_id']}",))
        assert cursor.fetchone()["count"] == leads_before_preview
        other_business_id = f"creator-other-business-{uuid.uuid4()}"
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, business_type, city) VALUES (%s, %s, 'Другой бизнес', 'Салон', 'Москва')",
            (other_business_id, user_id),
        )
        with pytest.raises(LookupError):
            load_search_job(cursor, business_id=other_business_id, job_id=search["id"])
        with pytest.raises(LookupError):
            update_shortlist(cursor, business_id=other_business_id, result_id=manual_result["id"], status="rejected")
        with pytest.raises(LookupError):
            load_campaign(cursor, business_id=other_business_id, campaign_id=campaign["id"])

        prepared = prepare_candidate_outreach(
            cursor,
            connection,
            business_id=business_id,
            campaign_id=campaign["id"],
            candidate_id=campaign["candidates"][0]["id"],
            user_id=user_id,
        )
        assert prepared["recipient_ready"] is True
        cursor.execute("SELECT telegram_url FROM prospectingleads WHERE id = %s", (prepared["lead_id"],))
        assert cursor.fetchone()["telegram_url"] == "https://t.me/local_creator_ads"
        collaboration = create_collaboration(
            cursor,
            business_id=business_id,
            campaign_id=campaign["id"],
            candidate_id=campaign["candidates"][0]["id"],
            user_id=user_id,
            payload={"status": "invited", "terms": {"format": "обзор"}},
        )
        room = create_creator_room(cursor, business_id=business_id, collaboration_id=collaboration["id"])
        token = urlparse(room["public_url"]).path.rsplit("/", 1)[-1]
        assert load_creator_room(cursor, token)["business_name"] == "Семейный салон"

        collaboration = add_deliverable(
            cursor,
            business_id=business_id,
            collaboration_id=collaboration["id"],
            payload={
                "platform": "telegram",
                "deliverable_type": "post",
                "publication_url": "https://t.me/mamy_primorskogo/10",
                "tracking": {
                    "destination_url": "https://salon.example/book?location=spb",
                    "promo_code": "SALON10",
                    "cta": "Записаться на детскую стрижку",
                },
            },
        )
        deliverable = collaboration["deliverables"][0]
        assert "utm_source=telegram" in deliverable["tracking"]["tracked_url"]
        assert deliverable["tracking"]["promo_code"] == "SALON10"
        collaboration = verify_deliverable(cursor, business_id=business_id, deliverable_id=deliverable["id"], status="verified")
        deliverable = collaboration["deliverables"][0]
        assert [item["checkpoint"] for item in deliverable["measurement_checkpoints"]] == ["24h", "7d", "14d"]
        metrics = add_metric_snapshot(
            cursor,
            business_id=business_id,
            deliverable_id=deliverable["id"],
            payload={"checkpoint": "24h", "reach": 5000, "clicks": 100, "inquiries": 10, "placement_cost": 10000, "source_type": "business_reported", "confidence": 1},
        )
        assert metrics["calculated"]["cpm"] == 2000
        assert metrics["calculated"]["cost_per_inquiry"] == 1000
        assert metrics["measurement_checkpoints"]["completed"] == 1
        assert metrics["measurement_checkpoints"]["pending"] == 2
    finally:
        connection.rollback()
        cursor.close()
        connection.close()
