from services.operator_paid_actions import (
    APIFY_CREDIT_MULTIPLIER,
    PAID_ACTIONS,
    build_map_reviews_refresh_offer,
    build_paid_action_offer,
)


def test_paid_action_registry_covers_operator_paid_actions() -> None:
    assert PAID_ACTIONS["map_reviews_refresh"]["action_class"] == "paid_external"
    assert PAID_ACTIONS["review_replies_generate"]["action_class"] == "paid_compute"
    assert PAID_ACTIONS["news_generate"]["action_class"] == "paid_compute"
    assert PAID_ACTIONS["social_post_generate"]["action_class"] == "paid_compute"
    assert PAID_ACTIONS["services_optimize"]["action_class"] == "paid_compute"


def test_map_refresh_offer_is_proposal_only_and_uses_apify_multiplier() -> None:
    consent_policy = {"mode": "ask_each_time", "execution_allowed_without_prompt": False}
    offer = build_map_reviews_refresh_offer(
        business_id="biz-1",
        balance_credits=1000,
        estimated_credits=10,
        consent_policy=consent_policy,
    )

    assert offer["action_key"] == "map_reviews_refresh"
    assert offer["action_class"] == "paid_external"
    assert offer["status"] == "proposal_only"
    assert offer["consent_required"] is True
    assert offer["default_consent_mode"] == "ask_each_time"
    assert offer["provider"] == "apify"
    assert offer["credit_multiplier"] == APIFY_CREDIT_MULTIPLIER
    assert offer["affordable_runs_estimate"] == 100
    assert offer["paid_actions_performed"] is False
    assert offer["external_write"] is False
    assert offer["current_consent_policy"] == consent_policy


def test_offer_without_estimate_does_not_invent_price() -> None:
    offer = build_paid_action_offer("review_replies_generate", business_id="biz-1")

    assert offer["estimate_available"] is False
    assert offer["estimated_credits"] is None
    assert "Точная стоимость" in offer["copy"]["disclosure"]
    assert "Публикация ответов в карты сейчас ручная" in offer["copy"]["manual_publication_note"]
