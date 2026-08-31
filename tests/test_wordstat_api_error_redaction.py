from flask import Flask

from api import wordstat_api


INTERNAL_ERROR = "postgresql://private-user:private-password@database/internal"


class _Cursor:
    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return {"t": "wordstatkeywords"}


class _Connection:
    def __init__(self):
        self.row_factory = None
        self.closed = False
        self.rolled_back = False

    def cursor(self):
        return _Cursor()

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _app():
    app = Flask(__name__)
    app.register_blueprint(wordstat_api.wordstat_bp)
    return app


def _authorize(monkeypatch):
    monkeypatch.setattr(
        wordstat_api,
        "verify_session",
        lambda _token: {"user_id": "owner-1", "is_superadmin": False},
    )
    monkeypatch.setattr(wordstat_api, "_ensure_business_access", lambda *_args: None)


def _assert_redacted(response, request_id, message):
    assert response.status_code == 500
    assert response.get_json() == {
        "code": "internal_error",
        "message": message,
        "request_id": request_id,
    }
    assert "private-password" not in response.get_data(as_text=True)
    assert INTERNAL_ERROR not in response.get_data(as_text=True)


def test_keywords_internal_error_is_redacted(monkeypatch):
    connection = _Connection()
    _authorize(monkeypatch)
    monkeypatch.setattr(wordstat_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(
        wordstat_api,
        "collect_ranked_keywords",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(INTERNAL_ERROR)),
    )

    response = _app().test_client().get(
        "/api/wordstat/keywords?business_id=business-1",
        headers={
            "Authorization": "Bearer session-token",
            "X-Request-ID": "wordstat-keywords-redaction",
        },
    )

    _assert_redacted(
        response,
        "wordstat-keywords-redaction",
        "Не удалось получить SEO-ключи",
    )
    assert connection.closed is True


def test_search_internal_error_is_redacted(monkeypatch):
    connection = _Connection()
    _authorize(monkeypatch)
    monkeypatch.setattr(wordstat_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(
        wordstat_api,
        "_ensure_excluded_table",
        lambda _cursor: (_ for _ in ()).throw(RuntimeError(INTERNAL_ERROR)),
    )

    response = _app().test_client().get(
        "/api/wordstat/search?business_id=business-1&q=стрижка",
        headers={
            "Authorization": "Bearer session-token",
            "X-Request-ID": "wordstat-search-redaction",
        },
    )

    _assert_redacted(
        response,
        "wordstat-search-redaction",
        "Не удалось выполнить поиск SEO-ключей",
    )
    assert connection.rolled_back is True
    assert connection.closed is True


def test_metadata_internal_error_is_redacted(monkeypatch):
    monkeypatch.setattr(wordstat_api.os.path, "exists", lambda _path: True)

    def fail_open(*_args, **_kwargs):
        raise RuntimeError(INTERNAL_ERROR)

    monkeypatch.setattr("builtins.open", fail_open)

    response = _app().test_client().get(
        "/api/wordstat/metadata",
        headers={"X-Request-ID": "wordstat-metadata-redaction"},
    )

    _assert_redacted(
        response,
        "wordstat-metadata-redaction",
        "Не удалось получить метаданные SEO-ключей",
    )
