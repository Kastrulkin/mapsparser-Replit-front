from services.creator_taxonomy_service import classify_creator_profile


def _profile(*, description: str = "", evidence: list[dict] | None = None, research: dict | None = None) -> dict:
    return {
        "display_name": "Тестовый автор",
        "description": description,
        "metadata_json": {"research": research or {}, "qualification": {}},
        "channels": [{
            "platform": "telegram",
            "canonical_url": "https://t.me/example",
            "public_metrics_json": {"followers": 7200},
            "metadata_json": {},
        }],
        "evidence": evidence or [],
        "commercial": {},
    }


def test_discovery_city_is_not_treated_as_home_city():
    result = classify_creator_profile(_profile(
        evidence=[{
            "summary_text": "Видео содержит обзор кафе на Парнасе в Санкт-Петербурге.",
            "source_url": "https://example.test/video",
            "confidence": 0.9,
        }],
        research={"spb_expansion_queries": ["кафе Выборгский район СПб"]},
    ))

    assert result["home_city"] is None
    assert {item["name"] for item in result["content_geographies"]} >= {"Санкт-Петербург", "Выборгский"}
    assert any(item["basis"] == "discovery_query" for item in result["discovery_geography"])


def test_explicit_local_profile_sets_home_city_and_content_taxonomy():
    result = classify_creator_profile(_profile(
        description="Петербургский блогер и мама: обзоры детских кафе, афиша и куда пойти на Проспекте Просвещения.",
    ))

    assert result["home_city"] == "Санкт-Петербург"
    assert result["confidence"]["home_city"] >= 0.85
    assert result["primary_topic"] in {"family_parenting", "food_cafes", "local_places"}
    assert "reviews" in result["content_styles"]
    assert "guides_and_selections" in result["content_styles"]
    assert "Проспект Просвещения" in result["metro_stations"]
    assert "parents_and_families" in result["audience_types"]
    assert result["audience_size_band"] == "nano"


def test_direct_channel_follower_count_sets_micro_audience_band():
    profile = _profile(description="Петербургский блогер: обзоры семейных мест")
    profile["channels"] = [{
        "platform": "threads",
        "canonical_url": "https://www.threads.net/@local_parent",
        "follower_count": 24000,
    }]
    result = classify_creator_profile(profile)

    assert result["audience_size_band"] == "micro"


def test_tallinn_profile_is_not_misclassified_as_spb():
    result = classify_creator_profile(_profile(
        description="Family video blogger based in Tallinn. Travel, museums, local events and city life.",
        research={"spb_expansion_queries": ["СПб куда пойти"]},
    ))

    assert result["home_city"] == "Таллинн"
    assert result["home_city"] != "Санкт-Петербург"
    assert any(item["name"] == "Санкт-Петербург" for item in result["discovery_geography"])


def test_multiple_claimed_home_cities_remain_unconfirmed():
    result = classify_creator_profile(_profile(
        description="Блогер из Москвы и Санкт-Петербурга: lifestyle и городские места.",
    ))

    assert result["home_city"] is None
    assert {item["name"] for item in result["content_geographies"]} >= {"Москва", "Санкт-Петербург"}


def test_audience_geography_requires_explicit_audience_statement():
    without_statement = classify_creator_profile(_profile(
        evidence=[{"summary_text": "Обзор мест Санкт-Петербурга", "source_url": "https://example.test/post"}],
    ))
    with_statement = classify_creator_profile(_profile(
        evidence=[{"summary_text": "70% аудитории из Санкт-Петербурга", "source_url": "https://example.test/media-kit"}],
    ))

    assert without_statement["audience_geography"] == []
    assert with_statement["audience_geography"][0]["name"] == "Санкт-Петербург"
