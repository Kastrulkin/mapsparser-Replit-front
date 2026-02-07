import pytest


def make_dummy_session():
    class DummySession:
        def __init__(self):
            self.page = object()
            self.context = object()

    return DummySession()


def test_orchestrator_parks_session_on_captcha(monkeypatch):
    """
    keep_open_on_captcha=True + captcha_detected →
    сессия паркуется, close_session не вызывается, есть captcha_session_id.
    """
    import parser_interception as pi

    registry = {}
    opened = {"called": False}
    closed = {"called": False}
    parked = {"session_id": None}

    dummy_session = make_dummy_session()

    class FakeManager:
        def open_session(self, **kwargs):
            opened["called"] = True
            return dummy_session

        def close_session(self, session):
            closed["called"] = True

        def park(self, reg, session):
            parked["session_id"] = "S1"
            reg["S1"] = session
            return "S1"

        def get(self, reg, session_id):
            return reg.get(session_id)

    def fake_parse(self, url, session):
        return {
            "error": "captcha_detected",
            "captcha_url": "https://captcha.test/",
        }

    monkeypatch.setattr(pi, "BrowserSessionManager", FakeManager)
    monkeypatch.setattr(pi.YandexMapsInterceptionParser, "parse_yandex_card", fake_parse)

    result = pi.parse_yandex_card(
        "https://yandex.ru/maps/org/123/",
        keep_open_on_captcha=True,
        session_registry=registry,
    )

    assert opened["called"] is True
    assert closed["called"] is False
    assert result["error"] == "captcha_detected"
    assert result["captcha_session_id"] == "S1"
    assert result["captcha_needs_human"] is True
    assert "S1" in registry


def test_orchestrator_closes_session_on_success(monkeypatch):
    """
    Успешный парсинг (без капчи) → сессия закрывается, registry не пополняется.
    """
    import parser_interception as pi

    registry = {}
    opened = {"called": False}
    closed = {"called": False}

    dummy_session = make_dummy_session()

    class FakeManager:
        def open_session(self, **kwargs):
            opened["called"] = True
            return dummy_session

        def close_session(self, session):
            closed["called"] = True

        def park(self, reg, session):
            raise AssertionError("park не должен вызываться при успехе")

        def get(self, reg, session_id):
            return reg.get(session_id)

    def fake_parse(self, url, session):
        return {
            "title": "OK",
            "address": "Addr",
        }

    monkeypatch.setattr(pi, "BrowserSessionManager", FakeManager)
    monkeypatch.setattr(pi.YandexMapsInterceptionParser, "parse_yandex_card", fake_parse)

    result = pi.parse_yandex_card(
        "https://yandex.ru/maps/org/123/",
        keep_open_on_captcha=False,
        session_registry=registry,
    )

    assert opened["called"] is True
    assert closed["called"] is True
    assert result.get("error") is None
    assert registry == {}


def test_orchestrator_handles_missing_session_on_resume(monkeypatch):
    """
    Если передан session_id, но в registry его нет →
    возвращается error='captcha_session_lost'.
    """
    import parser_interception as pi

    registry = {}

    class FakeManager:
        def open_session(self, **kwargs):
            raise AssertionError("open_session не должен вызываться при resume")

        def close_session(self, session):
            pass

        def park(self, reg, session):
            raise AssertionError("park не должен вызываться при captcha_session_lost")

        def get(self, reg, session_id):
            return None

    monkeypatch.setattr(pi, "BrowserSessionManager", FakeManager)

    result = pi.parse_yandex_card(
        "https://yandex.ru/maps/org/123/",
        keep_open_on_captcha=False,
        session_registry=registry,
        session_id="missing-session",
    )

    assert result["error"] == "captcha_session_lost"
    assert result["captcha_session_id"] == "missing-session"

