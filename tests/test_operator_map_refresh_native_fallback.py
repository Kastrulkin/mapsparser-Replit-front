from services import operator_map_refresh


class Cursor:
    def execute(self, _query, _params):
        return None

    def fetchone(self):
        return {"url": "https://yandex.ru/maps/org/example/1"}


def test_native_map_refresh_does_not_depend_on_apify_runtime_flag(monkeypatch):
    monkeypatch.setattr(operator_map_refresh, "OPERATOR_APIFY_REFRESH_ENABLED", False)

    plan = operator_map_refresh.build_operator_map_refresh_plan(
        Cursor(), business_id="business-1", user_id="user-1",
        source_override="yandex_maps", require_runtime_flag=True,
    )

    assert plan["status"] == "ready"
    assert plan["source"] == "yandex_maps"
    assert plan["blocked_reasons"] == []
