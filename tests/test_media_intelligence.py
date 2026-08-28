from services import media_intelligence
from services.media_intelligence import (
    detect_photo_library_key,
    ensure_recommended_photo_usage,
    prioritize_selected_photo,
    rank_photo_assets,
)


def test_detects_kids_hair_salon_library():
    key = detect_photo_library_key(
        {
            "name": "Весёлая расчёска",
            "business_type": "детская парикмахерская",
            "industry": "услуги для детей",
        }
    )

    assert key == "kids_hair_salon"


def test_detects_beauty_salon_library():
    key = detect_photo_library_key(
        {
            "name": "Органика",
            "business_type": "салон красоты",
            "industry": "beauty",
        }
    )

    assert key == "beauty_salon"


def test_photo_ranking_prefers_platform_and_goal_match():
    assets = [
        {
            "id": "weak",
            "category": "entrance",
            "quality_score": 70,
            "freshness_score": 70,
            "suitable_platforms": ["yandex_maps"],
        },
        {
            "id": "best",
            "category": "result",
            "quality_score": 65,
            "freshness_score": 70,
            "suitable_platforms": ["instagram", "vk"],
        },
    ]

    ranked = rank_photo_assets(assets, goal="Продающий пост про результат работы", platforms=["instagram", "vk"])

    assert ranked[0]["id"] == "best"
    assert ranked[0]["rank_score"] > ranked[1]["rank_score"]


def test_first_haircut_prefers_child_friendly_interior_over_generic_process():
    assets = [
        {
            "id": "generic-process",
            "category": "process",
            "quality_score": 90,
            "freshness_score": 80,
            "suitable_platforms": [],
        },
        {
            "id": "child-interior",
            "category": "interior",
            "quality_score": 90,
            "freshness_score": 90,
            "suitable_platforms": [],
        },
    ]

    ranked = rank_photo_assets(assets, goal="Первая стрижка ребёнка", platforms=[])

    assert ranked[0]["id"] == "child-interior"


def test_manual_photo_selection_overrides_automatic_ranking():
    ranked = [
        {"id": "automatic", "why": "Автоматический выбор"},
        {"id": "manual", "why": "Альтернатива"},
    ]

    selected, alternatives, manually_selected = prioritize_selected_photo(ranked, "manual")

    assert selected["id"] == "manual"
    assert selected["why"] == "Вы выбрали это фото для публикации."
    assert [item["id"] for item in alternatives] == ["automatic"]
    assert manually_selected is True


class EmptyUsageCursor:
    description = [("photo_asset_id",)]

    def execute(self, query, params=None):
        self.description = [("photo_asset_id",)]

    def fetchone(self):
        return None


def test_preparing_channels_can_fix_a_ready_photo_recommendation(monkeypatch):
    recorded = {}
    monkeypatch.setattr(
        media_intelligence,
        "recommend_media_for_post",
        lambda cursor, business_id, content_plan_item_id: {
            "status": "ready",
            "selected_asset": {"id": "photo-1"},
        },
    )
    monkeypatch.setattr(
        media_intelligence,
        "record_photo_usage",
        lambda cursor, **payload: recorded.update(payload),
    )

    result = ensure_recommended_photo_usage(
        EmptyUsageCursor(),
        business_id="business-1",
        content_plan_item_id="item-1",
    )

    assert result == {"selected": True, "photo_asset_id": "photo-1", "source": "recommendation"}
    assert recorded["photo_asset_id"] == "photo-1"
    assert recorded["target_id"] == "item-1"
    assert recorded["metadata"]["source"] == "automatic_media_planner"
