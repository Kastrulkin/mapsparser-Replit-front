import sys
import types
import json

import worker


def test_proxy_preflight_accepts_exact_yandex_organization(monkeypatch):
    class Response:
        status_code = 200
        url = "https://yandex.ru/maps/org/test/230326995176/"
        text = "<html>" + ("x" * 1200) + "230326995176</html>"

    monkeypatch.setattr(worker.requests, "get", lambda *args, **kwargs: Response())
    result = worker._preflight_yandex_proxy(
        "https://yandex.ru/maps/org/test/230326995176/",
        {
            "proxy": {
                "server": "http://proxy.example:33335",
                "username": "user",
                "password": "secret",
            }
        },
    )

    assert result["ok"] is True
    assert result["reason"] == "ok"


def test_proxy_preflight_rejects_limited_body(monkeypatch):
    class Response:
        status_code = 200
        url = "https://yandex.ru/maps/org/test/230326995176/"
        text = "limited"

    monkeypatch.setattr(worker.requests, "get", lambda *args, **kwargs: Response())
    result = worker._preflight_yandex_proxy(
        "https://yandex.ru/maps/org/test/230326995176/",
        {"proxy": {"server": "http://proxy.example:33335"}},
    )

    assert result["ok"] is False
    assert result["reason"] == "limited"


def test_proxy_selection_has_no_unsafe_active_fallback(monkeypatch):
    class Cursor:
        def __init__(self):
            self.execute_count = 0

        def execute(self, _query, _params=None):
            self.execute_count += 1

        def fetchone(self):
            return None

        def close(self):
            return None

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self):
            return self.cursor_value

        def close(self):
            return None

    connection = Connection()
    monkeypatch.setattr(worker, "get_db_connection", lambda: connection)

    assert worker._get_next_proxy_for_playwright() is None
    assert connection.cursor_value.execute_count == 1


def test_reviews_delta_task_uses_native_boundary_without_full_fallback(monkeypatch):
    state = {"updates": [], "applied": 0, "proxy_results": []}

    class Cursor:
        def execute(self, query, params=None):
            state["updates"].append((" ".join(str(query).split()), params))

        def close(self):
            return None

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self):
            return self.cursor_value

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(worker, "get_db_connection", lambda: Connection())
    monkeypatch.setattr(worker, "get_use_apify_map_parsing", lambda _conn: True)
    monkeypatch.setattr(worker, "load_known_yandex_review_ids", lambda *_args, **_kwargs: ["known-1"])
    monkeypatch.setattr(worker, "load_expected_yandex_reviews_total", lambda *_args, **_kwargs: 300)
    monkeypatch.setattr(
        worker,
        "_get_next_proxy_for_playwright",
        lambda: {"id": "proxy-1", "proxy": {"server": "http://proxy.example:33335"}},
    )
    monkeypatch.setattr(worker, "_preflight_yandex_proxy", lambda *_args, **_kwargs: {"ok": True, "reason": "ok"})
    monkeypatch.setattr(worker, "_build_human_browser_profile", lambda: {"user_agent": "ua", "viewport": {}, "launch_args": [], "init_scripts": []})
    monkeypatch.setattr(worker, "get_yandex_cookies", lambda: [])

    def native_parser(_url, **kwargs):
        assert kwargs["parse_mode"] == "reviews_delta"
        assert kwargs["known_review_ids"] == ["known-1"]
        return {
            "reviews": [
                {"id": "new-1", "text": "Новый", "rating": 5},
                {"id": "known-1", "text": "Известный", "rating": 4},
            ],
            "_parser_run": {"delta_boundary_reached": True, "review_stop_reason": "known_review_id"},
        }

    monkeypatch.setattr(worker, "_parse_yandex_card_with_playwright_fallback", native_parser)

    def apply_delta(_cursor, **kwargs):
        state["applied"] += 1
        assert kwargs["business_id"] == "business-1"
        return {"normalized": 2}

    monkeypatch.setattr(worker, "apply_yandex_review_delta", apply_delta)
    monkeypatch.setattr(
        worker,
        "fetch_complete_yandex_reviews",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("full fallback must be skipped")),
    )
    monkeypatch.setattr(worker, "handle_review_sync_completion", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        worker,
        "_mark_proxy_result",
        lambda proxy_id, **kwargs: state["proxy_results"].append((proxy_id, kwargs["success"])),
    )

    worker._process_yandex_reviews_delta_task(
        {
            "id": "queue-1",
            "task_type": "reviews_delta",
            "business_id": "business-1",
            "url": "https://yandex.ru/maps/org/test/1/",
        }
    )

    assert state["applied"] == 1
    assert state["proxy_results"] == [("proxy-1", True)]
    assert any(params and params[0] == worker.STATUS_COMPLETED for _query, params in state["updates"])


def test_reviews_delta_apify_fallback_is_bounded_and_applied_as_delta(monkeypatch):
    state = {"fallback_max_reviews": None, "delta_applied": 0, "snapshot_applied": 0}

    class Cursor:
        def execute(self, _query, _params=None):
            return None

        def close(self):
            return None

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(worker, "get_db_connection", lambda: Connection())
    monkeypatch.setattr(worker, "get_use_apify_map_parsing", lambda _conn: True)
    monkeypatch.setattr(worker, "load_known_yandex_review_ids", lambda *_args, **_kwargs: ["known-1"])
    monkeypatch.setattr(worker, "load_expected_yandex_reviews_total", lambda *_args, **_kwargs: 630)
    monkeypatch.setattr(worker, "_get_next_proxy_for_playwright", lambda: None)
    monkeypatch.setattr(
        worker,
        "_preflight_yandex_proxy",
        lambda *_args, **_kwargs: {"ok": False, "reason": "proxy_unavailable", "elapsed_ms": 0},
    )
    monkeypatch.setattr(worker, "_mark_proxy_result", lambda *_args, **_kwargs: None)

    def bounded_fallback(_url, *, max_reviews, **_kwargs):
        state["fallback_max_reviews"] = max_reviews
        return [
            {"external_review_id": "new-1", "text": "Новый", "rating": 5},
            {"external_review_id": "known-1", "text": "Известный", "rating": 4},
        ]

    def apply_delta(_cursor, **kwargs):
        state["delta_applied"] += 1
        assert kwargs["business_id"] == "business-1"
        return {"normalized": 2}

    def apply_snapshot(*_args, **_kwargs):
        state["snapshot_applied"] += 1
        raise AssertionError("bounded fallback must not replace the complete review snapshot")

    monkeypatch.setattr(worker, "fetch_complete_yandex_reviews", bounded_fallback)
    monkeypatch.setattr(worker, "apply_yandex_review_delta", apply_delta)
    monkeypatch.setattr(worker, "apply_complete_review_snapshot", apply_snapshot)
    monkeypatch.setattr(worker, "handle_review_sync_completion", lambda *_args, **_kwargs: None)

    worker._process_yandex_reviews_delta_task(
        {
            "id": "queue-1",
            "task_type": "reviews_delta",
            "business_id": "business-1",
            "url": "https://yandex.ru/maps/org/test/1/",
        }
    )

    assert state["fallback_max_reviews"] is not None
    assert 0 < state["fallback_max_reviews"] <= 50
    assert state["delta_applied"] == 1
    assert state["snapshot_applied"] == 0


def test_reviews_delta_native_only_runs_directly_without_proxy(monkeypatch):
    state = {"applied": 0}

    class Cursor:
        def execute(self, _query, _params=None):
            return None

        def close(self):
            return None

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(worker, "get_db_connection", lambda: Connection())
    monkeypatch.setattr(worker, "get_use_apify_map_parsing", lambda _conn: False)
    monkeypatch.setattr(worker, "load_known_yandex_review_ids", lambda *_args, **_kwargs: ["known-1"])
    monkeypatch.setattr(worker, "load_expected_yandex_reviews_total", lambda *_args, **_kwargs: 142)
    monkeypatch.setattr(worker, "_get_next_proxy_for_playwright", lambda: None)
    monkeypatch.setattr(
        worker,
        "_preflight_yandex_proxy",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("proxy preflight must be skipped")),
    )
    monkeypatch.setattr(worker, "_build_human_browser_profile", lambda: {"user_agent": "ua", "viewport": {}, "launch_args": [], "init_scripts": []})
    monkeypatch.setattr(worker, "get_yandex_cookies", lambda: [])
    monkeypatch.setattr(
        worker,
        "_parse_yandex_card_with_playwright_fallback",
        lambda _url, **_kwargs: {
            "reviews": [
                {"id": "new-1", "text": "Новый", "rating": 5},
                {"id": "known-1", "text": "Известный", "rating": 4},
            ],
            "_parser_run": {"delta_boundary_reached": True, "review_stop_reason": "known_review_id"},
        },
    )
    monkeypatch.setattr(
        worker,
        "fetch_complete_yandex_reviews",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Apify must stay disabled")),
    )

    def apply_delta(_cursor, **_kwargs):
        state["applied"] += 1
        return {"normalized": 2}

    monkeypatch.setattr(worker, "apply_yandex_review_delta", apply_delta)
    monkeypatch.setattr(worker, "handle_review_sync_completion", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "_mark_proxy_result", lambda *_args, **_kwargs: None)

    worker._process_yandex_reviews_delta_task(
        {
            "id": "queue-1",
            "task_type": "reviews_delta",
            "business_id": "business-1",
            "url": "https://yandex.ru/maps/org/test/1/",
        }
    )

    assert state["applied"] == 1


def test_reviews_delta_native_only_never_falls_back_to_apify(monkeypatch):
    state = {"errors": []}

    class Cursor:
        def execute(self, _query, _params=None):
            return None

        def close(self):
            return None

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            return None

    monkeypatch.setattr(worker, "get_db_connection", lambda: Connection())
    monkeypatch.setattr(worker, "get_use_apify_map_parsing", lambda _conn: False)
    monkeypatch.setattr(worker, "load_known_yandex_review_ids", lambda *_args, **_kwargs: ["known-1"])
    monkeypatch.setattr(worker, "load_expected_yandex_reviews_total", lambda *_args, **_kwargs: 142)
    monkeypatch.setattr(worker, "_get_next_proxy_for_playwright", lambda: None)
    monkeypatch.setattr(worker, "_build_human_browser_profile", lambda: {"user_agent": "ua", "viewport": {}, "launch_args": [], "init_scripts": []})
    monkeypatch.setattr(worker, "get_yandex_cookies", lambda: [])
    monkeypatch.setattr(
        worker,
        "_parse_yandex_card_with_playwright_fallback",
        lambda *_args, **_kwargs: {"error": "captcha_detected"},
    )
    monkeypatch.setattr(
        worker,
        "fetch_complete_yandex_reviews",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Apify must stay disabled")),
    )
    monkeypatch.setattr(worker, "_mark_proxy_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "_handle_worker_error", lambda _queue_id, error: state["errors"].append(error))

    worker._process_yandex_reviews_delta_task(
        {
            "id": "queue-1",
            "task_type": "reviews_delta",
            "business_id": "business-1",
            "url": "https://yandex.ru/maps/org/test/1/",
        }
    )

    assert state["errors"] == ["reviews_delta_native_only_failed:captcha_detected"]


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


def test_validate_native_yandex_rejects_incomplete_review_collection():
    card_data = {
        "title": "Органика",
        "address": "Санкт-Петербург, проспект Испытателей, 35",
        "rating": 4.8,
        "reviews_count": 344,
        "categories": ["Салон красоты"],
        "reviews": [
            {
                "id": f"review-{index}",
                "author": f"Автор {index}",
                "rating": 5,
                "text": f"Отзыв {index}",
            }
            for index in range(5)
        ],
    }

    is_successful, reason, validation = worker._validate_parsing_result(
        card_data,
        source="yandex_maps",
    )

    assert is_successful is False
    assert "incomplete_reviews" in reason
    assert validation is not None


def _complete_native_yandex_card():
    return {
        "title": "Органика",
        "address": "Санкт-Петербург, проспект Испытателей, 35",
        "rating": 4.8,
        "reviews_count": 3,
        "categories": ["Салон красоты"],
        "reviews": [
            {"id": f"native-{index}", "author": "Автор", "text": f"Отзыв {index}"}
            for index in range(3)
        ],
    }


def test_native_yandex_success_skips_apify():
    calls = {"native": 0, "apify": 0}

    def native_parser():
        calls["native"] += 1
        return _complete_native_yandex_card()

    def apify_parser():
        calls["apify"] += 1
        return {"error": "must_not_be_called"}

    result, used_apify, reason = worker._parse_yandex_native_first_with_fallback(
        native_parser,
        apify_parser,
    )

    assert calls == {"native": 1, "apify": 0}
    assert used_apify is False
    assert reason == "success"
    assert result["_parser_route"] == "native_yandex"


def test_incomplete_native_yandex_falls_back_to_apify_once():
    calls = {"apify": 0}
    incomplete = _complete_native_yandex_card()
    incomplete["reviews_count"] = 100
    incomplete["reviews"] = incomplete["reviews"][:1]

    def apify_parser():
        calls["apify"] += 1
        return {"title": "Органика", "categories": ["Салон красоты"]}

    result, used_apify, reason = worker._parse_yandex_native_first_with_fallback(
        lambda: incomplete,
        apify_parser,
    )

    assert calls["apify"] == 1
    assert used_apify is True
    assert "incomplete_reviews" in reason
    assert result["_parser_route"] == "apify_yandex_fallback"
    assert "incomplete_reviews" in result["_native_failure_reason"]


def test_native_yandex_error_falls_back_and_preserves_both_failures():
    result, used_apify, reason = worker._parse_yandex_native_first_with_fallback(
        lambda: {"error": "yandex_rate_limited", "http_status": 429},
        lambda: {"error": "apify_empty_dataset"},
    )

    assert used_apify is True
    assert "yandex_rate_limited" in reason
    assert result["error"] == "apify_empty_dataset"
    assert result["_parser_route"] == "apify_yandex_fallback"
    assert result["_native_failure_reason"] == reason


def test_native_and_apify_exceptions_return_honest_fallback_error():
    def native_parser():
        raise TimeoutError("native timeout")

    def apify_parser():
        raise RuntimeError("provider unavailable")

    result, used_apify, reason = worker._parse_yandex_native_first_with_fallback(
        native_parser,
        apify_parser,
    )

    assert used_apify is True
    assert "native_parser_exception" in reason
    assert result["error"] == "apify_fallback_exception"
    assert "provider unavailable" in result["message"]
    assert result["_native_failure_reason"] == reason


def test_google_and_2gis_never_enter_native_yandex_route():
    assert worker._should_try_native_yandex("apify_google", "google_maps") is False
    assert worker._should_try_native_yandex("apify_2gis", "2gis") is False
    assert worker._should_try_native_yandex("apify_yandex", "yandex_maps") is True


def test_forced_native_subprocess_returns_bounded_timeout(monkeypatch):
    state = {"started": False, "terminated": False, "joins": []}

    class FakeQueue:
        def empty(self):
            return True

    class FakeProcess:
        def start(self):
            state["started"] = True

        def join(self, timeout=None):
            state["joins"].append(timeout)

        def is_alive(self):
            return True

        def terminate(self):
            state["terminated"] = True

    class FakeContext:
        def Queue(self, maxsize):
            assert maxsize == 1
            return FakeQueue()

        def Process(self, target, args, daemon):
            assert target is worker._parse_yandex_card_subprocess_entry
            assert daemon is True
            return FakeProcess()

    monkeypatch.setattr(worker.multiprocessing, "get_context", lambda method: FakeContext())
    monkeypatch.setattr(
        worker,
        "parse_yandex_card",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("sync path must be skipped")),
    )

    result = worker._parse_yandex_card_with_playwright_fallback(
        "https://yandex.ru/maps/org/1/",
        keep_open_on_captcha=False,
        timeout_sec=180,
        force_subprocess=True,
    )

    assert result["error"] == "parser_subprocess_timeout"
    assert "180s" in result["message"]
    assert state == {"started": True, "terminated": True, "joins": [180, 5]}


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


def test_apify_empty_dataset_stops_after_small_dedicated_retry_budget(monkeypatch):
    monkeypatch.setenv("TRANSIENT_PARSE_MAX_ATTEMPTS", "8")
    monkeypatch.setenv("APIFY_EMPTY_DATASET_MAX_ATTEMPTS", "2")
    monkeypatch.setattr(
        worker,
        "get_db_connection",
        lambda: (_ for _ in ()).throw(AssertionError("terminal retry must not touch the database")),
    )

    ok = worker._queue_transient_parse_retry(
        {
            "id": "queue-empty-1",
            "source": "apify_yandex",
            "error_message": "transient_retry_attempt=2; transient_error=apify_empty_dataset",
        },
        "error: apify_parser_subprocess_exception detail=Apify returned empty dataset for business card parsing",
        {
            "error": "apify_empty_dataset",
            "message": "Apify returned empty dataset for business card parsing",
        },
    )

    assert ok is False


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
