from scripts.classify_beauty_community_sources import classify_archive_source, classify_map_source


def test_curated_professional_archive_becomes_default_source():
    result = classify_archive_source({
        "title": "Дневник бьюти-предпринимателя",
        "source_role": "unknown",
        "documents_count": 935,
    })

    assert result["decision"] == "professional"
    assert result["role"] == "expert"
    assert "владельцы" in result["categories"]


def test_customer_facing_archive_is_explicitly_excluded():
    result = classify_archive_source({
        "title": "Салоны Красоты Москвы",
        "source_role": "salon",
        "documents_count": 17_523,
    })

    assert result == {"decision": "b2c", "reason": "explicit_customer_facing_archive"}


def test_ready_customer_post_library_does_not_enter_owner_pulse():
    result = classify_archive_source({
        "title": "Готовые посты мастера маникюра",
        "source_role": "service",
        "documents_count": 6_145,
    })

    assert result["decision"] == "content_library"
    assert result["role"] == "expert"
    assert "контент" in result["categories"]


def test_map_profile_channel_is_b2c_unless_admin_overrode_it():
    source = {"metadata_json": {"discovery_origin": "map_parse"}}
    curated = {"metadata_json": {"discovery_origin": "map_parse", "community_default": True}}

    assert classify_map_source(source)["decision"] == "b2c"
    assert classify_map_source(curated)["decision"] == "review"
