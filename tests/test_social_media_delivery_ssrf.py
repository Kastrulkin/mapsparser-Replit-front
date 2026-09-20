import socket

import pytest

from core import outbound_network
from services import social_post_service
from services.social_posts import media_delivery


PUBLIC_IP = "93.184.216.34"


class _PinnedResponse:
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
    observed = {"dns": [], "pools": [], "requests": []}
    address_map = addresses or {}

    def resolving(hostname, port, *_args, **_kwargs):
        observed["dns"].append((hostname, port))
        values = address_map.get(hostname, [PUBLIC_IP])
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port)) for address in values]

    class Pool:
        def __init__(self, host, **kwargs):
            observed["pools"].append({"host": host, **kwargs})

        def urlopen(self, method, path, **kwargs):
            observed["requests"].append({"method": method, "path": path, **kwargs})
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


def test_external_media_rejects_private_url_before_legacy_transport(monkeypatch):
    legacy_calls = []
    pinned_calls = []

    def reject_private(*args, **kwargs):
        pinned_calls.append((args, kwargs))
        raise ValueError("private destination")

    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None, raising=False)
    monkeypatch.setattr(
        media_delivery,
        "outbound_urlopen",
        lambda *args, **kwargs: legacy_calls.append((args, kwargs)) or _Response(b"private-image"),
        raising=False,
    )
    monkeypatch.setattr(
        outbound_network,
        "public_pinned_get",
        reject_private,
    )

    assert media_delivery._media_asset_file(
        {"id": "photo-1", "public_url": "http://127.0.0.1/private.jpg"}
    ) == {}
    assert len(pinned_calls) == 1
    assert legacy_calls == []


@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("http://127.0.0.1/private.jpg", {"127.0.0.1": ["127.0.0.1"]}),
        ("http://private.invalid/private.jpg", {"private.invalid": ["10.0.0.9"]}),
        ("http://mixed.invalid/private.jpg", {"mixed.invalid": [PUBLIC_IP, "127.0.0.1"]}),
    ],
)
def test_external_media_rejects_private_and_mixed_destinations_before_pinned_transport(monkeypatch, url, addresses):
    observed = _pinned_transport(monkeypatch, [], addresses)
    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None)

    assert media_delivery._media_asset_file({"id": "photo-1", "public_url": url}) == {}
    assert observed["pools"] == []


def test_external_media_rechecks_dns_before_pinning(monkeypatch):
    observed = _pinned_transport(monkeypatch, [])
    answers = [[PUBLIC_IP], ["127.0.0.1"]]

    def rebinding(hostname, port, *_args, **_kwargs):
        observed["dns"].append((hostname, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port)) for address in answers.pop(0)]

    monkeypatch.setattr(outbound_network.socket, "getaddrinfo", rebinding)
    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None)

    assert media_delivery._media_asset_file({"id": "photo-1", "public_url": "http://rebind.invalid/photo.jpg"}) == {}
    assert len(observed["dns"]) == 2
    assert observed["pools"] == []


def test_external_media_follows_only_pinned_public_redirects_and_rejects_oversize(monkeypatch):
    requested = []
    responses = [
        outbound_network.OutboundHttpFetchResponse(302, {"location": "/image.jpg"}, b""),
        outbound_network.OutboundHttpFetchResponse(200, {"content-type": "image/jpeg"}, b"image"),
    ]

    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None, raising=False)
    monkeypatch.setattr(
        outbound_network,
        "public_pinned_get",
        lambda value, **kwargs: requested.append((value, kwargs)) or responses.pop(0),
    )

    result = media_delivery._media_asset_file(
        {"id": "photo-1", "public_url": "https://public.invalid/start", "mime_type": "image/jpeg"}
    )

    assert result["content"] == b"image"
    assert [value for value, _kwargs in requested] == [
        "https://public.invalid/start",
        "https://public.invalid/image.jpg",
    ]
    assert all(kwargs["max_bytes"] == 10_000_001 for _value, kwargs in requested)

    monkeypatch.setattr(
        outbound_network,
        "public_pinned_get",
        lambda *_args, **_kwargs: outbound_network.OutboundHttpFetchResponse(
            200, {"content-type": "image/jpeg"}, b"x" * 10_000_001
        ),
    )
    assert media_delivery._media_asset_file(
        {"id": "photo-2", "public_url": "https://public.invalid/large", "mime_type": "image/jpeg"}
    ) == {}


def test_external_media_follows_public_redirects_with_real_pinned_transport_and_bounded_read(monkeypatch):
    first = _PinnedResponse(302, {"location": "/image.jpg"})
    second = _PinnedResponse(200, {"content-type": "image/jpeg"}, b"image")
    observed = _pinned_transport(monkeypatch, [first, second])
    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None)

    result = media_delivery._media_asset_file(
        {"id": "photo-1", "public_url": "https://public.invalid/start", "mime_type": "image/jpeg"}
    )

    assert result["content"] == b"image"
    assert [request["path"] for request in observed["requests"]] == ["/start", "/image.jpg"]
    assert all(request["redirect"] is False for request in observed["requests"])
    assert all(response.read_limits == [10_000_001] and response.released for response in (first, second))


def test_external_media_rejects_private_redirect_through_pinned_transport(monkeypatch):
    requested = []

    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None)

    def pinned_get(value, **_kwargs):
        requested.append(value)
        if value == "https://public.invalid/start":
            return outbound_network.OutboundHttpFetchResponse(302, {"location": "http://127.0.0.1/private.jpg"}, b"")
        raise ValueError("private destination")

    monkeypatch.setattr(outbound_network, "public_pinned_get", pinned_get)

    assert media_delivery._media_asset_file(
        {"id": "photo-3", "public_url": "https://public.invalid/start"}
    ) == {}
    assert requested == ["https://public.invalid/start", "http://127.0.0.1/private.jpg"]


def test_external_media_rejects_private_redirect_before_second_pinned_connection(monkeypatch):
    observed = _pinned_transport(
        monkeypatch,
        [_PinnedResponse(302, {"location": "http://127.0.0.1/private.jpg"})],
        {"127.0.0.1": ["127.0.0.1"]},
    )
    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None)

    assert media_delivery._media_asset_file(
        {"id": "photo-3", "public_url": "https://public.invalid/start"}
    ) == {}
    assert len(observed["pools"]) == 1
    assert len(observed["requests"]) == 1


def test_external_media_caps_redirects_and_handles_transport_failure(monkeypatch):
    redirects = [_PinnedResponse(302, {"location": f"/hop-{index}"}) for index in range(1, 6)]
    observed = _pinned_transport(monkeypatch, redirects)
    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None)

    assert media_delivery._media_asset_file(
        {"id": "photo-4", "public_url": "http://public.invalid/start"}
    ) == {}
    assert len(observed["requests"]) == 5

    failed = _pinned_transport(monkeypatch, [TimeoutError("synthetic timeout")])
    assert media_delivery._media_asset_file(
        {"id": "photo-5", "public_url": "http://public.invalid/timeout"}
    ) == {}
    assert len(failed["requests"]) == 1


def test_external_media_rejects_overflow_after_bounded_pinned_read(monkeypatch):
    oversized = _PinnedResponse(200, {"content-type": "image/jpeg"}, b"x" * 10_000_001)
    observed = _pinned_transport(monkeypatch, [oversized])
    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: None)

    assert media_delivery._media_asset_file(
        {"id": "photo-overflow", "public_url": "https://public.invalid/overflow.jpg"}
    ) == {}
    assert len(observed["requests"]) == 1
    assert oversized.read_limits == [10_000_001]
    assert oversized.released is True


def test_external_media_keeps_local_storage(monkeypatch):
    def fail_network(*_args, **_kwargs):
        raise AssertionError("network should not run for stored media")

    monkeypatch.setattr(media_delivery, "load_media_file", lambda *_args: b"stored")
    monkeypatch.setattr(social_post_service, "load_media_file", lambda *_args: b"stored")
    monkeypatch.setattr(outbound_network, "public_pinned_get", fail_network)
    assert media_delivery._media_asset_file({"id": "stored", "storage_path": "stored.jpg", "public_url": "https://public.invalid/photo.jpg"})[
        "content"
    ] == b"stored"


def test_runtime_facade_uses_pinned_fetch(monkeypatch):
    response = _PinnedResponse(200, {"content-type": "image/jpeg"}, b"facade-image")
    observed = _pinned_transport(monkeypatch, [response])
    monkeypatch.setattr(social_post_service, "load_media_file", lambda *_args: None)
    assert social_post_service._media_asset_file(
        {"id": "facade", "public_url": "https://public.invalid/facade.jpg"}
    )["content"] == b"facade-image"
    assert observed["pools"][0]["host"] == PUBLIC_IP


class _Response:
    def __init__(self, content):
        self.content = content

    def read(self):
        return self.content

    def close(self):
        return None
