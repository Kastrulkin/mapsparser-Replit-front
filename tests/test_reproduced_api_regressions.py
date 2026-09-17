import io
import json

from flask import Flask

from api import finance_api, metrics_history_api, operator_api


class PreviewCursor:
    def __init__(self):
        self.params = None

    def execute(self, _query, params=None):
        self.params = params


def test_finance_crm_preview_uses_timezone_aware_expiration(monkeypatch):
    cursor = PreviewCursor()
    monkeypatch.setattr(
        finance_api,
        "_load_finance_crm_connection",
        lambda *_args: {"settings_json": {}},
    )

    finance_api._store_finance_crm_preview(
        cursor,
        "business-1",
        "yclients",
        {
            "preview_token": "preview-1",
            "period": {"start_date": "2026-09-01", "end_date": "2026-09-17"},
            "rows_total": 1,
            "valid_rows": 1,
            "failed_rows": 0,
            "errors": [],
        },
    )

    settings = json.loads(cursor.params[0])
    assert settings["last_preview"]["created_at"].endswith("+00:00")
    assert settings["last_preview"]["expires_at"].endswith("+00:00")


def _upload_request(app, field_name, filename, content_type, data):
    return app.test_request_context(
        "/api/finance/transaction/upload",
        method="POST",
        headers={"Authorization": "Bearer valid"},
        data={field_name: (io.BytesIO(data), filename, content_type)},
    )


def test_finance_transaction_text_upload_reaches_text_analyzer(monkeypatch):
    app = Flask(__name__)
    calls = []
    monkeypatch.setattr(finance_api, "verify_session", lambda _token: {"user_id": "user-1"})
    monkeypatch.setattr(finance_api, "get_business_id_from_user", lambda _user_id: "business-1")
    monkeypatch.setattr(
        finance_api,
        "analyze_text_with_gigachat",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"error": "analyzer-sentinel"},
    )

    with _upload_request(app, "file", "transactions.csv", "text/csv", b"date,amount\n2026-09-17,100"):
        response, status = finance_api.upload_transaction_file()

    assert status == 500
    assert response.get_json() == {"error": "analyzer-sentinel"}
    assert calls[0][1] == {"business_id": "business-1", "user_id": "user-1"}


def test_finance_transaction_image_upload_reaches_image_analyzer(monkeypatch):
    app = Flask(__name__)
    calls = []
    monkeypatch.setattr(finance_api, "verify_session", lambda _token: {"user_id": "user-1"})
    monkeypatch.setattr(finance_api, "get_business_id_from_user", lambda _user_id: "business-1")
    monkeypatch.setattr(
        finance_api,
        "analyze_screenshot_with_gigachat",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"error": "image-analyzer-sentinel"},
    )

    with _upload_request(app, "photo", "transactions.png", "image/png", b"fake-png"):
        response, status = finance_api.upload_transaction_file()

    assert status == 500
    assert response.get_json() == {"error": "image-analyzer-sentinel"}
    assert calls[0][1] == {"business_id": "business-1", "user_id": "user-1"}


def test_manual_metric_routes_use_request_auth_helper(monkeypatch):
    app = Flask(__name__)
    calls = []
    monkeypatch.setattr(
        metrics_history_api,
        "require_auth_from_request",
        lambda: calls.append("auth") or None,
    )

    with app.test_request_context(
        "/api/business/business-1/metrics-history",
        method="POST",
        json={"date": "2026-09-17"},
    ):
        add_response, add_status = metrics_history_api.add_manual_metric("business-1")
    with app.test_request_context(
        "/api/business/business-1/metrics-history/metric-1",
        method="DELETE",
    ):
        delete_response, delete_status = metrics_history_api.delete_manual_metric("business-1", "metric-1")

    assert add_status == 401
    assert delete_status == 401
    assert add_response.get_json()["error"] == "Требуется авторизация"
    assert delete_response.get_json()["error"] == "Требуется авторизация"
    assert calls == ["auth", "auth"]


class FailingOperatorConnection:
    def __init__(self):
        self.rolled_back = False

    def cursor(self):
        return object()

    def rollback(self):
        self.rolled_back = True


class FailingOperatorDatabase:
    instances = []

    def __init__(self):
        self.conn = FailingOperatorConnection()
        self.closed = False
        self.instances.append(self)

    def close(self):
        self.closed = True


def test_operator_inbox_returns_structured_error_when_builder_fails(monkeypatch):
    app = Flask(__name__)
    FailingOperatorDatabase.instances.clear()
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", FailingOperatorDatabase)
    monkeypatch.setattr(operator_api, "verify_business_access", lambda *_args: (True, "owner-1"))
    monkeypatch.setattr(
        operator_api,
        "build_operator_inbox",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("forced failure")),
    )

    with app.test_request_context("/operator/inbox?business_id=business-1"):
        response, status = operator_api.operator_inbox()

    body = response.get_json()
    database = FailingOperatorDatabase.instances[0]
    assert status == 500
    assert body["error_code"] == "operator_inbox_failed"
    assert body["error_id"]
    assert database.conn.rolled_back is True
    assert database.closed is True
