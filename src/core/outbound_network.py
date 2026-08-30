from __future__ import annotations

import ipaddress
import os
import socket
import urllib.request as urllib_request
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import certifi
import urllib3


@dataclass(frozen=True)
class OutboundHttpResponse:
    status_code: int
    text: str


def resolve_outbound_http_proxy() -> str:
    for key in ("OUTBOUND_HTTP_PROXY", "EXTERNAL_HTTP_PROXY"):
        value = str(os.getenv(key, "") or "").strip()
        if value:
            return value
    return ""


def outbound_urlopen(req, timeout: int = 10):
    proxy = resolve_outbound_http_proxy()
    if not proxy:
        return urllib_request.urlopen(req, timeout=timeout)
    opener = urllib_request.build_opener(
        urllib_request.ProxyHandler(
            {
                "http": proxy,
                "https": proxy,
            }
        )
    )
    return opener.open(req, timeout=timeout)


def validate_public_http_url(value: str) -> str:
    clean_url = str(value or "").strip()
    try:
        parsed = urlsplit(clean_url)
    except ValueError as error:
        raise ValueError("Допустима только публичная HTTP-ссылка") from error
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Допустима только публичная HTTP-ссылка")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Допустима только публичная HTTP-ссылка")

    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".localhost", ".local")):
        raise ValueError("Допустима только публичная HTTP-ссылка")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, ValueError) as error:
        raise ValueError("Допустима только публичная HTTP-ссылка") from error
    if not addresses:
        raise ValueError("Допустима только публичная HTTP-ссылка")
    for address in addresses:
        raw_ip = str(address[4][0] or "").split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError as error:
            raise ValueError("Допустима только публичная HTTP-ссылка") from error
        if not ip.is_global:
            raise ValueError("Допустима только публичная HTTP-ссылка")
    return clean_url


def _public_addresses_for_url(value: str) -> tuple[str, list[str], int]:
    clean_url = validate_public_http_url(value)
    parsed = urlsplit(clean_url)
    hostname = str(parsed.hostname or "").casefold().rstrip(".")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    public_addresses = []
    for address in addresses:
        raw_ip = str(address[4][0] or "").split("%", 1)[0]
        ip = ipaddress.ip_address(raw_ip)
        if not ip.is_global:
            raise ValueError("Допустима только публичная HTTP-ссылка")
        if raw_ip not in public_addresses:
            public_addresses.append(raw_ip)
    if not public_addresses:
        raise ValueError("Допустима только публичная HTTP-ссылка")
    return clean_url, public_addresses, port


def public_pinned_post(value: str, body: bytes, headers: dict[str, str], timeout: int = 5) -> OutboundHttpResponse:
    clean_url, public_addresses, port = _public_addresses_for_url(value)
    parsed = urlsplit(clean_url)
    hostname = str(parsed.hostname or "").casefold().rstrip(".")
    request_path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    default_port = 443 if parsed.scheme == "https" else 80
    host_header = hostname if port == default_port else f"{hostname}:{port}"
    request_headers = {**headers, "Host": host_header}
    pinned_ip = public_addresses[0]
    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            pinned_ip,
            port=port,
            timeout=urllib3.Timeout(total=timeout),
            retries=False,
            cert_reqs="CERT_REQUIRED",
            ca_certs=certifi.where(),
            assert_hostname=hostname,
            server_hostname=hostname,
        )
    else:
        pool = urllib3.HTTPConnectionPool(
            pinned_ip,
            port=port,
            timeout=urllib3.Timeout(total=timeout),
            retries=False,
        )
    try:
        response = pool.urlopen(
            "POST",
            request_path,
            body=body,
            headers=request_headers,
            redirect=False,
            preload_content=False,
        )
        try:
            response_text = response.read(1001).decode("utf-8", errors="replace")[:1000]
        finally:
            response.release_conn()
        return OutboundHttpResponse(status_code=int(response.status), text=response_text)
    finally:
        pool.close()


class _PublicRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def public_outbound_urlopen(req, timeout: int = 10):
    request_url = str(getattr(req, "full_url", req) or "").strip()
    validate_public_http_url(request_url)
    handlers = [_PublicRedirectHandler()]
    proxy = resolve_outbound_http_proxy()
    if proxy:
        handlers.insert(
            0,
            urllib_request.ProxyHandler(
                {
                    "http": proxy,
                    "https": proxy,
                }
            ),
        )
    opener = urllib_request.build_opener(*handlers)
    response = opener.open(req, timeout=timeout)
    try:
        validate_public_http_url(str(response.geturl() or request_url))
    except Exception:
        response.close()
        raise
    return response
