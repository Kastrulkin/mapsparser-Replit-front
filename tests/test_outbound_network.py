import urllib.request

from core import outbound_network
from core import telegram_network


def test_outbound_urlopen_uses_configured_http_proxy(monkeypatch):
    captured = {}

    class FakeOpener:
        def open(self, req, timeout=10):
            captured["request"] = req
            captured["timeout"] = timeout
            return "response"

    def fake_build_opener(handler):
        captured["handler"] = handler
        return FakeOpener()

    monkeypatch.setenv("OUTBOUND_HTTP_PROXY", "http://192.168.0.177:10809")
    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)

    result = outbound_network.outbound_urlopen("https://graph.facebook.com", timeout=12)

    assert result == "response"
    assert captured["request"] == "https://graph.facebook.com"
    assert captured["timeout"] == 12
    assert captured["handler"].proxies == {
        "http": "http://192.168.0.177:10809",
        "https": "http://192.168.0.177:10809",
    }


def test_telegram_http_proxy_falls_back_to_outbound_proxy(monkeypatch):
    monkeypatch.delenv("TELEGRAM_HTTP_PROXY", raising=False)
    monkeypatch.delenv("TELEGRAM_API_PROXY", raising=False)
    monkeypatch.setenv("OUTBOUND_HTTP_PROXY", "http://192.168.0.177:10809")

    assert telegram_network.resolve_telegram_http_proxy() == "http://192.168.0.177:10809"
