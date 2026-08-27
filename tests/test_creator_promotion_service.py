from datetime import datetime, timezone

import pytest
import services.creator_promotion_service

from services.creator_promotion_service import (
    SCORING_VERSION,
    _candidate_matches_audience_range,
    _creator_result_limit,
    _normalize_audience_range,
    add_metric_snapshot,
    build_tracking_plan,
    campaign_terms_review,
    creator_feature_state,
    influencer_workspace,
    preview_candidate_outreach,
    score_creator_candidate,
)


def test_creator_result_limit_defaults_and_clamps():
    assert _creator_result_limit({}) == 30
    assert _creator_result_limit({"result_limit": "30"}) == 30
    assert _creator_result_limit({"result_limit": 0}) == 1
    assert _creator_result_limit({"result_limit": 250}) == 100
    assert _creator_result_limit({"result_limit": "invalid"}) == 30


def test_audience_range_is_normalized_and_validated():
    assert _normalize_audience_range({}) == (None, None)
    assert _normalize_audience_range({"audience_min": "500", "audience_max": "10000"}) == (500, 10000)
    with pytest.raises(ValueError, match="Минимальная аудитория"):
        _normalize_audience_range({"audience_min": 10000, "audience_max": 500})


def test_audience_range_is_a_hard_filter_and_requires_confirmed_metrics():
    brief = {"audience_min": 500, "audience_max": 10000}
    assert _candidate_matches_audience_range({"public_metrics": {"followers": 4500}}, brief) is True
    assert _candidate_matches_audience_range({"public_metrics": {"subscribers": 12000}}, brief) is False
    assert _candidate_matches_audience_range({"public_metrics": {}}, brief) is False
    assert _candidate_matches_audience_range({"public_metrics": {}}, {}) is True


def test_campaign_terms_review_requires_explicit_agreement():
    incomplete = campaign_terms_review({
        "formats": ["обзор"],
        "offer": {"details": "Визит"},
        "budget": {},
        "period": {},
        "constraints": {"usage_rights": {"confirmed": False}},
    })
    assert incomplete["missing"] == ["бюджет или бартер", "сроки", "права на материал"]

    complete = campaign_terms_review({
        "formats": ["обзор"],
        "offer": {"barter": True},
        "period": {"description": "до 15 сентября"},
        "constraints": {"usage_rights": {"description": "репост 3 месяца"}},
    })
    assert complete["missing"] == []
from services.creator_source_enrichment_service import (
    ENRICHMENT_VERSION,
    infer_creator_source_metadata,
)
from services.creator_catalog_service import creator_platform
from services.creator_profile_revalidation_service import compare_creator_identity
from services.lead_workstream_service import CREATOR_COLLABORATION, normalize_workstream_type


def test_creator_features_are_off_by_default(monkeypatch):
    for name in (
        "PROMOTION_HUB_ENABLED",
        "INFLUENCER_DISCOVERY_ENABLED",
        "INFLUENCER_OUTREACH_ENABLED",
        "INFLUENCER_METRICS_ENABLED",
        "INFLUENCER_SOURCE_ENRICHMENT_ENABLED",
        "INFLUENCER_PROFILE_REVALIDATION_ENABLED",
        "INFLUENCER_BUSINESS_IDS",
    ):
        monkeypatch.delenv(name, raising=False)

    assert creator_feature_state("business-1") == {
        "promotion_hub": False,
        "discovery": False,
        "outreach": False,
        "metrics": False,
        "source_enrichment": False,
        "profile_revalidation": False,
        "supported_platforms": ["telegram", "vk", "website", "instagram", "threads", "tiktok", "youtube"],
        "pilot_restricted": False,
    }


def test_creator_feature_allowlist_is_enforced(monkeypatch):
    monkeypatch.setenv("PROMOTION_HUB_ENABLED", "true")
    monkeypatch.setenv("INFLUENCER_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("INFLUENCER_OUTREACH_ENABLED", "true")
    monkeypatch.setenv("INFLUENCER_METRICS_ENABLED", "true")
    monkeypatch.setenv("INFLUENCER_BUSINESS_IDS", "business-1,business-2")

    assert creator_feature_state("business-1")["metrics"] is True
    assert creator_feature_state("business-3")["promotion_hub"] is False


def test_influencer_workspace_exposes_safe_cards_and_block_level_access(monkeypatch):
    monkeypatch.setattr(services.creator_promotion_service, "_load_business", lambda _cursor, _business_id: {"id": "business-1"})
    monkeypatch.setattr(services.creator_promotion_service, "list_search_jobs", lambda _cursor, _business_id: [{"id": "search-1", "results_count": 1, "shortlisted_count": 0}])
    monkeypatch.setattr(
        services.creator_promotion_service,
        "load_search_job",
        lambda _cursor, **_kwargs: {
            "id": "search-1",
            "status": "completed",
            "brief": {"city": "Санкт-Петербург"},
            "results": [{
                "id": "result-1",
                "creator_profile_id": "creator-1",
                "display_name": "Анна про Петербург",
                "description": "Обзоры локальных мест и услуг",
                "platform": "telegram",
                "canonical_url": "https://t.me/anna_spb",
                "home_city": "Санкт-Петербург",
                "primary_topic": "local_places",
                "secondary_topics": ["beauty_wellness"],
                "content_styles": ["reviews"],
                "observed_formats": ["обзор"],
                "public_metrics": {"subscribers": 4200},
                "preferred_contact": "private@example.test",
                "contactability": "advertising_contact",
                "accepts_barter": True,
                "score": 86,
                "reasons": ["Пишет о местах Санкт-Петербурга"],
                "shortlist_status": "suggested",
                "evidence": [{"type": "public_post", "summary": "Публичный обзор салона", "source_url": "https://t.me/anna_spb/10"}],
            }],
        },
    )
    monkeypatch.setattr(services.creator_promotion_service, "list_campaigns", lambda _cursor, _business_id: [{"offer": {"barter": True, "service": "Стрижка"}}])
    monkeypatch.setattr(services.creator_promotion_service, "creator_automation_allowed", lambda _cursor, _business_id: False)
    monkeypatch.setattr(services.creator_promotion_service, "creator_feature_state", lambda _business_id: {"promotion_hub": True, "discovery": True})

    workspace = influencer_workspace(None, business_id="business-1", filters={"barter": "true"})

    assert workspace["counts"] == {"total": 1, "returned": 1, "shortlisted": 0}
    assert workspace["offer"]["service"] == "Стрижка"
    assert workspace["creators"][0]["audience_count"] == 4200
    assert workspace["creators"][0]["public_url"] == "https://t.me/anna_spb"
    assert "preferred_contact" not in workspace["creators"][0]
    assert workspace["access"]["discovery"]["status"] == "available"
    assert workspace["access"]["message_generation"]["status"] == "payment_required"


def test_creator_score_is_weighted_explainable_and_versioned():
    result = score_creator_candidate(
        {
            "display_name": "Мамы Приморского района",
            "description": "Санкт-Петербург: родители с детьми, семейные места и детская стрижка",
            "primary_city": "Санкт-Петербург",
            "primary_area": "Приморский район",
            "topics": ["дети", "родители", "семейные места"],
            "evidence_texts": ["Регулярные обзоры локальных мест для родителей"],
            "document_count": 24,
            "public_metrics": {"median_views": 5000, "median_reactions": 250},
            "formats": ["обзор", "пост"],
            "last_observed_at": datetime.now(timezone.utc),
            "contactability": "advertising_contact",
            "accepts_barter": True,
            "brand_safety_status": "clear",
        },
        {
            "city": "Санкт-Петербург",
            "area": "Приморский район",
            "audience": "родители с детьми",
            "service": "детская стрижка",
            "formats": ["обзор"],
        },
    )

    assert result["score"] >= 78
    assert result["result_group"] == "best_fit"
    assert result["breakdown"] == {
        "locality": 30,
        "audience_fit": 25,
        "engagement": 15,
        "format_fit": 10,
        "freshness": 10,
        "commercial_readiness": 10,
    }
    assert result["scoring_version"] == SCORING_VERSION
    assert any("Приморский район" in reason for reason in result["reasons"])


def test_blocked_creator_is_excluded_even_with_a_high_score():
    result = score_creator_candidate(
        {
            "display_name": "Центральный район",
            "description": "Москва, локальные места и семейная аудитория",
            "primary_city": "Москва",
            "primary_area": "Центральный район",
            "topics": ["семья"],
            "document_count": 20,
            "public_metrics": {"median_views": 10000, "median_reactions": 600},
            "formats": ["пост"],
            "last_observed_at": datetime.now(timezone.utc),
            "contactability": "advertising_contact",
            "price_min": 10000,
            "brand_safety_status": "blocked",
        },
        {"city": "Москва", "area": "Центральный район", "audience": "семья", "formats": ["пост"]},
    )

    assert result["gates"]["brand_safety"] is False
    assert result["result_group"] == "excluded"


def test_known_wrong_geography_is_a_hard_exclusion():
    result = score_creator_candidate(
        {
            "display_name": "Казань сегодня",
            "description": "Городские новости Казани",
            "primary_city": "Казань",
            "document_count": 12,
            "formats": ["пост"],
            "last_observed_at": datetime.now(timezone.utc),
            "contactability": "public_contact",
        },
        {"city": "Москва", "formats": ["пост"]},
    )

    assert result["gates"]["geography_compatible"] is False
    assert result["result_group"] == "excluded"


def test_structured_local_search_uses_content_geography_platform_style_and_contact():
    result = score_creator_candidate(
        {
            "display_name": "Семейный Выборгский",
            "primary_city": None,
            "primary_area": None,
            "content_geographies": [
                {"kind": "city", "name": "Санкт-Петербург"},
                {"kind": "district", "name": "Выборгский"},
            ],
            "metro_stations": ["Проспект Просвещения"],
            "audience_types": ["parents_and_families"],
            "content_styles": ["reviews"],
            "platforms": ["telegram", "threads"],
            "audience_size_band": "micro",
            "formats": ["telegram_post", "short_text_post"],
            "document_count": 12,
            "last_observed_at": datetime.now(timezone.utc),
            "contactability": "public_contact",
        },
        {
            "city": "Санкт-Петербург",
            "area": "Выборгский",
            "audience": "родители",
            "content_styles": ["reviews"],
            "platforms": ["telegram", "threads"],
            "audience_size_bands": ["micro"],
            "contact_required": True,
        },
    )

    assert result["gates"]["geography_compatible"] is True
    assert result["gates"]["platform_compatible"] is True
    assert result["gates"]["content_style_compatible"] is True
    assert result["gates"]["public_contact_available"] is True
    assert result["breakdown"]["locality"] == 30


def test_discovery_geography_does_not_satisfy_locality_gate():
    result = score_creator_candidate(
        {
            "display_name": "Автор из Таллинна",
            "primary_city": "Таллинн",
            "discovery_geography": [{"kind": "city", "name": "Санкт-Петербург"}],
            "platforms": ["instagram"],
            "document_count": 4,
            "last_observed_at": datetime.now(timezone.utc),
            "contactability": "public_contact",
        },
        {"city": "Санкт-Петербург"},
    )

    assert result["gates"]["geography_compatible"] is False
    assert result["result_group"] == "excluded"


def test_non_creator_business_channel_is_a_hard_exclusion():
    result = score_creator_candidate(
        {
            "display_name": "Салон в Приморском районе",
            "description": "Санкт-Петербург, родители и дети",
            "primary_city": "Санкт-Петербург",
            "primary_area": "Приморский район",
            "topics": ["семья"],
            "document_count": 20,
            "formats": ["пост"],
            "last_observed_at": datetime.now(timezone.utc),
            "contactability": "public_contact",
            "creator_eligible": False,
        },
        {"city": "Санкт-Петербург", "area": "Приморский район", "audience": "семья"},
    )

    assert result["gates"]["creator_eligible"] is False
    assert result["result_group"] == "excluded"


def test_public_source_enrichment_extracts_provenance_metrics_and_ad_contact():
    result = infer_creator_source_metadata(
        {
            "title": "Мамы Приморского района СПб",
            "canonical_url": "https://t.me/mamy_primorskogo",
            "source_role": "community",
            "metadata_json": {},
            "document_count": 12,
            "latest_document_at": datetime(2026, 8, 20, tzinfo=timezone.utc),
            "documents_json": [
                {
                    "content": "Родители и дети: обзор семейных мест. По вопросам рекламы @mamy_ads",
                    "metadata": {"views": 5000, "reactions_total": 250, "forwards": 20},
                },
                {
                    "content": "Новая подборка для семей Санкт-Петербурга",
                    "metadata": {"views": 3000, "reactions_total": 150, "forwards": 10},
                },
            ],
        }
    )

    assert result["city"] == "Санкт-Петербург"
    assert result["area"] == "Приморский район"
    assert "семья и дети" in result["topics"]
    assert result["creator_profile_type"] == "community"
    assert result["creator_eligible"] is True
    assert result["contactability"] == "advertising_contact"
    assert result["preferred_contact"] == "@mamy_ads"
    assert result["public_metrics"]["median_views"] == 4000
    assert result["public_metrics"]["median_reactions"] == 200
    assert result["creator_enrichment"]["version"] == ENRICHMENT_VERSION
    assert result["creator_enrichment"]["evidence"]["city"]["basis"] == "public_title_or_documents"


def test_tallinn_creator_enrichment_supports_local_travel_and_expat_topics():
    result = infer_creator_source_metadata(
        {
            "title": "Tallinn Expats & Travel",
            "canonical_url": "https://t.me/tallinn_expats",
            "source_role": "expert",
            "metadata_json": {},
            "document_count": 6,
            "documents_json": [
                {
                    "content": "Tallinn airport transfer, relocation and travel guide",
                    "metadata": {"views": 1200, "reactions": 48},
                }
            ],
        }
    )

    assert result["city"] == "Tallinn"
    assert {"путешествия", "трансферы и транспорт", "экспаты"}.issubset(set(result["topics"]))
    assert result["creator_profile_type"] == "author"
    assert result["creator_eligible"] is True


def test_service_source_is_retained_as_evidence_but_not_creator_candidate():
    result = infer_creator_source_metadata(
        {
            "title": "Косметология СПб",
            "canonical_url": "https://t.me/clinic_spb",
            "source_role": "service",
            "metadata_json": {"official_brand_source": True},
            "document_count": 3,
            "documents_json": [{"content": "Красота и косметология", "metadata": {}}],
        }
    )

    assert result["creator_eligible"] is False
    assert result["creator_profile_type"] == "channel"


def test_one_off_city_mention_does_not_create_false_locality():
    documents = [
        {"content": "Новости индустрии без географической привязки", "metadata": {}}
        for _index in range(19)
    ]
    documents.append({"content": "Один участник конференции приехал из Tallinn", "metadata": {}})
    result = infer_creator_source_metadata(
        {
            "title": "Профессиональный отраслевой канал",
            "canonical_url": "https://t.me/industry",
            "source_role": "expert",
            "metadata_json": {},
            "document_count": 20,
            "documents_json": documents,
        }
    )

    assert "city" not in result


def test_creator_workstream_alias_is_supported():
    assert normalize_workstream_type("influencer") == CREATOR_COLLABORATION


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.threads.com/@local_creator", "threads"),
        ("https://www.instagram.com/local_creator", "instagram"),
        ("https://www.youtube.com/@local_creator", "youtube"),
        ("https://www.tiktok.com/@local_creator", "tiktok"),
    ],
)
def test_creator_catalog_supports_multiplatform_profiles(url, platform):
    assert creator_platform(url) == platform


def test_creator_identity_change_requires_strong_title_and_topic_drift():
    changed = compare_creator_identity(
        "Семейный Санкт-Петербург",
        "Афиша и места для родителей с детьми",
        "Путь к себе",
        "Психология и внутренний мир",
    )
    same_creator = compare_creator_identity(
        "BEAUTYHOLIC",
        "Петербургский блог об уходе и красоте",
        "BEAUTYHOLIC | Санкт-Петербург",
        "Уход, beauty и локальные находки",
    )

    assert changed["mismatch"] is True
    assert same_creator["mismatch"] is False


class ExistingDeliverableCursor:
    def execute(self, _query, _params):
        return None

    def fetchone(self):
        return {"id": "deliverable-1"}


def test_creator_metrics_reject_negative_values():
    with pytest.raises(ValueError, match="не могут быть отрицательными"):
        add_metric_snapshot(
            ExistingDeliverableCursor(),
            business_id="business-1",
            deliverable_id="deliverable-1",
            payload={"reach": -1, "source_type": "business_reported", "confidence": 1},
        )


def test_creator_metrics_do_not_accept_unverified_revenue_sources():
    with pytest.raises(ValueError, match="только из данных бизнеса или CRM"):
        add_metric_snapshot(
            ExistingDeliverableCursor(),
            business_id="business-1",
            deliverable_id="deliverable-1",
            payload={"confirmed_revenue": 1000, "source_type": "creator_reported", "confidence": 0.8},
        )


def test_creator_tracking_plan_preserves_query_and_adds_stable_attribution():
    plan = build_tracking_plan(
        {
            "destination_url": "https://example.test/book?location=spb",
            "promo_code": " organika 15 ",
            "cta": "Записаться на консультацию",
        },
        platform="telegram",
        campaign_id="campaign-12345678",
        creator_profile_id="creator-87654321",
    )

    assert "location=spb" in plan["tracked_url"]
    assert "utm_source=telegram" in plan["tracked_url"]
    assert "utm_medium=influencer" in plan["tracked_url"]
    assert plan["promo_code"] == "ORGANIKA15"
    assert plan["measurement_schedule"] == ["24h", "7d", "14d"]


def test_creator_tracking_plan_rejects_non_http_destination():
    with pytest.raises(ValueError, match="начинаться с http"):
        build_tracking_plan(
            {"destination_url": "javascript:alert(1)"},
            platform="telegram",
            campaign_id="campaign-1",
            creator_profile_id="creator-1",
        )


class OutreachPreviewCursor:
    def __init__(self, row):
        self.row = row

    def execute(self, _query, _params):
        return None

    def fetchone(self):
        return self.row


@pytest.mark.parametrize(
    ("business_name", "city", "address", "goal", "expected_identity", "expected_goal"),
    [
        (
            "Органика",
            "Санкт-Петербург",
            "Санкт-Петербург, проспект Испытателей, 35",
            "Получить измеримые обращения в Санкт-Петербурге",
            "Органика (Санкт-Петербург, проспект Испытателей, 35)",
            "получить измеримые обращения в Санкт-Петербурге",
        ),
        (
            "Весёлая расчёска",
            "Санкт-Петербург",
            "Материнская точка сети",
            "Получить записи родителей",
            "Весёлая расчёска (Санкт-Петербург)",
            "получить записи родителей",
        ),
        (
            "Riderra (Tallinn)",
            "",
            "",
            "Проверить бронирования трансферов в Таллине",
            "Riderra (Tallinn)",
            "проверить бронирования трансферов в Таллине",
        ),
    ],
)
def test_outreach_preview_keeps_public_location_clean_and_preserves_goal_case(
    business_name,
    city,
    address,
    goal,
    expected_identity,
    expected_goal,
):
    cursor = OutreachPreviewCursor({
        "id": "candidate-1",
        "creator_profile_id": "creator-1",
        "candidate_status": "shortlisted",
        "score_snapshot_json": {},
        "campaign_status": "draft",
        "goal": goal,
        "formats_json": ["пост"],
        "offer_json": {"barter": True},
        "budget_json": {},
        "period_json": {"description": "в течение 14 дней"},
        "constraints_json": {"usage_rights": {"description": "репост 90 дней"}},
        "display_name": "Локальный автор",
        "primary_city": city,
        "primary_area": None,
        "reasons_json": [],
        "platform": "telegram",
        "canonical_url": "https://t.me/local_author",
        "contactability": "advertising_contact",
        "preferred_contact": "https://t.me/local_author_ads",
        "contact_confirmation_status": "observed",
        "business_name": business_name,
        "business_city": city,
        "business_address": address,
        "evidence_summary": "публичная площадка подтверждает локальную аудиторию",
        "evidence_source_url": "https://example.test/evidence",
        "evidence_confidence": 0.9,
    })

    preview = preview_candidate_outreach(
        cursor,
        business_id="business-1",
        campaign_id="campaign-1",
        candidate_id="candidate-1",
    )

    assert f"Мы — {expected_identity}." in preview["message"]
    assert f"чтобы {expected_goal}." in preview["message"]


def test_localos_sender_collects_creator_terms_without_claiming_a_specific_client():
    cursor = OutreachPreviewCursor({
        "id": "candidate-1",
        "creator_profile_id": "creator-1",
        "candidate_status": "shortlisted",
        "score_snapshot_json": {},
        "campaign_status": "draft",
        "sender_mode": "localos_for_partner",
        "goal": "Получить обращения",
        "formats_json": ["пост"],
        "offer_json": {"mode": "creator_terms_intake"},
        "budget_json": {"requires_creator_quote": True},
        "period_json": {"description": "сроки согласуются после брифа"},
        "constraints_json": {"usage_rights": {"description": "права согласуются отдельно"}},
        "display_name": "Локальный автор",
        "primary_city": "Санкт-Петербург",
        "primary_area": None,
        "reasons_json": [],
        "platform": "threads",
        "canonical_url": "https://www.threads.com/@local_author",
        "contactability": "advertising_contact",
        "preferred_contact": "https://t.me/local_author_ads",
        "contact_confirmation_status": "observed",
        "business_name": "Органика",
        "business_city": "Санкт-Петербург",
        "business_address": "проспект Испытателей, 35",
        "evidence_summary": "публичный профиль посвящён локальному beauty-контенту",
        "evidence_source_url": "https://www.threads.com/@local_author",
        "evidence_confidence": 0.9,
    })

    preview = preview_candidate_outreach(
        cursor,
        business_id="business-1",
        campaign_id="campaign-1",
        candidate_id="candidate-1",
    )

    assert "Мы в LocalOS" in preview["message"]
    assert "форматы, цены, географию аудитории, свежие охваты" in preview["message"]
    assert "Органика" not in preview["message"]
    assert preview["sender_mode"] == "localos_for_partner"
