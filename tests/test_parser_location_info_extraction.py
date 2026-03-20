from parser_interception import YandexMapsInterceptionParser


def test_extract_location_info_prefers_org_matched_node_and_short_title():
    parser = YandexMapsInterceptionParser()
    parser.org_id = "236899959392"

    payload = {
        "data": {
            "items": [
                {
                    "id": "111",
                    "name": "{\"text\":\"Хорошее место\"}",
                    "fullAddress": "Шумный адрес",
                    "ratingData": {"ratingValue": 0, "reviewCount": 0},
                },
                {
                    "id": "236899959392",
                    "shortTitle": "Кебаб 24",
                    "fullAddress": "Санкт-Петербург, Липовая аллея, 12",
                    "ratingData": {"ratingValue": 4.6, "reviewCount": 187},
                    "categories": [{"name": "Кафе"}, {"name": "Быстрое питание"}],
                    "phones": [{"formatted": "+7 (900) 000-00-00"}],
                },
            ]
        }
    }

    result = parser._extract_location_info(payload)

    assert result.get("title") == "Кебаб 24"
    assert result.get("address") == "Санкт-Петербург, Липовая аллея, 12"
    assert result.get("rating") == "4.6"
    assert result.get("reviews_count") == 187
    assert "Кафе" in (result.get("categories") or [])
    assert result.get("phone") == "+7 (900) 000-00-00"


def test_extract_location_info_ignores_noisy_json_title_candidates():
    parser = YandexMapsInterceptionParser()
    payload = {
        "name": "{\"text\":\"Хорошее место\"}",
        "shortTitle": "Нормальное название",
        "fullAddress": "Тестовый адрес, 1",
        "ratingData": {"ratingValue": 4.9, "reviewCount": 42},
    }

    result = parser._extract_location_info(payload)

    assert result.get("title") == "Нормальное название"
    assert result.get("rating") == "4.9"
    assert result.get("reviews_count") == 42
