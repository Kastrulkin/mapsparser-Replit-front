from flask import Flask

from core.cors_policy import configure_cors, resolve_allowed_origins


def test_production_cors_excludes_loopback_origins(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://localos.pro,http://localhost:3000,http://127.0.0.1:3000,http://[::1]:3000",
    )

    assert resolve_allowed_origins() == ["https://localos.pro"]


def test_development_cors_keeps_loopback_origins(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )

    assert resolve_allowed_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_cors_does_not_advertise_an_origin_when_request_has_none(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://localos.pro")
    app = Flask(__name__)
    configure_cors(app)

    response = app.test_client().get("/")

    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_reflects_only_an_allowed_request_origin(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://localos.pro")
    app = Flask(__name__)
    configure_cors(app)

    allowed_response = app.test_client().get(
        "/",
        headers={"Origin": "https://localos.pro"},
    )
    denied_response = app.test_client().get(
        "/",
        headers={"Origin": "https://evil.example"},
    )

    assert allowed_response.headers.get("Access-Control-Allow-Origin") == "https://localos.pro"
    assert "Access-Control-Allow-Origin" not in denied_response.headers
