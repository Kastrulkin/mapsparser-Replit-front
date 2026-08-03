from api.operator_api import _mobile_navigation


def _by_key(items):
    return {item["key"]: item for item in items}


def test_business_navigation_prioritizes_daily_work_and_progress():
    navigation = _by_key(_mobile_navigation({"kind": "business"}))

    assert navigation["tasks"]["label"] == "В работе"
    assert navigation["tasks"]["group"] == "primary"
    assert navigation["progress"]["group"] == "primary"
    assert navigation["reviews"]["group"] == "more"


def test_platform_navigation_hides_business_growth_progress():
    navigation = _by_key(_mobile_navigation({"kind": "platform"}, is_superadmin=True))

    assert navigation["progress"]["status"] == "hidden"
    assert navigation["tasks"]["status"] == "available"
