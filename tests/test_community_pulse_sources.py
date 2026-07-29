from services.community_pulse_sources import is_default_industry_source, source_industry_key
from services.knowledge_graph_service import normalize_source_categories
from services.operator_mobile_today import _pulse_overview


def test_beauty_public_editorial_source_is_available_by_default():
    source = {
        "title": "Владельцы салонов красоты",
        "source_role": "community",
        "metadata_json": {},
    }

    assert source_industry_key(source) == "beauty"
    assert is_default_industry_source(source, {"beauty"}) is True


def test_business_submitted_source_stays_personal_until_curated():
    source = {
        "title": "Бьюти-практика",
        "source_role": "community",
        "metadata_json": {"submitted_by_business_id": "business-1", "industry_key": "beauty"},
    }

    assert is_default_industry_source(source, {"beauty"}) is False
    source["metadata_json"]["community_default"] = True
    assert is_default_industry_source(source, {"beauty"}) is True


def test_map_discovered_business_channel_is_not_an_industry_default():
    source = {
        "title": "Beauty Day — салон красоты",
        "source_role": "service",
        "metadata_json": {"discovery_origin": "map_parse"},
    }

    assert is_default_industry_source(source, {"beauty"}) is False


def test_admin_categories_define_industry_and_audience_safely():
    owner_chat = {
        "title": "Профессиональный разговор",
        "source_role": "community",
        "metadata_json": {"categories": ["бьюти", "чат", "владельцы"], "community_default": True},
    }
    customer_channel = {
        "title": "Советы салона",
        "source_role": "community",
        "metadata_json": {"categories": ["бьюти", "канал", "для клиентов"], "community_default": True},
    }

    assert source_industry_key(owner_chat) == "beauty"
    assert is_default_industry_source(owner_chat, {"beauty"}) is True
    assert is_default_industry_source(customer_channel, {"beauty"}) is False


def test_source_categories_are_normalized_and_deduplicated():
    categories = normalize_source_categories([" Beauty ", "бьюти", "Чаты", "Для владельцев", "bad/category"])

    assert categories == ["бьюти", "чат", "владельцы"]


def test_industry_overview_shows_ranked_source_highlights_when_no_topic_cluster_is_confirmed():
    rows = [
        {
            "source_id": "source-1",
            "chat_title": "Beauty Owners",
            "telegram_message_id": "message-1",
            "message_date": "2026-07-29T10:00:00+00:00",
            "message_link": "https://t.me/beauty/1",
            "message_text": "Новые требования к маркировке вступят в силу осенью. Салоны обсуждают подготовку.",
            "raw_payload_json": {"priority_score": 70, "raw_engagement": 20},
        },
        {
            "source_id": "source-2",
            "chat_title": "Salon Marketing",
            "telegram_message_id": "message-2",
            "message_date": "2026-07-29T11:00:00+00:00",
            "message_link": "https://t.me/salon/2",
            "message_text": "Как меняется спрос на окрашивание летом. Владельцы делятся наблюдениями.",
            "raw_payload_json": {"priority_score": 90, "raw_engagement": 30},
        },
    ]

    pulse = _pulse_overview(rows, {"beauty"})

    assert len(pulse) == 2
    assert pulse[0]["eyebrow"] == "Главное за день"
    assert pulse[0]["title"] == "Как меняется спрос на окрашивание летом"
    assert pulse[0]["source_url"] == "https://t.me/salon/2"
    assert len(pulse[0]["provenance"]) == 1
