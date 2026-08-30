import pytest
from flask import Flask

from api import admin_prospecting
from services import partnership_leads_service

admin_prospecting._bind_runtime_namespace()


@pytest.fixture
def app():
    return Flask(__name__)


def assert_safe_internal_error(app, handler, leaked_detail):
    with app.test_request_context("/?business_id=business-1"):
        response, status = handler()

    payload = response.get_json()
    assert status == 500
    assert payload["code"] == "internal_error"
    assert payload["request_id"]
    assert leaked_detail not in str(payload)


def test_partnership_lead_errors_do_not_leak_database_details(app, monkeypatch):
    leaked_detail = 'operator does not exist: text = uuid LINE 42 secret'
    monkeypatch.setattr(partnership_leads_service, "_require_auth", lambda: ({"user_id": "owner-1"}, None))
    monkeypatch.setattr(
        partnership_leads_service,
        "get_db_connection",
        lambda: (_ for _ in ()).throw(RuntimeError(leaked_detail)),
    )

    assert_safe_internal_error(app, partnership_leads_service.partnership_list_leads, leaked_detail)


@pytest.mark.parametrize("handler_name", ["partnership_blockers_summary", "partnership_ralph_loop_summary"])
def test_partnership_summary_errors_do_not_leak_database_details(app, monkeypatch, handler_name):
    leaked_detail = 'operator does not exist: text = uuid LINE 42 secret'
    handler = admin_prospecting._IMPLEMENTATIONS[handler_name]
    monkeypatch.setitem(handler.__globals__, "_require_auth", lambda: ({"user_id": "owner-1"}, None))
    monkeypatch.setitem(
        handler.__globals__,
        "get_db_connection",
        lambda: (_ for _ in ()).throw(RuntimeError(leaked_detail)),
    )

    assert_safe_internal_error(app, handler, leaked_detail)
