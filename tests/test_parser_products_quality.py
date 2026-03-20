from parser_interception import YandexMapsInterceptionParser


def test_filter_products_quality_removes_editorial_noise():
    parser = YandexMapsInterceptionParser()
    raw = [
        {"name": "Шаверма в лаваше", "price": "360", "category": ""},
        {"name": "Салоны красоты с наградой «Хорошее место 2026»", "price": "", "category": ""},
        {"name": "Туалет", "price": "", "category": ""},
    ]
    clean = parser._filter_products_quality(raw)
    names = [str(item.get("name")) for item in clean]
    assert "Шаверма в лаваше" in names
    assert "Салоны красоты с наградой «Хорошее место 2026»" not in names
    assert "Туалет" not in names


def test_filter_products_quality_supports_grouped_payload():
    parser = YandexMapsInterceptionParser()
    raw_grouped = [
        {
            "category": "Стрижки",
            "items": [
                {"name": "Стрижка мужская", "price": "1200 ₽", "description": ""},
                {"name": "Туалет", "price": "", "description": ""},
            ],
        }
    ]

    clean = parser._filter_products_quality(raw_grouped)
    assert len(clean) == 1
    assert clean[0].get("name") == "Стрижка мужская"
    assert clean[0].get("category") == "Стрижки"


def test_extract_data_from_responses_bruteforce_selects_best_products():
    parser = YandexMapsInterceptionParser()
    parser.api_responses = {
        "https://yandex.ru/maps/api/some_feature": {
            "data": {"items": [{"name": "Туалет", "type": "feature", "value": "есть"}]},
        },
        "https://yandex.ru/maps/api/another_payload": {
            "data": {"menu": [{"name": "Стрижка", "price": {"text": "1500 ₽"}, "category": "Услуги"}]},
        },
    }

    data = parser._extract_data_from_responses()
    products = data.get("products") or []
    names = []
    for block in products:
        if not isinstance(block, dict):
            continue
        for item in block.get("items") or []:
            if isinstance(item, dict):
                names.append(str(item.get("name") or ""))
    assert "Стрижка" in names
    assert "Туалет" not in names
