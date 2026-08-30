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
