from flask import Flask
import pytest

from api import progress_api


def _failing_database_manager():
    raise RuntimeError("postgresql://private-user:private-password@database/internal")


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/api/business/business-1/progress", "Не удалось получить прогресс бизнеса"),
        ("/api/business/business-1/card-audit", "Не удалось получить аудит карточки"),
        ("/api/business/business-1/public-audit-links", "Не удалось получить ссылки на аудит"),
    ],
)
def test_progress_internal_error_is_redacted(monkeypatch, path, message):
    app = Flask(__name__)
    app.register_blueprint(progress_api.progress_bp)
    monkeypatch.setattr(progress_api, "verify_session", lambda _token: {"id": "user-1"})
    monkeypatch.setattr(progress_api, "DatabaseManager", _failing_database_manager)

    response = app.test_client().get(
        path,
        headers={
            "Authorization": "Bearer session-token",
            "X-Request-ID": "progress-redaction",
        },
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "code": "internal_error",
        "message": message,
        "request_id": "progress-redaction",
    }
    assert "private-password" not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "path",
    [
        "/api/business/business-1/progress",
        "/api/business/business-1/card-audit",
    ],
)
def test_authenticated_progress_endpoints_require_maps_subscription(monkeypatch, path):
    class _Cursor:
        def execute(self, _query, _params=None):
            return None

        def fetchone(self):
            return {"id": "business-1"}

    class _Connection:
        def cursor(self):
            return _Cursor()

    class _Database:
        def __init__(self):
            self.conn = _Connection()

        def close(self):
            return None

    app = Flask(__name__)
    app.register_blueprint(progress_api.progress_bp)
    monkeypatch.setattr(progress_api, "verify_session", lambda _token: {"id": "user-1"})
    monkeypatch.setattr(progress_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(progress_api, "DatabaseManager", _Database)
    monkeypatch.setattr(
        progress_api,
        "get_capability_access",
        lambda *_args, **_kwargs: {
            "allowed": False,
            "capability": "progress",
            "code": "payment_required",
            "required_tier": "starter",
        },
        raising=False,
    )
    monkeypatch.setattr(
        progress_api,
        "calculate_business_progress",
        lambda *_args: (_ for _ in ()).throw(AssertionError("locked progress must not be calculated")),
    )
    monkeypatch.setattr(
        progress_api,
        "build_card_audit_snapshot",
        lambda *_args: (_ for _ in ()).throw(AssertionError("locked audit must not be calculated")),
    )

    response = app.test_client().get(path, headers={"Authorization": "Bearer session-token"})

    assert response.status_code == 402
    assert response.get_json()["code"] == "payment_required"
