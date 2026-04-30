from src.core.content_plan_generator import build_content_plan_skeleton


def test_content_plan_skeleton_respects_allowed_period_and_sources():
    context = {
        "business": {"name": "LocalOS Cafe", "city": "Санкт-Петербург"},
        "services": [{"id": "svc-1", "name": "Кофе навынос"}],
        "seo_keywords": [{"keyword": "кофе рядом", "views": 1200}],
        "sales_signals": [{"title": "Капучино", "transaction_id": "tx-1"}],
        "audit_signals": [{"title": "Мало свежих новостей", "problem": "нет активности"}],
    }

    plan = build_content_plan_skeleton(
        context,
        period_days=60,
        density="standard",
        content_mix={
            "services": True,
            "seo": True,
            "sales": True,
            "audit": True,
            "seasonal": False,
        },
    )

    assert plan["period_days"] == 60
    assert plan["title"] == "Контент-план на 60 дней"
    assert len(plan["items"]) >= 4
    assert any(item["content_type"] == "service" for item in plan["items"])
    assert any(item["content_type"] == "seo" for item in plan["items"])
    assert any(item["content_type"] == "sales" for item in plan["items"])
    assert any(item["content_type"] == "audit" for item in plan["items"])


def test_content_plan_skeleton_falls_back_to_30_for_invalid_period():
    plan = build_content_plan_skeleton(
        {"business": {"name": "Fallback Biz"}},
        period_days=45,
        density="light",
        content_mix={},
    )

    assert plan["period_days"] == 30
    assert len(plan["items"]) >= 4
    assert all(item["theme"] for item in plan["items"])
