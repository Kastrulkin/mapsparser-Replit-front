from api.operator_api import _mobile_navigation


PAID_MODULES = {"operator", "progress", "content", "finance", "partnerships"}


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
