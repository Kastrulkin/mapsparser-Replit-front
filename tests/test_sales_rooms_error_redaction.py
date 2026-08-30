from flask import Flask
import pytest

from api import sales_rooms_api


def _failing_connection():
    raise RuntimeError("postgresql://public-room:private-password@database/internal")


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("get", "/api/sales-rooms/public/example-room", None),
        (
            "post",
            "/api/sales-rooms/public/example-room/participants",
            {
                "email": "participant@example.com",
                "personal_data_consent": True,
            },
        ),
    ],
)
def test_public_sales_room_internal_errors_are_redacted(monkeypatch, method, path, json):
    app = Flask(__name__)
    app.register_blueprint(sales_rooms_api.sales_rooms_bp)
    monkeypatch.setattr(sales_rooms_api, "get_db_connection", _failing_connection)

    response = getattr(app.test_client(), method)(
        path,
        json=json,
        headers={"X-Request-ID": "sales-room-redaction"},
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "code": "internal_error",
        "message": "Не удалось обработать запрос к комнате",
        "request_id": "sales-room-redaction",
    }
    assert "private-password" not in response.get_data(as_text=True)
