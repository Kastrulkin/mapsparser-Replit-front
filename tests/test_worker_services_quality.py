import worker


def test_map_card_services_filters_obvious_noise():
    card_data = {
        "products": [
            {
                "category": "Стрижки",
                "items": [
                    {"name": "Стрижка женская", "price": "1500 ₽", "description": "с укладкой"},
                    {"name": "Туалет", "price": "", "description": ""},
                    {"name": "Собрали в одном месте бары у метро", "price": "", "description": "подборка"},
                    {"name": "Массаж лица", "price": "", "description": "45 минут"},
                ],
            }
        ]
    }

    rows = worker.map_card_services(card_data, "biz_1", "user_1")
    names = {str(r.get("name")) for r in rows}

    assert "Стрижка женская" in names
    assert "Массаж лица" in names
    assert "Туалет" not in names
    assert "Собрали в одном месте бары у метро" not in names


def test_service_rows_grouped_products_have_stable_price_format():
    rows = [
        {
            "name": "Стрижка",
            "category": "Стрижки",
            "description": "Тест",
            "price_from": 1200.0,
            "price_to": 1200.0,
            "raw": {},
        },
        {
            "name": "Окрашивание",
            "category": "Окрашивание",
            "description": "",
            "price_from": 3000.0,
            "price_to": 5000.0,
            "raw": {},
        },
    ]

    grouped = worker._service_rows_to_grouped_products(rows)
    flat = [item for bucket in grouped for item in bucket.get("items", [])]
    by_name = {item.get("name"): item for item in flat}

    assert by_name["Стрижка"]["price"] == "1200 ₽"
    assert by_name["Окрашивание"]["price"] == "3000-5000 ₽"


def test_promote_nested_card_payload_extracts_required_fields():
    payload = {
        "data": {
            "payload": {
                "company": {
                    "name": "Кебаб 24",
                    "address_name": "Санкт-Петербург, Липовая аллея, 14А",
                    "ratingData": {"rating": 4.7, "count": 128},
                    "rubrics": [{"name": "Кафе"}],
                }
            }
        },
        "reviews": [],
    }

    normalized = worker._promote_nested_card_payload(payload)

    assert normalized.get("title_or_name") == "Кебаб 24"
    assert normalized.get("title") == "Кебаб 24"
    assert normalized.get("address") == "Санкт-Петербург, Липовая аллея, 14А"
    assert normalized.get("rating") == 4.7
    assert normalized.get("reviews_count") == 128
    assert normalized.get("categories") == [{"name": "Кафе"}]


def test_captcha_retry_delay_for_mass_batch_is_fixed_30_min_default():
    queue_dict = {"batch_id": "batch-1", "batch_kind": "network_sync"}
    delay = worker._captcha_retry_delay_for_task(queue_dict, attempt_no=4)
    assert int(delay.total_seconds()) == 30 * 60


def test_apply_business_identity_fallback_populates_missing_identity():
    card_data = {"rating": 4.5, "reviews_count": 10}

    used = worker._apply_business_identity_fallback(
        card_data,
        business_name="Кебаб 24",
        business_address="Санкт-Петербург, Липовая аллея, 14А",
    )

    assert used is True
    assert card_data.get("title_or_name") == "Кебаб 24"
    assert card_data.get("title") == "Кебаб 24"
    assert card_data.get("address") == "Санкт-Петербург, Липовая аллея, 14А"
    assert "identity_fallback:business_record" in (card_data.get("warnings") or [])
