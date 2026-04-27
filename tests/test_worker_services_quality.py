import sys
import types
import json

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


def test_map_card_services_infers_specific_category_when_source_sends_other():
    card_data = {
        "products": [
            {
                "category": "Другое",
                "items": [
                    {
                        "name": "Консультация врача-косметолога",
                        "description": "Диагностика кожи и подбор ухода",
                        "price": "2500 ₽",
                    }
                ],
            }
        ]
    }

    rows = worker.map_card_services(card_data, "biz_1", "user_1")
    assert len(rows) == 1
    assert rows[0]["category"] != "Другое"
    assert "космет" in str(rows[0]["category"]).lower()


def test_extract_service_category_skips_editorial_category_labels():
    value = worker._extract_service_category({"category": "Бары и пабы с наградой «Хорошее место 2026»"})
    assert value == ""


def test_validate_parsing_result_marks_sparse_apify_yandex_payload_as_failure():
    card_data = {
        "title": "Кебаб",
        "address": "Санкт-Петербург, Плесецкая улица, 2",
        "rating": 3.9,
        "reviews_count": 3,
        "categories": [],
        "products": [],
    }

    is_successful, reason, validation = worker._validate_parsing_result(card_data, source="apify_yandex")

    assert is_successful is False
    assert "apify_yandex_sparse_payload" in reason
    assert validation is not None


def test_validate_parsing_result_keeps_non_apify_sparse_yandex_payload_as_success():
    card_data = {
        "title": "Кебаб",
        "address": "Санкт-Петербург, Плесецкая улица, 2",
        "rating": 3.9,
        "reviews_count": 3,
        "categories": [],
        "products": [],
    }

    is_successful, reason, validation = worker._validate_parsing_result(card_data, source="yandex_business")

    assert is_successful is True
    assert reason == "success"
    assert validation is not None


def test_queue_transient_parse_retry_accepts_apify_sparse_quality_gap(monkeypatch):
    captured = {}

    class FakeCursor:
        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = params

        def close(self):
            return None

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def close(self):
            return None

    fake_conn = FakeConn()
    monkeypatch.setattr(worker, "get_db_connection", lambda: fake_conn)

    queue_dict = {
        "id": "queue-1",
        "source": "apify_yandex",
        "error_message": "",
        "batch_id": "batch-1",
    }
    ok = worker._queue_transient_parse_retry(
        queue_dict,
        "low_quality_payload:apify_yandex_sparse_payload missing=categories,products",
        {"error": "", "message": ""},
    )

    assert ok is True
    assert fake_conn.committed is True
    assert captured["params"][0] == worker.STATUS_PENDING


def test_queue_transient_parse_retry_accepts_apify_timeout(monkeypatch):
    captured = {}

    class FakeCursor:
        def execute(self, query, params):
            captured["params"] = params

        def close(self):
            return None

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def close(self):
            return None

    fake_conn = FakeConn()
    monkeypatch.setattr(worker, "get_db_connection", lambda: fake_conn)

    queue_dict = {
        "id": "queue-timeout-1",
        "source": "apify_yandex",
        "error_message": "",
        "batch_id": "batch-1",
    }
    ok = worker._queue_transient_parse_retry(
        queue_dict,
        "error: apify_parser_subprocess_timeout",
        {"error": "apify_parser_subprocess_timeout", "message": "Apify business parse timeout after 330s"},
    )

    assert ok is True
    assert fake_conn.committed is True
    assert "transient_error=apify_parser_subprocess_timeout" in str(captured["params"][2])


def test_effective_apify_timeout_sec_switches_to_slow_lane_after_timeout_retry(monkeypatch):
    monkeypatch.setenv("APIFY_BUSINESS_PARSE_TIMEOUT_SEC", "330")
    monkeypatch.setenv("APIFY_BUSINESS_PARSE_TIMEOUT_SEC_SLOW", "540")
    monkeypatch.setenv("APIFY_TIMEOUT_SLOW_LANE_AFTER_ATTEMPT", "1")

    queue_dict = {
        "source": "apify_yandex",
        "error_message": "transient_retry_attempt=1; transient_error=apify_parser_subprocess_timeout; detail=timeout",
    }

    assert worker._apify_business_timeout_profile(queue_dict) == "slow_lane"
    assert worker._effective_apify_business_timeout_sec(queue_dict) == 540


def test_parse_card_via_apify_attaches_debug_metadata(monkeypatch):
    class FakeProspectingService:
        def __init__(self, source: str) -> None:
            self.source = source

        def run_business_by_map_url(
            self,
            url: str,
            limit: int,
            timeout_sec: int,
            city: str,
            debug_bundle_dir=None,
            debug_context=None,
        ) -> dict:
            return {
                "run_id": "run-1",
                "dataset_id": "dataset-1",
                "run_input": {
                    "startUrls": [{"url": url}],
                    "businessIds": ["1221240931"],
                    "enrichBusinessData": True,
                },
                "items": [
                    {
                        "name": "Test Business",
                        "address": "Nevsky 1",
                        "description": "Desc",
                        "category": "Cafe",
                        "rating": 4.8,
                        "reviews_count": 12,
                        "website": "https://example.com",
                        "raw_payload_json": {"foo": "bar", "isVerifiedOwner": True},
                        "services_json": [{"name": "Espresso", "category": "Drinks", "price": "200"}],
                        "reviews_json": [{"text": "Great"}],
                        "photos_json": ["https://img.example/1.jpg"],
                    }
                ],
            }

    fake_module = types.ModuleType("services.prospecting_service")
    fake_module.ProspectingService = FakeProspectingService
    monkeypatch.setitem(sys.modules, "services.prospecting_service", fake_module)

    card_data = worker._parse_card_via_apify(
        "https://yandex.ru/maps/org/test/1221240931/",
        parsed_source="yandex_maps",
        source_hint="apify_yandex",
        city="Saint Petersburg",
    )

    apify_debug = card_data.get("_apify_debug")
    assert isinstance(apify_debug, dict)
    assert apify_debug.get("run_id") == "run-1"
    assert apify_debug.get("dataset_id") == "dataset-1"
    assert apify_debug.get("run_input", {}).get("enrichBusinessData") is True
    assert apify_debug.get("item_preview", {}).get("name") == "Test Business"
    assert card_data.get("is_verified") is True
    assert card_data.get("overview", {}).get("is_verified") is True


def test_parse_card_via_apify_falls_back_to_raw_address_and_categories(monkeypatch):
    class FakeProspectingService:
        def __init__(self, source: str) -> None:
            self.source = source

        def run_business_by_map_url(
            self,
            url: str,
            limit: int,
            timeout_sec: int,
            city: str,
            debug_bundle_dir=None,
            debug_context=None,
        ) -> dict:
            return {
                "run_id": "run-2",
                "dataset_id": "dataset-2",
                "run_input": {},
                "items": [
                    {
                        "name": "Kebab",
                        "address": "",
                        "description": "Лермонтовский просп., 50, Санкт-Петербург",
                        "category": "Кафе / быстрое питание",
                        "rating": 0,
                        "reviews_count": 0,
                        "raw_payload_json": {
                            "address": "",
                            "city": "Санкт-Петербург",
                            "street": "Лермонтовский проспект",
                            "house": "50",
                            "categories": ["Кафе", "быстрое питание"],
                            "status": "permanent-closed",
                        },
                        "services_json": [],
                        "reviews_json": [],
                        "photos_json": [],
                    }
                ],
            }

    fake_module = types.ModuleType("services.prospecting_service")
    fake_module.ProspectingService = FakeProspectingService
    monkeypatch.setitem(sys.modules, "services.prospecting_service", fake_module)

    card_data = worker._parse_card_via_apify(
        "https://yandex.ru/maps/org/test/137931029341/",
        parsed_source="yandex_maps",
        source_hint="apify_yandex",
        city="Saint Petersburg",
    )

    assert card_data.get("address") == "Санкт-Петербург, Лермонтовский проспект, 50"
    assert card_data.get("categories") == ["Кафе", "быстрое питание"]
    assert card_data.get("business_status") == "permanent-closed"


def test_parse_card_via_apify_subprocess_entry_writes_result_to_file(monkeypatch, tmp_path):
    class FakeQueue:
        def __init__(self):
            self.items = []

        def put(self, value):
            self.items.append(value)

    monkeypatch.setattr(
        worker,
        "_parse_card_via_apify",
        lambda url, **kwargs: {"title": "Test", "url": url, "payload": {"x": 1}},
    )

    result_file_path = tmp_path / "apify_result.json"
    fake_queue = FakeQueue()
    worker._parse_card_via_apify_subprocess_entry(
        fake_queue,
        "https://yandex.ru/maps/org/test/55526380200/",
        {
            "parsed_source": "yandex_maps",
            "source_hint": "apify_yandex",
            "result_file_path": str(result_file_path),
        },
    )

    assert fake_queue.items == [{"result_file_path": str(result_file_path)}]
    assert json.loads(result_file_path.read_text(encoding="utf-8")).get("title") == "Test"


def test_validate_parsing_result_marks_closed_apify_yandex_business_as_failure():
    card_data = {
        "title": "Кебаб",
        "address": "Санкт-Петербург, Лермонтовский проспект, 50",
        "rating": 0,
        "reviews_count": 0,
        "categories": ["Кафе"],
        "products": [],
        "business_status": "permanent-closed",
    }

    is_successful, reason, validation = worker._validate_parsing_result(card_data, source="apify_yandex")

    assert is_successful is False
    assert reason == "business_closed:permanent_closed"
    assert validation is not None
