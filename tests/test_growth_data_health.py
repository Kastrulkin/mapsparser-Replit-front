from datetime import datetime, timezone

from services.growth_data_health_service import build_analytics_level, build_data_health, build_rhythm, load_finance_data_health
from services.product_telemetry_service import validate_product_event


NOW = datetime(2026, 8, 9, tzinfo=timezone.utc)


def test_data_health_distinguishes_missing_fresh_due_and_stale():
    assert build_data_health(None, None, now=NOW)["status"] == "missing"
    assert build_data_health("2026-08-04T10:00:00+00:00", "crm", 2, now=NOW)["status"] == "fresh"
    assert build_data_health("2026-07-29T10:00:00+00:00", "import", 2, now=NOW)["status"] == "due"
    stale = build_data_health("2026-07-01T10:00:00+00:00", "manual", 2, now=NOW)
    assert stale["status"] == "stale"
    assert "quality_score" not in stale


def test_finance_health_unlock_and_rhythm_are_explicit():
    health = build_data_health("2026-08-08T10:00:00+00:00", "crm", 5, now=NOW)
    assert build_analytics_level(health, source_count=2)["level"] == "actionable"
    assert build_rhythm(health, active_weeks=3) == {"active_weeks": 3, "status": "active", "label": "Регулярный ритм"}


def test_product_telemetry_accepts_fixed_mini_app_events_only():
    assert validate_product_event("onboarding_completed", "telegram_mini_app")[2] is None
    assert validate_product_event("today_delegate_focus", "telegram_mini_app")[2] is None
    assert validate_product_event("unknown", "telegram_mini_app")[2] == "Событие не поддерживается"


class _FinanceHealthCursor:
    def __init__(self):
        self.last_query = ""

    def execute(self, query, _params=None):
        self.last_query = query

    def fetchone(self):
        if "to_regclass" in self.last_query:
            return {"relation": "available"}
        return {
            "record_count": 16,
            "latest_at": "2026-08-08T10:00:00+00:00",
            "latest_source": "yclients_stats",
            "source_count": 1,
            "datasets": ["sales", "services"],
            "active_weeks": 3,
        }


def test_finance_health_describes_coverage_in_business_terms():
    result = load_finance_data_health(_FinanceHealthCursor(), ["business-1"], now=NOW)

    assert result["data_health"]["source"] == "yclients_stats"
    assert result["data_health"]["coverage"] == ["sales", "services"]
    assert result["data_health"]["missing"] == ["загрузка команды и рабочих мест"]
    assert result["analytics_level"]["level"] == "actionable"


class _NetworkFinanceHealthCursor(_FinanceHealthCursor):
    def fetchall(self):
        return [
            {
                "business_id": "fresh-location",
                "record_count": 8,
                "latest_at": "2026-08-08T10:00:00+00:00",
                "latest_source": "yclients_stats",
                "source_count": 1,
                "datasets": ["sales", "services", "capacity"],
                "active_weeks": 3,
            },
            {
                "business_id": "stale-location",
                "record_count": 4,
                "latest_at": "2026-07-01T10:00:00+00:00",
                "latest_source": "manual",
                "source_count": 1,
                "datasets": ["sales"],
                "active_weeks": 1,
            },
        ]


def test_network_finance_health_keeps_each_location_visible():
    result = load_finance_data_health(
        _NetworkFinanceHealthCursor(),
        ["fresh-location", "stale-location", "missing-location"],
        now=NOW,
    )

    assert result["data_health"]["status"] == "missing"
    assert result["location_summary"] == {
        "total": 3,
        "fresh": 1,
        "due": 0,
        "stale": 1,
        "missing": 1,
    }
    locations = {item["business_id"]: item for item in result["location_health"]}
    assert locations["fresh-location"]["status"] == "fresh"
    assert locations["stale-location"]["status"] == "stale"
    assert locations["missing-location"]["status"] == "missing"
