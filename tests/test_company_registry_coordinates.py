from __future__ import annotations

from typing import Any

import pytest

from services.company_registry_service import ensure_company_for_business, ensure_company_for_lead


class RecordingCursor:
    def __init__(self, *, linked_lead: bool = False):
        self.calls: list[tuple[str, tuple[Any, ...] | dict[str, Any] | None]] = []
        self.query = ""
        self.linked_lead = linked_lead

    def execute(self, query, params=None):
        self.query = " ".join(str(query).split())
        self.calls.append((self.query, params))

    def fetchone(self):
        if "FROM business_company_links" in self.query:
            return None
        if "SELECT company_id, company_location_id FROM prospectingleads" in self.query:
            if self.linked_lead:
                return {"company_id": "company-1", "company_location_id": "location-1"}
            return None
        if "FROM company_identity_keys" in self.query:
            return None
        return None

    def fetchall(self):
        return []

    def close(self):
        return None


class RecordingConnection:
    def __init__(self, *, linked_lead: bool = False):
        self.cursor_instance = RecordingCursor(linked_lead=linked_lead)

    def cursor(self, cursor_factory=None):
        return self.cursor_instance


def _location_insert_params(connection: RecordingConnection) -> tuple[Any, ...]:
    for query, params in connection.cursor_instance.calls:
        if "INSERT INTO company_locations" in query:
            assert isinstance(params, tuple)
            return params
    raise AssertionError("company location insert was not executed")


def test_business_registry_uses_legacy_geo_coordinates():
    connection = RecordingConnection()

    ensure_company_for_business(
        connection,
        {
            "id": "business-1",
            "name": "Школа",
            "geo_lat": 59.938297,
            "geo_lon": 30.36303,
            "geo": {"lat": 59.938297, "lon": 30.36303},
        },
    )

    params = _location_insert_params(connection)
    assert params[6:8] == (59.938297, 30.36303)


@pytest.mark.parametrize(
    "lead",
    [
        {"lat": 59.936056, "lon": 30.310439},
        {"raw_payload_json": {"latitude": 59.932847, "longitude": 30.321662}},
    ],
)
def test_lead_registry_uses_saved_and_raw_coordinates(lead):
    connection = RecordingConnection()

    ensure_company_for_lead(
        connection,
        "lead-1",
        {"id": "lead-1", "name": "Студия", **lead},
    )

    params = _location_insert_params(connection)
    assert params[5] is not None
    assert params[6] is not None


def test_existing_registry_location_is_enriched_after_parse():
    connection = RecordingConnection(linked_lead=True)

    ensure_company_for_lead(
        connection,
        "lead-1",
        {
            "id": "lead-1",
            "name": "Студия",
            "raw_payload_json": {"latitude": 59.928156, "longitude": 30.312262},
        },
    )

    coordinate_updates = [
        (query, params)
        for query, params in connection.cursor_instance.calls
        if "UPDATE company_locations" in query and "latitude" in query and "longitude" in query
    ]
    assert coordinate_updates, "existing company location must receive newly parsed coordinates"
