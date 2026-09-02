from api.operator_api import _mobile_capability_for_action, _mobile_filter_payload_items, _mobile_navigation
from subscription_manager import build_subscription_capabilities


PAID_MODULES = {"operator", "progress", "content", "finance", "partnerships"}


def _scope(tier: str, status: str = "active") -> dict:
    return {
        "kind": "business",
        "id": "business-1",
        "business_ids": ["business-1"],
        "subscription_tier": tier,
        "subscription_status": status,
        "subscription_ends_at": None,
    }


def _navigation(tier: str, status: str = "active") -> dict:
    return {item["key"]: item for item in _mobile_navigation(_scope(tier, status))}


def test_unpaid_business_does_not_expose_paid_miniapp_modules():
    scope = {
        "kind": "business",
        "id": "dolgoozernaya",
        "business_ids": ["dolgoozernaya"],
        "subscription_tier": "trial",
        "subscription_status": "inactive",
        "subscription_ends_at": None,
    }

    navigation = {item["key"]: item for item in _mobile_navigation(scope)}

    exposed = {
        key
        for key in PAID_MODULES
        if navigation[key]["status"] == "available"
    }
    assert exposed == set(), (
        "Unpaid Mini App scope exposes paid modules: "
        + ", ".join(sorted(exposed))
    )


def test_starter_opens_maps_radar_reviews_and_progress_only():
    navigation = _navigation("starter")

    for key in ("cards", "services", "reviews", "progress", "feed", "community_sources"):
        assert navigation[key]["status"] == "available"
    for key in ("partnerships", "influencers", "content", "finance", "operator"):
        assert navigation[key]["status"] == "read_only"
        assert navigation[key]["preview_available"] is True


def test_professional_opens_acquisition_but_not_management():
    navigation = _navigation("professional")

    assert navigation["partnerships"]["status"] == "available"
    assert navigation["influencers"]["status"] == "available"
    assert navigation["finance"]["status"] == "read_only"
    assert navigation["content"]["required_tier_name"] == "Управление"
    assert navigation["operator"]["status"] == "read_only"


def test_concierge_opens_management_modules():
    navigation = _navigation("concierge")

    for key in ("content", "finance", "operator", "partnerships", "influencers"):
        assert navigation[key]["status"] == "available"


def test_mobile_actions_map_to_the_same_capabilities_as_navigation():
    assert _mobile_capability_for_action("cards.refresh") == "maps"
    assert _mobile_capability_for_action("reviews.generate") == "maps.reviews"
    assert _mobile_capability_for_action("partnerships.lead.delete") == "partnerships"
    assert _mobile_capability_for_action("content.plan.generate") == "social_content"
    assert _mobile_capability_for_action("finance.sales_import") == "finance"


def test_today_and_workspace_payloads_drop_closed_module_items():
    access = build_subscription_capabilities(tier="starter", status="active")
    payload = {
        "items": [
            {"id": "maps", "screen": "cards", "title": "Обновить карточку"},
            {"id": "finance", "screen": "finance", "title": "Проверить выручку"},
            {"id": "partners", "screen": "partnerships", "title": "Ответ партнёра"},
        ]
    }

    filtered = _mobile_filter_payload_items(payload, access)

    assert [item["id"] for item in filtered["items"]] == ["maps"]
