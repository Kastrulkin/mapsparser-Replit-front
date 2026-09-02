from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.creator_offer_distribution_service import _eligibility, distribution_enabled, validate_offer


def campaign(**offer_overrides):
    offer = {
        "service": "Детская стрижка",
        "category": "семейные услуги",
        "benefit": "Бесплатная стрижка",
        "capacity": 3,
        **offer_overrides,
    }
    return {
        "geography": {"city": "Санкт-Петербург"},
        "audience": {"topics": ["семья", "дети"]},
        "formats": ["пост"],
        "offer": offer,
    }


def candidate(**overrides):
    return {
        "city": "Санкт-Петербург",
        "district": "Выборгский",
        "topics_json": ["семья", "дети"],
        "formats_json": ["пост"],
        "disposition": "available",
        "accepts_barter": True,
        "brand_safety_status": "ok",
        "excluded_categories_json": [],
        **overrides,
    }


def test_unknown_geography_is_strictly_excluded():
    reason, _snapshot = _eligibility(
        candidate(city=None, district=None, content_geographies_json=[], audience_geography_json=[]),
        campaign(),
    )
    assert reason == "geography_unknown"


def test_unconfirmed_barter_is_strictly_excluded():
    reason, _snapshot = _eligibility(candidate(accepts_barter=None), campaign(barter=True))
    assert reason == "barter_unconfirmed"


def test_shortlist_does_not_limit_distribution_but_business_exclusion_does():
    shortlist_reason, snapshot = _eligibility(candidate(disposition="shortlisted"), campaign())
    excluded_reason, _excluded_snapshot = _eligibility(candidate(disposition="excluded"), campaign())
    assert shortlist_reason is None
    assert snapshot["disposition"] == "shortlisted"
    assert excluded_reason == "excluded_for_business"


def test_pause_and_category_preferences_block_only_new_matching_offers():
    pause_reason, _snapshot = _eligibility(
        candidate(paused_until=datetime.now(timezone.utc) + timedelta(days=7)),
        campaign(),
    )
    category_reason, _category_snapshot = _eligibility(
        candidate(excluded_categories_json=["семейные услуги"]),
        campaign(),
    )
    assert pause_reason == "creator_paused"
    assert category_reason == "category_blocked"


def test_distribution_flag_is_off_by_default(monkeypatch):
    monkeypatch.delenv("CREATOR_OFFER_DISTRIBUTION_ENABLED", raising=False)
    monkeypatch.delenv("CREATOR_OFFER_DISTRIBUTION_BUSINESS_IDS", raising=False)
    assert distribution_enabled() is False
    monkeypatch.setenv("CREATOR_OFFER_DISTRIBUTION_ENABLED", "true")
    assert distribution_enabled() is True
    monkeypatch.setenv("CREATOR_OFFER_DISTRIBUTION_BUSINESS_IDS", "business-1")
    assert distribution_enabled("business-1") is True
    assert distribution_enabled("business-2") is False


def test_offer_requires_a_future_machine_readable_deadline():
    offer = campaign()
    offer["period"] = {"end_at": "когда-нибудь"}
    with pytest.raises(ValueError, match="будущей датой"):
        validate_offer(offer)


def test_migration_backfills_without_creating_notifications():
    source = Path("alembic_migrations/versions/20260902_add_creator_offer_distribution.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS creator_business_preferences" in source
    assert "CREATE TABLE IF NOT EXISTS creator_offer_recipients" in source
    assert "progress_json JSONB" in source
    assert "FROM creator_collaborations collaboration" in source
    assert "ON CONFLICT (campaign_id, creator_profile_id) DO NOTHING" in source
    assert "INSERT INTO creator_notification_outbox" not in source


def test_worker_distribution_is_batched_and_idempotent_by_contract():
    service = Path("src/services/creator_offer_distribution_service.py").read_text(encoding="utf-8")
    worker = Path("src/worker.py").read_text(encoding="utf-8")
    assert "ON CONFLICT (campaign_id, creator_profile_id) DO NOTHING" in service
    assert "ON CONFLICT (dedupe_key) DO NOTHING" in service
    assert "process_next_distribution_run" in worker
    assert "_process_creator_offer_distribution_if_due()" in worker
