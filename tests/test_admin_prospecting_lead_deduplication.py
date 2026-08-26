from flask import Flask

from api import admin_prospecting
from services import lead_workstream_service


PUDRA_COMPANY_ID = "b2c6f76f-9623-4f99-9c0a-cd875ae0bc9a"
PUDRA_LOCATION_ID = "4c531a35-13be-4dab-937d-1dd67b1b76e6"
PUDRA_SOURCE_URL = "https://yandex.com/maps/org/pudra/164928086887/"


def _pudra_lead(lead_id, *, status, pipeline_status, created_at):
    return {
        "id": lead_id,
        "name": "Пудра",
        "category": "Салон красоты / ногтевая студия / косметология",
        "address": "Колпино",
        "source_url": PUDRA_SOURCE_URL,
        "source_external_id": "164928086887",
        "company_id": PUDRA_COMPANY_ID,
        "company_location_id": PUDRA_LOCATION_ID,
        "status": status,
        "pipeline_status": pipeline_status,
        "created_at": created_at,
    }


class _Database:
    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def get_all_leads_compact(self):
        return [
            _pudra_lead(
                "7a1ddd31-1167-4446-8926-48270ba796f4",
                status="sent",
                pipeline_status="contacted",
                created_at="2026-03-27T10:00:00Z",
            ),
            _pudra_lead(
                "6c4229fc-ee9c-49d2-a344-b70cbd016c00",
                status="deferred",
                pipeline_status="postponed",
                created_at="2026-04-14T10:00:00Z",
            ),
            _pudra_lead(
                "183a9d7e-dc85-43e5-a8c4-496e26f715bc",
                status="deferred",
                pipeline_status="postponed",
                created_at="2026-04-15T10:00:00Z",
            ),
            {
                "id": "a759b6a9-0f88-40cb-9497-26f6bd3df922",
                "name": "Эстем",
                "category": "Косметологическая клиника",
                "address": "Санкт-Петербург",
                "source_url": "https://yandex.com/maps/org/estem/158068320718/",
                "source_external_id": "158068320718",
                "company_id": "estem-company",
                "company_location_id": "estem-location",
                "status": "sent",
                "pipeline_status": "contacted",
                "created_at": "2026-08-04T08:04:54Z",
            },
        ]


class _Cursor:
    def execute(self, _query, _params=None):
        return None

    def fetchall(self):
        return []


class _Connection:
    def cursor(self, **_kwargs):
        return _Cursor()

    def close(self):
        return None


def test_admin_registry_collapses_exact_pudra_location_duplicates(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(admin_prospecting, "_require_superadmin", lambda: ({"user_id": "admin"}, None))
    monkeypatch.setattr(admin_prospecting, "DatabaseManager", _Database)
    monkeypatch.setattr(admin_prospecting, "get_db_connection", _Connection)
    monkeypatch.setattr(
        lead_workstream_service,
        "attach_workstreams",
        lambda _connection, leads: [dict(lead, workstreams=[]) for lead in leads],
    )

    with app.test_request_context("/api/admin/prospecting/leads?compact=1"):
        response = admin_prospecting.get_leads()

    payload = response.get_json()
    assert payload["count"] == 2
    assert [lead["id"] for lead in payload["leads"]] == [
        "7a1ddd31-1167-4446-8926-48270ba796f4",
        "a759b6a9-0f88-40cb-9497-26f6bd3df922",
    ]


def test_admin_registry_paginates_before_attaching_expensive_workstreams(monkeypatch):
    class PaginatedDatabase(_Database):
        def get_all_leads_compact(self):
            return [
                {
                    "id": f"lead-{index}",
                    "name": f"Company {index}",
                    "category": "Clinic",
                    "source": "apify_yandex",
                    "source_external_id": f"company-{index}",
                    "created_at": f"2026-08-{20 - index:02d}T10:00:00Z",
                }
                for index in range(1, 6)
            ]

    attached_lead_ids = []

    def attach_page(_connection, leads):
        attached_lead_ids.extend(lead["id"] for lead in leads)
        return [dict(lead, workstreams=[]) for lead in leads]

    app = Flask(__name__)
    monkeypatch.setattr(admin_prospecting, "_require_superadmin", lambda: ({"user_id": "admin"}, None))
    monkeypatch.setattr(admin_prospecting, "DatabaseManager", PaginatedDatabase)
    monkeypatch.setattr(admin_prospecting, "get_db_connection", _Connection)
    monkeypatch.setattr(lead_workstream_service, "attach_workstreams", attach_page)

    with app.test_request_context(
        "/api/admin/prospecting/leads?compact=1&page=2&page_size=2"
    ):
        response = admin_prospecting.get_leads()

    payload = response.get_json()
    assert attached_lead_ids == ["lead-3", "lead-4"]
    assert [lead["id"] for lead in payload["leads"]] == ["lead-3", "lead-4"]
    assert payload["count"] == 2
    assert payload["total"] == 5
    assert payload["page"] == 2
    assert payload["page_size"] == 2
    assert payload["total_pages"] == 3


def test_admin_registry_prefilters_workstream_scope_before_pagination(monkeypatch):
    class ScopedDatabase(_Database):
        def get_all_leads_compact(self):
            return [
                {
                    "id": f"lead-{index}",
                    "name": f"Company {index}",
                    "category": "Clinic",
                    "source": "apify_yandex",
                    "source_external_id": f"company-{index}",
                    "created_at": f"2026-08-{20 - index:02d}T10:00:00Z",
                }
                for index in range(1, 6)
            ]

    class ScopeCursor(_Cursor):
        def __init__(self):
            self.query = ""

        def execute(self, query, _params=None):
            self.query = query

        def fetchall(self):
            if "ws.lead_id::text AS lead_id" in self.query:
                return [{"lead_id": "lead-2"}, {"lead_id": "lead-4"}, {"lead_id": "lead-5"}]
            return []

    class ScopeConnection(_Connection):
        def cursor(self, **_kwargs):
            return ScopeCursor()

    attached_lead_ids = []

    def attach_page(_connection, leads):
        attached_lead_ids.extend(lead["id"] for lead in leads)
        return [dict(lead, workstreams=[{"workstream_type": "localos_sales"}]) for lead in leads]

    app = Flask(__name__)
    monkeypatch.setattr(admin_prospecting, "_require_superadmin", lambda: ({"user_id": "admin"}, None))
    monkeypatch.setattr(admin_prospecting, "DatabaseManager", ScopedDatabase)
    monkeypatch.setattr(admin_prospecting, "get_db_connection", ScopeConnection)
    monkeypatch.setattr(lead_workstream_service, "attach_workstreams", attach_page)

    with app.test_request_context(
        "/api/admin/prospecting/leads?compact=1&page=1&page_size=2&workstream_type=localos_sales"
    ):
        response = admin_prospecting.get_leads()

    payload = response.get_json()
    assert attached_lead_ids == ["lead-2", "lead-4"]
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
