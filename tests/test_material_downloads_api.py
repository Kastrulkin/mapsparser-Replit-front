from pathlib import Path

from flask import Flask

from api import material_downloads_api


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows):
        self.cursor_value = FakeCursor(rows)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build_app():
    app = Flask(__name__)
    app.register_blueprint(material_downloads_api.material_downloads_bp)
    return app


def configure_material(monkeypatch, tmp_path):
    pdf_path = tmp_path / "checklist.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    monkeypatch.setitem(
        material_downloads_api.MATERIAL_DOWNLOADS,
        "checklist-audita-kartochki-kompanii",
        {"path": pdf_path, "download_name": "checklist.pdf", "mimetype": "application/pdf"},
    )
    monkeypatch.setenv("MATERIAL_DOWNLOAD_TOKEN_SECRET", "test-material-download-secret")
    return pdf_path


def test_download_request_requires_explicit_consent(monkeypatch, tmp_path):
    configure_material(monkeypatch, tmp_path)
    response = build_app().test_client().post(
        "/api/public/material-downloads",
        json={
            "email": "owner@example.com",
            "material_slug": "checklist-audita-kartochki-kompanii",
            "personal_data_consent": "true",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "consent_required"


def test_download_request_records_consent_and_returns_signed_link(monkeypatch, tmp_path):
    configure_material(monkeypatch, tmp_path)
    connection = FakeConnection([{"request_count": 0}])
    monkeypatch.setattr(material_downloads_api, "get_db_connection", lambda: connection)

    response = build_app().test_client().post(
        "/api/public/material-downloads",
        json={
            "email": " Owner@Example.com ",
            "material_slug": "checklist-audita-kartochki-kompanii",
            "personal_data_consent": True,
            "consent_version": "client-cannot-override-version",
            "source_language": "el",
        },
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["download_url"].startswith("/api/public/material-downloads/")
    assert payload["expires_in"] == 900
    assert connection.committed is True
    assert connection.closed is True
    insert_params = connection.cursor_value.queries[1][1]
    assert insert_params[1] == "owner@example.com"
    assert insert_params[3] == "el"
    assert insert_params[4] == material_downloads_api.CONSENT_VERSION
    assert insert_params[5] == "192.0.2.10"


def test_signed_download_serves_xlsx_after_consent(monkeypatch, tmp_path):
    xlsx_path = tmp_path / "local-marketing-control.xlsx"
    xlsx_path.write_bytes(b"PK\x03\x04xlsx")
    monkeypatch.setitem(
        material_downloads_api.MATERIAL_DOWNLOADS,
        "tablica-kontrolya-lokalnogo-marketinga",
        {
            "path": xlsx_path,
            "download_name": "localos-tablica-kontrolya-lokalnogo-marketinga.xlsx",
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    monkeypatch.setenv("MATERIAL_DOWNLOAD_TOKEN_SECRET", "test-material-download-secret")
    connection = FakeConnection([{"id": "4fef1143-e2ea-40ea-8acd-816a16e1b8a8"}])
    monkeypatch.setattr(material_downloads_api, "get_db_connection", lambda: connection)
    token = material_downloads_api._download_serializer().dumps(
        {"request_id": "4fef1143-e2ea-40ea-8acd-816a16e1b8a8", "material_slug": "tablica-kontrolya-lokalnogo-marketinga"}
    )

    response = build_app().test_client().get(f"/api/public/material-downloads/{token}")

    assert response.status_code == 200
    assert response.data == xlsx_path.read_bytes()
    assert response.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "localos-tablica-kontrolya-lokalnogo-marketinga.xlsx" in response.headers["Content-Disposition"]


def test_signed_download_requires_saved_consent(monkeypatch, tmp_path):
    configure_material(monkeypatch, tmp_path)
    connection = FakeConnection([None])
    monkeypatch.setattr(material_downloads_api, "get_db_connection", lambda: connection)
    token = material_downloads_api._download_serializer().dumps(
        {"request_id": "4fef1143-e2ea-40ea-8acd-816a16e1b8a8", "material_slug": "checklist-audita-kartochki-kompanii"}
    )

    response = build_app().test_client().get(f"/api/public/material-downloads/{token}")

    assert response.status_code == 403
    assert connection.committed is False
    assert connection.closed is True


def test_signed_download_serves_pdf_after_consent(monkeypatch, tmp_path):
    pdf_path = configure_material(monkeypatch, tmp_path)
    connection = FakeConnection([{"id": "4fef1143-e2ea-40ea-8acd-816a16e1b8a8"}])
    monkeypatch.setattr(material_downloads_api, "get_db_connection", lambda: connection)
    token = material_downloads_api._download_serializer().dumps(
        {"request_id": "4fef1143-e2ea-40ea-8acd-816a16e1b8a8", "material_slug": "checklist-audita-kartochki-kompanii"}
    )

    response = build_app().test_client().get(f"/api/public/material-downloads/{token}")

    assert response.status_code == 200
    assert response.data == pdf_path.read_bytes()
    assert response.headers["Content-Type"] == "application/pdf"
    assert "attachment" in response.headers["Content-Disposition"]
    assert connection.committed is True
    assert connection.closed is True
