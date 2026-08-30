from flask import Flask
import pytest

from api import content_voice_api


def _raise_provider_secret(*_args, **_kwargs):
    raise RuntimeError("provider-token=private-content-secret")


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("get", "/api/content-voice?business_id=business-1", None),
        ("post", "/api/content-voice/examples", {"business_id": "business-1", "text": "Example"}),
        ("delete", "/api/content-voice/examples/example-1", None),
    ],
)
def test_content_voice_internal_errors_are_redacted(monkeypatch, method, path, json):
    app = Flask(__name__)
    app.register_blueprint(content_voice_api.content_voice_bp)
    monkeypatch.setattr(content_voice_api, "verify_session", lambda _token: {"user_id": "user-1"})
    monkeypatch.setattr(content_voice_api, "get_content_voice", _raise_provider_secret)
    monkeypatch.setattr(content_voice_api, "add_content_voice_example", _raise_provider_secret)
    monkeypatch.setattr(content_voice_api, "delete_content_voice_example", _raise_provider_secret)

    response = getattr(app.test_client(), method)(
        path,
        json=json,
        headers={
            "Authorization": "Bearer session-token",
            "X-Request-ID": "content-voice-redaction",
        },
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "code": "internal_error",
        "message": "Не удалось обработать настройки стиля",
        "request_id": "content-voice-redaction",
    }
    assert "private-content-secret" not in response.get_data(as_text=True)
