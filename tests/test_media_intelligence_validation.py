import pytest

from services import ai_runtime


class FakeVisionClient:
    def __init__(self, *, should_fail=False):
        self.should_fail = should_fail
        self.calls = 0

    def analyze_screenshot(self, *_args, **_kwargs):
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("provider down")
        return """
        {
          "category": "result",
          "quality_score": 80,
          "freshness_score": 75,
          "orientation": "vertical",
          "people_count": 1,
          "service_tags": ["стрижка"],
          "suitable_platforms": ["instagram", "vk"],
          "caption": "готовая работа",
          "why": "виден результат"
        }
        """


class FakeCursor:
    def __init__(self, *, enabled=True, cache=None, balance=100):
        self.enabled = enabled
        self.cache = cache
        self.balance = balance
        self.last_query = ""
        self.last_params = ()
        self.queries = []
        self.usage_events = []
        self.photo_updates = []
        self.reservation_inserts = []
        self.reservation_updates = []
        self.ledger_entries = []
        self.user_updates = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        self.queries.append(self.last_query)
        if "insert into ai_usage_events" in self.last_query:
            self.usage_events.append(params or ())
        if "update photo_assets" in self.last_query:
            self.photo_updates.append((self.last_query, params or ()))
        if "insert into operatorcreditreservations" in self.last_query:
            self.reservation_inserts.append(params or ())
        if "update operatorcreditreservations" in self.last_query:
            self.reservation_updates.append(params or ())
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())
        if "update users" in self.last_query:
            self.user_updates.append(params or ())

    def fetchone(self):
        query = self.last_query
        if "from ai_capability_settings" in query:
            return {"enabled": self.enabled}
        if "from photo_assets" in query and "asset_version" in query:
            return {
                "id": "asset-1",
                "asset_version": 1,
                "original_url": "https://example.com/photo.jpg",
                "storage_key": "",
                "versions_json": {},
            }
        if "from ai_runtime_cache" in query:
            if self.cache:
                return {"result_json": self.cache, "usage_event_id": "source-usage-1"}
            return None
        if "to_regclass" in query:
            return {"to_regclass": "operatorcreditreservations"}
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": 0}
        if "from operatorcreditreservations" in query:
            return {
                "id": "reservation-1",
                "business_id": "biz-1",
                "user_id": "user-1",
                "action_key": ai_runtime.PHOTO_ANALYSIS_ACTION_KEY,
                "status": "reserved",
                "estimated_credits": ai_runtime.PHOTO_ANALYSIS_CREDITS,
                "reserved_credits": ai_runtime.PHOTO_ANALYSIS_CREDITS,
                "charged_credits": 0,
                "released_credits": 0,
                "credit_ledger_id": None,
            }
        if "returning id" in query and self.reservation_inserts:
            return {
                "id": "reservation-1",
                "status": "reserved",
                "reserved_credits": self.reservation_inserts[-1][6],
            }
        return None


def test_new_photo_analysis_charges_two_credits_and_updates_asset(monkeypatch):
    cursor = FakeCursor()
    client = FakeVisionClient()
    monkeypatch.setattr(ai_runtime, "get_gigachat_client", lambda: client)

    result = ai_runtime.analyze_photo_runtime(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        asset_id="asset-1",
        image_base64="ZmFrZQ==",
        context={"business_type": "детская парикмахерская"},
    )

    assert result["success"] is True
    assert result["status"] == "analyzed"
    assert result["charged_credits"] == 2
    assert client.calls == 1
    assert len(cursor.usage_events) == 1
    assert cursor.usage_events[0][8] == 2
    assert cursor.usage_events[0][10] is False
    assert cursor.ledger_entries
    assert any("analysis_status = 'analyzed'" in query for query, _params in cursor.photo_updates)


def test_cached_photo_analysis_does_not_call_provider_or_charge(monkeypatch):
    cursor = FakeCursor(cache={"category": "result", "quality_score": 80})
    client = FakeVisionClient()
    monkeypatch.setattr(ai_runtime, "get_gigachat_client", lambda: client)

    result = ai_runtime.analyze_photo_runtime(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        asset_id="asset-1",
        image_base64="ZmFrZQ==",
        context={"business_type": "детская парикмахерская"},
    )

    assert result["success"] is True
    assert result["status"] == "cached"
    assert result["charged_credits"] == 0
    assert client.calls == 0
    assert not cursor.reservation_inserts
    assert not cursor.ledger_entries
    assert len(cursor.usage_events) == 1
    assert cursor.usage_events[0][8] == 0
    assert cursor.usage_events[0][10] is True


def test_provider_error_retries_releases_credits_and_marks_failed(monkeypatch):
    cursor = FakeCursor()
    client = FakeVisionClient(should_fail=True)
    monkeypatch.setattr(ai_runtime, "get_gigachat_client", lambda: client)
    monkeypatch.setattr(ai_runtime.time, "sleep", lambda _seconds: None)

    result = ai_runtime.analyze_photo_runtime(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        asset_id="asset-1",
        image_base64="ZmFrZQ==",
        context={"business_type": "детская парикмахерская"},
    )

    assert result["success"] is False
    assert result["status"] == "analysis_failed"
    assert result["charged_credits"] == 0
    assert result["attempts"] == 3
    assert client.calls == 3
    assert not cursor.ledger_entries
    assert cursor.reservation_updates
    assert any(params[0] == "released" for params in cursor.reservation_updates)
    assert any(params[0] == "analysis_failed" for _query, params in cursor.photo_updates)


def test_photo_analysis_economics_flags_meter_adjustment_when_margin_is_low():
    result = ai_runtime.estimate_photo_analysis_economics(
        photo_count=100,
        provider_total_cost=1200,
        credit_price=5,
        multiplier=10,
    )

    assert result["estimated_credits"] == 200
    assert result["estimated_revenue"] == 1000
    assert result["needs_meter_adjustment"] is True


def test_photo_analysis_economics_passes_when_margin_covers_multiplier():
    result = ai_runtime.estimate_photo_analysis_economics(
        photo_count=100,
        provider_total_cost=80,
        credit_price=5,
        multiplier=10,
    )

    assert result["estimated_credits"] == 200
    assert result["estimated_revenue"] == 1000
    assert result["needs_meter_adjustment"] is False
