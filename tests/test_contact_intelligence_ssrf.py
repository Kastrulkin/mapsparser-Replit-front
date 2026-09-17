import socket

from core import outbound_network
from services import contact_intelligence_service
import pytest


def test_contact_collection_uses_pinned_fetch_instead_of_hostname_request(monkeypatch):
    requested = []
    monkeypatch.setattr(contact_intelligence_service, "_public_http_url", lambda value: str(value))
    monkeypatch.setattr(
        contact_intelligence_service.outbound_network,
        "public_pinned_get",
        lambda value, **_kwargs: requested.append(value) or outbound_network.OutboundHttpFetchResponse(
            status_code=200,
            headers={"content-type": "text/html"},
            body=b"<html></html>",
        ),
    )
    monkeypatch.setattr(
        contact_intelligence_service.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _item in ()).throw(AssertionError("hostname request is not pinned")),
    )

    contacts, warnings = contact_intelligence_service.collect_public_website_contacts("http://rebind.invalid")

    assert contacts == []
    assert warnings == []
    assert requested == ["http://rebind.invalid"]


def test_pinned_fetch_connects_to_validated_ip_not_rebound_hostname(monkeypatch):
    captured = {}

    class Response:
        status = 200
        headers = {"content-type": "text/html"}

        def read(self, _limit):
            return b""

        def release_conn(self):
            return None

    class Pool:
        def __init__(self, host, **_kwargs):
            captured["host"] = host

        def urlopen(self, *_args, **_kwargs):
            return Response()

        def close(self):
            return None

    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
    )
    monkeypatch.setattr(outbound_network.urllib3, "HTTPConnectionPool", Pool)

    response = outbound_network.public_pinned_get("http://rebind.invalid/path", headers={})

    assert response.status_code == 200
    assert captured["host"] == "93.184.216.34"


@pytest.mark.parametrize("address", ["127.0.0.1", "::1", "fe80::1", "fc00::1"])
def test_pinned_fetch_rejects_non_public_dns_answers(monkeypatch, address):
    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))],
    )

    with pytest.raises(ValueError):
        outbound_network.public_pinned_get("http://rebind.invalid", headers={})


def test_pinned_fetch_rejects_mixed_public_and_private_dns(monkeypatch):
    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
        ],
    )

    with pytest.raises(ValueError):
        outbound_network.public_pinned_get("http://rebind.invalid", headers={})


def test_pinned_fetch_rechecks_dns_and_rejects_rebinding(monkeypatch):
    calls = []

    def resolving(*_args, **_kwargs):
        calls.append(True)
        address = "93.184.216.34" if len(calls) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))]

    monkeypatch.setattr(outbound_network.socket, "getaddrinfo", resolving)

    with pytest.raises(ValueError):
        outbound_network.public_pinned_get("http://rebind.invalid", headers={})
    assert len(calls) == 2


def test_collector_skips_second_resolver_failure(monkeypatch):
    calls = []

    def resolving(*_args, **_kwargs):
        calls.append(True)
        if len(calls) == 1:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]
        raise OSError("rebind lookup failed")

    monkeypatch.setattr(contact_intelligence_service.socket, "getaddrinfo", resolving)

    contacts, warnings = contact_intelligence_service.collect_public_website_contacts("http://rebind.invalid")

    assert contacts == []
    assert warnings == ["Не удалось проверить http://rebind.invalid"]
    assert len(calls) == 2


def test_https_pinned_fetch_uses_ip_with_original_host_sni(monkeypatch):
    captured = {}

    class Response:
        status = 200
        headers = {}

        def read(self, _limit):
            return b""

        def release_conn(self):
            return None

    class Pool:
        def __init__(self, host, **kwargs):
            captured["host"] = host
            captured.update(kwargs)

        def urlopen(self, *_args, **_kwargs):
            return Response()

        def close(self):
            return None

    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    monkeypatch.setattr(outbound_network.urllib3, "HTTPSConnectionPool", Pool)

    outbound_network.public_pinned_get("https://rebind.invalid/path", headers={})

    assert captured["host"] == "93.184.216.34"
    assert captured["assert_hostname"] == "rebind.invalid"
    assert captured["server_hostname"] == "rebind.invalid"


def test_ipv6_pinned_fetch_brackets_host_header(monkeypatch):
    captured = {}

    class Response:
        status = 200
        headers = {}

        def read(self, _limit):
            return b""

        def release_conn(self):
            return None

    class Pool:
        def __init__(self, host, **kwargs):
            captured["host"] = host
            captured.update(kwargs)

        def urlopen(self, _method, _path, **kwargs):
            captured["headers"] = kwargs["headers"]
            return Response()

        def close(self):
            return None

    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 8443, 0, 0))
        ],
    )
    monkeypatch.setattr(outbound_network.urllib3, "HTTPSConnectionPool", Pool)

    outbound_network.public_pinned_get("https://[2001:4860:4860::8888]:8443/path", headers={})

    assert captured["host"] == "2001:4860:4860::8888"
    assert captured["headers"]["Host"] == "[2001:4860:4860::8888]:8443"
    assert captured["server_hostname"] == "2001:4860:4860::8888"


def test_pinned_fetch_obeys_size_cap_and_releases_pool_on_read_error(monkeypatch):
    captured = {"released": False, "closed": False}

    class Response:
        status = 200
        headers = {}

        def read(self, limit):
            captured["limit"] = limit
            raise TimeoutError("read failure")

        def release_conn(self):
            captured["released"] = True

    class Pool:
        def __init__(self, *_args, **_kwargs):
            return None

        def urlopen(self, *_args, **_kwargs):
            return Response()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
    )
    monkeypatch.setattr(outbound_network.urllib3, "HTTPConnectionPool", Pool)

    with pytest.raises(TimeoutError):
        outbound_network.public_pinned_get("http://rebind.invalid", headers={}, max_bytes=123)
    assert captured["limit"] == 123
    assert captured["released"] is True
    assert captured["closed"] is True


def test_collector_skips_private_redirect_and_keeps_declared_charset(monkeypatch):
    requested = []
    responses = [
        outbound_network.OutboundHttpFetchResponse(
            status_code=302,
            headers={"location": "http://private.invalid"},
            body=b"",
        )
    ]
    monkeypatch.setattr(
        contact_intelligence_service,
        "_public_http_url",
        lambda value: "http://public.invalid" if str(value) == "http://public.invalid" else None,
    )
    monkeypatch.setattr(
        contact_intelligence_service.outbound_network,
        "public_pinned_get",
        lambda value, **_kwargs: requested.append(value) or responses.pop(0),
    )

    contacts, warnings = contact_intelligence_service.collect_public_website_contacts("http://public.invalid")

    assert contacts == []
    assert warnings == []
    assert requested == ["http://public.invalid"]
    assert contact_intelligence_service._decode_website_html("Привет".encode("cp1251"), "text/html; charset=cp1251") == "Привет"
    assert contact_intelligence_service._decode_website_html(b"hello", "text/html; charset=unknown") == "hello"
