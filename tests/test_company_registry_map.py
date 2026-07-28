from decimal import Decimal

from services.company_registry_service import list_company_map_points


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.query = ""

    def execute(self, query, params):
        self.calls.append((query, dict(params)))
        self.query = query

    def fetchone(self):
        return {
            "matching_count": 3,
            "mapped_count": 2,
            "client_count": 1,
            "lead_count": 1,
            "partner_count": 1,
            "competitor_count": 0,
        }

    def fetchall(self):
        if "ORDER BY c.canonical_name" in self.query:
            return [
                {
                    "id": "company-1",
                    "name": "Тестовая школа",
                    "primary_category": "Детское образование",
                    "latitude": Decimal("55.7558"),
                    "longitude": Decimal("37.6173"),
                    "is_client": True,
                    "is_localos_lead": False,
                    "is_partner": True,
                    "is_competitor": False,
                }
            ]
        return [{"value": "Детское образование", "count": 3}]

    def close(self):
        return None


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def cursor(self, cursor_factory=None):
        return self.fake_cursor


def test_company_map_uses_server_filters_and_serializes_coordinates():
    connection = FakeConnection()

    result = list_company_map_points(
        connection,
        user_id="admin-1",
        is_superadmin=True,
        search="школа",
        role="partner",
        category="Детское образование",
    )

    assert result["counts"] == {
        "matching": 3,
        "mapped": 2,
        "without_coordinates": 1,
        "roles": {"client": 1, "localos_lead": 1, "partner": 1, "competitor": 0},
    }
    assert result["items"][0]["latitude"] == 55.7558
    assert result["items"][0]["longitude"] == 37.6173
    assert [role["key"] for role in result["items"][0]["roles"]] == ["client", "partner"]
    assert result["filters"]["categories"] == [
        {"value": "Детское образование", "label": "Детское образование", "count": 3}
    ]
    assert connection.fake_cursor.calls[0][1]["category"] == "детское образование"
    assert "workstream_type = 'client_partnership'" in connection.fake_cursor.calls[0][0]


def test_company_map_summary_skips_the_heavy_points_query():
    connection = FakeConnection()

    result = list_company_map_points(
        connection,
        user_id="admin-1",
        is_superadmin=True,
        include_points=False,
    )

    assert result["items"] == []
    assert len(connection.fake_cursor.calls) == 2
    assert all("ORDER BY c.canonical_name" not in query for query, _params in connection.fake_cursor.calls)
