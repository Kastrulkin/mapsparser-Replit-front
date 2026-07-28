from services.company_geocoding_service import (
    build_geocoding_query,
    build_geocoding_queries,
    choose_candidate,
    score_candidate,
)


def test_build_query_adds_city_and_country_once():
    query = build_geocoding_query({
        "address": "Комендантская пл., 1А",
        "city": "Санкт-Петербург",
    })

    assert query == "1А, Комендантская пл., Санкт-Петербург, Россия"


def test_build_query_reorders_provider_address_for_nominatim():
    query = build_geocoding_query({
        "address": "Санкт-Петербург, Пушкин, Конюшенная улица, 1/18Д",
        "city": "Пушкин",
    })

    assert query == "1/18Д, Конюшенная улица, Пушкин, Санкт-Петербург, Россия"


def test_build_query_has_compact_corpus_fallback():
    queries = build_geocoding_queries({
        "address": "Санкт-Петербург, Новоизмайловский проспект, 22, корп. 2",
        "city": "Санкт-Петербург",
    })

    assert "22 к2, Новоизмайловский проспект, Санкт-Петербург, Россия" in queries


def test_build_query_keeps_nearest_locality_and_simplifies_litera():
    queries = build_geocoding_queries({
        "address": "Санкт-Петербург, Пушкин, Конюшенная улица, 1/18Д",
        "city": "Пушкин",
    })

    assert "1/18, Конюшенная улица, Пушкин, Россия" in queries


def test_build_query_simplifies_settlement_prefix():
    queries = build_geocoding_queries({
        "address": "Московская область, посёлок городского типа Путилково, Новотушинская улица, 1",
        "city": "",
    })

    assert "1, Новотушинская улица, Путилково, Россия" in queries


def test_precise_house_and_city_match_is_accepted():
    query = "22, Невский проспект, Санкт-Петербург, Россия"
    candidate = {
        "lat": "59.9363",
        "lon": "30.3211",
        "display_name": "22, Невский проспект, Санкт-Петербург, Россия",
        "addresstype": "house",
        "osm_type": "way",
        "osm_id": 123,
        "address": {"house_number": "22", "city": "Санкт-Петербург"},
    }

    result = choose_candidate(query, "Санкт-Петербург", [candidate])

    assert result is not None
    assert result["confidence"] == 1.0
    assert result["latitude"] == 59.9363


def test_city_level_result_is_rejected_even_when_coordinates_exist():
    score, reasons = score_candidate(
        "Санкт-Петербург, Невский проспект, 22, Россия",
        "Санкт-Петербург",
        {
            "lat": "59.93",
            "lon": "30.31",
            "display_name": "Санкт-Петербург, Россия",
            "addresstype": "city",
            "address": {"city": "Санкт-Петербург"},
        },
    )

    assert score == 0.0
    assert reasons == ["administrative_result"]


def test_wrong_city_or_house_does_not_pass_confidence_threshold():
    result = choose_candidate(
        "Санкт-Петербург, Невский проспект, 22, Россия",
        "Санкт-Петербург",
        [{
            "lat": "55.75",
            "lon": "37.61",
            "display_name": "10, Невский переулок, Москва, Россия",
            "addresstype": "house",
            "address": {"house_number": "10", "city": "Москва"},
        }],
    )

    assert result is None
