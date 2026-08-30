from flask import Flask
import pytest

from api import reports_api


CARD_ID = "d270e95c-4d1e-48b8-95f6-53479d9f9ca8"
BUSINESS_ID = "c2c7c2de-e02d-45e9-9886-4098a64a2fef"


class _Connection:
    def cursor(self):
        return object()

    def close(self):
        return None


def _app():
    app = Flask(__name__)
    app.register_blueprint(reports_api.reports_bp)
    return app


def _card(report_path):
    return {
        "id": CARD_ID,
        "business_id": BUSINESS_ID,
        "title": "Synthetic report",
        "seo_score": 73,
        "ai_analysis": "Synthetic analysis",
        "report_path": str(report_path),
    }


def _authorize(monkeypatch, allowed):
    monkeypatch.setattr(
        reports_api,
        "require_auth_from_request",
        lambda: {"user_id": "owner-1", "is_superadmin": False},
        raising=False,
    )
    monkeypatch.setattr(
        reports_api,
        "verify_business_access",
        lambda *_args: (allowed, "owner-1" if allowed else "foreign-owner"),
        raising=False,
    )
    monkeypatch.setattr(reports_api, "get_db_connection", _Connection)


@pytest.mark.parametrize(
    "route",
    (
        f"/api/download-report/{CARD_ID}",
        f"/api/view-report/{CARD_ID}",
        f"/api/reports/{CARD_ID}/status",
    ),
)
def test_report_routes_require_authentication(monkeypatch, tmp_path, route):
    report_path = tmp_path / "report.html"
    report_path.write_text("<h1>Synthetic report</h1>", encoding="utf-8")
    monkeypatch.setattr(reports_api, "_get_card", lambda _card_id: _card(report_path))
    monkeypatch.setattr(reports_api, "require_auth_from_request", lambda: None, raising=False)

    response = _app().test_client().get(route)

    assert response.status_code == 401
    assert response.get_json()["code"] == "authentication_required"


@pytest.mark.parametrize(
    "route",
    (
        f"/api/download-report/{CARD_ID}",
        f"/api/view-report/{CARD_ID}",
        f"/api/reports/{CARD_ID}/status",
    ),
)
def test_report_routes_reject_foreign_business(monkeypatch, tmp_path, route):
    report_path = tmp_path / "report.html"
    report_path.write_text("<h1>Synthetic report</h1>", encoding="utf-8")
    monkeypatch.setattr(reports_api, "_get_card", lambda _card_id: _card(report_path))
    _authorize(monkeypatch, allowed=False)

    response = _app().test_client().get(route, headers={"Authorization": "Bearer synthetic-token"})

    assert response.status_code == 403
    assert response.get_json()["code"] == "business_access_denied"


def test_report_status_does_not_expose_server_path(monkeypatch, tmp_path):
    report_path = tmp_path / "report.html"
    report_path.write_text("<h1>Synthetic report</h1>", encoding="utf-8")
    monkeypatch.setattr(reports_api, "_get_card", lambda _card_id: _card(report_path))
    _authorize(monkeypatch, allowed=True)

    response = _app().test_client().get(
        f"/api/reports/{CARD_ID}/status",
        headers={"Authorization": "Bearer synthetic-token"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["has_report"] is True
    assert "report_path" not in payload


def test_report_error_does_not_expose_exception_text(monkeypatch):
    _authorize(monkeypatch, allowed=True)
    monkeypatch.setattr(
        reports_api,
        "_get_card",
        lambda _card_id: (_ for _ in ()).throw(RuntimeError("database-password=do-not-leak")),
    )

    response = _app().test_client().get(
        f"/api/reports/{CARD_ID}/status",
        headers={"Authorization": "Bearer synthetic-token"},
    )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["code"] == "internal_error"
    assert "database-password" not in response.get_data(as_text=True)
