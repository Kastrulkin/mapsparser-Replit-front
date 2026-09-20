import socket

import pytest
import requests

from core import outbound_network
from services import content_plan_service


PUBLIC_IP = "93.184.216.34"


class _Response:
    def __init__(self, status, headers=None, body=b""):
        self.status = status
        self.headers = headers or {}
        self.body = body
        self.read_limits = []
        self.released = False

    def read(self, limit):
        self.read_limits.append(limit)
        return self.body

    def release_conn(self):
        self.released = True


def _pinned_transport(monkeypatch, responses, addresses=None):
    observed = {"pools": [], "requests": [], "dns": []}
    address_map = addresses or {}

    def resolving(hostname, port, *_args, **_kwargs):
        observed["dns"].append((hostname, port))
        values = address_map.get(hostname, [PUBLIC_IP])
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
            for address in values
        ]

    class Pool:
        def __init__(self, host, **kwargs):
            observed["pools"].append({"host": host, **kwargs})

        def urlopen(self, method, path, **kwargs):
            observed["requests"].append({"method": method, "path": path, **kwargs})
            if not responses:
                raise AssertionError("unexpected pinned request")
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        def close(self):
            return None

    monkeypatch.setattr(outbound_network.socket, "getaddrinfo", resolving)
    monkeypatch.setattr(outbound_network.urllib3, "HTTPConnectionPool", Pool)
    monkeypatch.setattr(outbound_network.urllib3, "HTTPSConnectionPool", Pool)
    return observed


def _reject_legacy_requests(monkeypatch):
    calls = []

    def legacy_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("content-plan site reader must use a pinned connection")

    monkeypatch.setattr(requests, "get", legacy_get)
    return calls


@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("http://127.0.0.1/private", {"127.0.0.1": ["127.0.0.1"]}),
        ("http://[::1]/private", {"::1": ["::1"]}),
        ("http://169.254.169.254/latest", {"169.254.169.254": ["169.254.169.254"]}),
        ("http://private.invalid/", {"private.invalid": ["10.0.0.9"]}),
        ("http://mixed.invalid/", {"mixed.invalid": [PUBLIC_IP, "127.0.0.1"]}),
    ],
)
def test_content_plan_site_reader_rejects_private_and_mixed_destinations_before_transport(
    monkeypatch, url, addresses
):
    observed = _pinned_transport(monkeypatch, [], addresses)
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description(url) == ""
    assert legacy_calls == []
    assert observed["pools"] == []


@pytest.mark.parametrize("url", ["https://user:secret@public.invalid/", "ftp://public.invalid/", "file:///etc/hosts", "file:/etc/hosts"])
def test_content_plan_site_reader_rejects_credentials_and_non_http_urls_without_dns_or_transport(monkeypatch, url):
    observed = _pinned_transport(monkeypatch, [])
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description(url) == ""
    assert legacy_calls == []
    assert observed["dns"] == []
    assert observed["pools"] == []


def test_content_plan_site_reader_rechecks_dns_before_pinning(monkeypatch):
    observed = _pinned_transport(monkeypatch, [])
    legacy_calls = _reject_legacy_requests(monkeypatch)
    answers = [[PUBLIC_IP], ["127.0.0.1"]]

    def rebinding_dns(hostname, port, *_args, **_kwargs):
        observed["dns"].append((hostname, port))
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
            for address in answers.pop(0)
        ]

    monkeypatch.setattr(outbound_network.socket, "getaddrinfo", rebinding_dns)

    assert content_plan_service._fetch_site_description("http://rebind.invalid/") == ""
    assert legacy_calls == []
    assert len(observed["dns"]) == 2
    assert observed["pools"] == []


@pytest.mark.parametrize(
    ("url", "path", "host", "port"),
    [
        ("http://public.invalid/about", "/about", "public.invalid", 80),
        ("https://public.invalid/about", "/about", "public.invalid", 443),
        ("public.invalid", "/", "public.invalid", 443),
        ("public.invalid:8443", "/", "public.invalid:8443", 8443),
    ],
)
def test_content_plan_site_reader_extracts_public_html_via_pinned_transport(monkeypatch, url, path, host, port):
    response = _Response(
        200,
        {"content-type": "text/html; charset=utf-8"},
        b"<meta name='description' content='Public editorial context'>",
    )
    observed = _pinned_transport(monkeypatch, [response])
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description(url) == "Public editorial context"
    assert legacy_calls == []
    assert observed["pools"][0]["host"] == PUBLIC_IP
    request = observed["requests"][0]
    assert (request["method"], request["path"], request["headers"]["Host"]) == ("GET", path, host)
    assert request["headers"]["User-Agent"] == "LocalOSBot/1.0 (+https://localos.pro)"
    assert request["redirect"] is False
    assert observed["pools"][0]["port"] == port
    assert response.released is True
    assert response.read_limits == [1_000_001]
    if not url.startswith("http://"):
        assert observed["pools"][0]["assert_hostname"] == "public.invalid"
        assert observed["pools"][0]["server_hostname"] == "public.invalid"


def test_content_plan_site_reader_does_not_follow_private_redirect(monkeypatch):
    observed = _pinned_transport(
        monkeypatch,
        [_Response(302, {"location": "http://127.0.0.1/private"})],
        {"127.0.0.1": ["127.0.0.1"]},
    )
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description("http://public.invalid/start") == ""
    assert legacy_calls == []
    assert [item["path"] for item in observed["requests"]] == ["/start"]
    assert len(observed["pools"]) == 1


def test_content_plan_site_reader_handles_relative_redirect_and_bounds_redirect_loop(monkeypatch):
    success = _pinned_transport(
        monkeypatch,
        [
            _Response(302, {"location": "/about"}),
            _Response(200, {"content-type": "text/html"}, b"<title>Public title</title>"),
        ],
    )
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description("http://public.invalid/start") == "Public title"
    assert legacy_calls == []
    assert [item["path"] for item in success["requests"]] == ["/start", "/about"]

    loop = _pinned_transport(monkeypatch, [_Response(302, {"location": "/loop"})] * 4)
    assert content_plan_service._fetch_site_description("http://public.invalid/loop") == ""
    assert 1 <= len(loop["requests"]) <= 4


def test_content_plan_site_reader_bounds_unique_redirect_chain_to_five_requests(monkeypatch):
    redirects = [_Response(302, {"location": f"/hop-{index}"}) for index in range(1, 6)]
    observed = _pinned_transport(monkeypatch, redirects)
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description("http://public.invalid/start") == ""
    assert legacy_calls == []
    assert [item["path"] for item in observed["requests"]] == [
        "/start",
        "/hop-1",
        "/hop-2",
        "/hop-3",
        "/hop-4",
    ]


@pytest.mark.parametrize(
    ("content_type", "body", "expected"),
    [
        ("text/html; charset=cp1251", "<title>Описание салона</title>".encode("cp1251"), "Описание салона"),
        ("text/html; charset=unknown", b"<title>UTF-8 fallback</title>", "UTF-8 fallback"),
        (
            "text/html; charset=utf-8",
            "<meta charset='windows-1251'><title>Приоритет HTTP</title>".encode("utf-8"),
            "Приоритет HTTP",
        ),
        (
            "text/html",
            "<meta charset='windows-1251'><meta name='description' content='Описание страницы'>".encode("cp1251"),
            "Описание страницы",
        ),
    ],
)
def test_content_plan_site_reader_preserves_declared_charset(monkeypatch, content_type, body, expected):
    response = _Response(200, {"content-type": content_type}, body)
    _pinned_transport(monkeypatch, [response])
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description("http://public.invalid/about") == expected
    assert legacy_calls == []


def test_content_plan_site_reader_bounds_body_and_falls_back_on_transport_error(monkeypatch):
    accepted_description = b"<meta name='description' content='accepted at limit'>"
    accepted = _Response(200, {"content-type": "text/html"}, accepted_description + b"x" * (1_000_000 - len(accepted_description)))
    _pinned_transport(monkeypatch, [accepted])
    legacy_calls = _reject_legacy_requests(monkeypatch)
    assert content_plan_service._fetch_site_description("http://public.invalid/limit") == "accepted at limit"
    assert legacy_calls == []

    description = b"<meta name='description' content='must not parse'>"
    oversized = _Response(200, {"content-type": "text/html"}, description + b"x" * (1_000_001 - len(description)))
    observed = _pinned_transport(monkeypatch, [oversized])
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description("http://public.invalid/large") == ""
    assert legacy_calls == []
    assert oversized.read_limits == [1_000_001]
    assert len(observed["requests"]) == 1

    error = _pinned_transport(monkeypatch, [TimeoutError("bounded transport failure")])
    assert content_plan_service._fetch_site_description("http://public.invalid/failure") == ""
    assert len(error["requests"]) == 1


@pytest.mark.parametrize(
    "response",
    [_Response(302, body=b"<title>Must not parse</title>"), _Response(404, body=b"<title>Must not parse</title>")],
)
def test_content_plan_site_reader_falls_back_for_missing_redirect_or_non_success(monkeypatch, response):
    observed = _pinned_transport(monkeypatch, [response])
    legacy_calls = _reject_legacy_requests(monkeypatch)

    assert content_plan_service._fetch_site_description("http://public.invalid/start") == ""
    assert legacy_calls == []
    assert len(observed["requests"]) == 1


def test_content_plan_business_facts_blocks_stored_website_fallback_without_losing_description(monkeypatch):
    observed = _pinned_transport(monkeypatch, [], {"127.0.0.1": ["127.0.0.1"]})
    legacy_calls = _reject_legacy_requests(monkeypatch)

    facts = content_plan_service._content_plan_business_facts(
        {"name": "Business", "description": "Owner supplied description", "site": "", "website": "http://127.0.0.1/private"},
        {},
    )

    assert (facts["site"], facts["site_description"], facts["description"]) == ("http://127.0.0.1/private", "", "Owner supplied description")
    assert legacy_calls == []
    assert observed["pools"] == []
