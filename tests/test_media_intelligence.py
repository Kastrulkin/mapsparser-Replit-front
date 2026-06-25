from services.media_intelligence import detect_photo_library_key, rank_photo_assets


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
