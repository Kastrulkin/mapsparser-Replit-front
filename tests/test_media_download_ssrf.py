import pytest

from core import outbound_network
from services import ai_runtime


class _RedirectedResponse:
    def __init__(self, url="http://169.254.169.254/latest/meta-data"):
        self.closed = False
        self.url = url

    def geturl(self):
        return self.url

    def read(self, _limit):
        return b"private-metadata"

    def close(self):
        self.closed = True


def test_image_download_rejects_loopback_before_network_call(monkeypatch):
    opener_calls = []

    def record_build_opener(*_handlers):
        opener_calls.append(True)
        raise AssertionError("loopback network request was attempted")

    monkeypatch.setattr(outbound_network.urllib_request, "build_opener", record_build_opener)

    with pytest.raises(ValueError, match="публичн"):
        ai_runtime._download_image_as_base64("http://127.0.0.1:8000/internal")

    assert opener_calls == []


def test_image_download_rejects_redirect_to_link_local(monkeypatch):
    response = _RedirectedResponse()

    def public_dns(hostname, port, type):
        if hostname == "169.254.169.254":
            return [(2, 1, 6, "", ("169.254.169.254", port))]
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    class _Opener:
        def open(self, _request, timeout):
            return response

    monkeypatch.setattr(outbound_network.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(outbound_network.urllib_request, "build_opener", lambda *_handlers: _Opener())

    with pytest.raises(ValueError, match="публичн"):
        ai_runtime._download_image_as_base64("https://images.example.test/photo.jpg")

    assert response.closed is True


def test_public_image_download_keeps_outbound_proxy(monkeypatch):
    captured = {}
    response = _RedirectedResponse("https://images.example.test/photo.jpg")

    class _Opener:
        def open(self, request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return response

    def build_opener(*handlers):
        captured["handlers"] = handlers
        return _Opener()

    monkeypatch.setenv("OUTBOUND_HTTP_PROXY", "http://192.168.0.177:10809")
    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda _hostname, port, type: [(2, 1, 6, "", ("93.184.216.34", port))],
    )
    monkeypatch.setattr(outbound_network.urllib_request, "build_opener", build_opener)

    request = ai_runtime.urllib.request.Request("https://images.example.test/photo.jpg")
    result = outbound_network.public_outbound_urlopen(request, timeout=12)

    assert result is response
    assert captured["request"] is request
    assert captured["timeout"] == 12
    assert captured["handlers"][0].proxies == {
        "http": "http://192.168.0.177:10809",
        "https": "http://192.168.0.177:10809",
    }
    assert isinstance(captured["handlers"][1], outbound_network._PublicRedirectHandler)
