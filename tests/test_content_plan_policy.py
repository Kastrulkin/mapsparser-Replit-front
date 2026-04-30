from src import subscription_manager


def test_content_plan_horizons_for_starter(monkeypatch):
    monkeypatch.setattr(
        subscription_manager,
        "get_subscription_access",
        lambda business_id: {
            "tier": "starter",
            "is_superadmin": False,
        },
    )

    assert subscription_manager.get_allowed_content_plan_horizons("biz-1") == [30]


def test_content_plan_horizons_for_concierge(monkeypatch):
    monkeypatch.setattr(
        subscription_manager,
        "get_subscription_access",
        lambda business_id: {
            "tier": "concierge",
            "is_superadmin": False,
        },
    )

    assert subscription_manager.get_allowed_content_plan_horizons("biz-2") == [30, 60, 90]


def test_content_plan_horizons_for_superadmin_override(monkeypatch):
    monkeypatch.setattr(
        subscription_manager,
        "get_subscription_access",
        lambda business_id: {
            "tier": "starter",
            "is_superadmin": True,
        },
    )

    assert subscription_manager.get_allowed_content_plan_horizons("biz-3") == [30, 60, 90]
