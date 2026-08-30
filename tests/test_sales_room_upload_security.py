import io

from flask import Flask
import pytest

from api import sales_rooms_api


class _SalesRoomCursor:
    def execute(self, _query, _params=None):
        return None


class _SalesRoomConnection:
    def __init__(self):
        self.committed = False

    def cursor(self, **_kwargs):
        return _SalesRoomCursor()

    def commit(self):
        self.committed = True

    def close(self):
        return None


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("photo.jpg", "image/jpeg"),
        ("document.pdf", "application/pdf"),
    ],
)
def test_public_sales_room_rejects_file_with_fake_signature(monkeypatch, filename, mime_type):
    app = Flask(__name__)
    app.register_blueprint(sales_rooms_api.sales_rooms_bp)
    connection = _SalesRoomConnection()
    storage_calls = []

    monkeypatch.setattr(sales_rooms_api, "_check_public_sales_room_rate_limit", lambda *_args: None)
    monkeypatch.setattr(sales_rooms_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(sales_rooms_api, "_ensure_sales_room_tables", lambda _connection: None)
    monkeypatch.setattr(
        sales_rooms_api,
        "_load_sales_room_by_slug",
        lambda _cursor, _slug: {"id": "room-1", "slug": "example-room"},
    )
    monkeypatch.setattr(sales_rooms_api, "_record_sales_room_event", lambda *_args, **_kwargs: None)

    def record_storage(**kwargs):
        storage_calls.append(kwargs)
        return {"storage_path": "/tmp/fake-upload"}

    monkeypatch.setattr(sales_rooms_api, "store_sales_room_file", record_storage)

    response = app.test_client().post(
        "/api/sales-rooms/public/example-room/files",
        data={"file": (io.BytesIO(b"<html>not the declared file type</html>"), filename, mime_type)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "File content does not match its type"}
    assert storage_calls == []
    assert connection.committed is False
