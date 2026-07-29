from services.community_pulse_sources import is_default_industry_source, source_industry_key
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


def test_industry_overview_is_honest_when_no_topic_cluster_is_confirmed():
    rows = [
        {
            "source_id": "source-1",
            "chat_title": "Beauty Owners",
            "telegram_message_id": "message-1",
            "message_date": "2026-07-29T10:00:00+00:00",
            "message_link": "https://t.me/beauty/1",
        },
        {
            "source_id": "source-2",
            "chat_title": "Salon Marketing",
            "telegram_message_id": "message-2",
            "message_date": "2026-07-29T11:00:00+00:00",
            "message_link": "https://t.me/salon/2",
        },
    ]

    pulse = _pulse_overview(rows, {"beauty"})

    assert pulse[0]["message_count"] == 2
    assert pulse[0]["sources_count"] == 2
    assert pulse[0]["title"] == "Новое в отрасли: бьюти-индустрия"
    assert len(pulse[0]["provenance"]) == 2
