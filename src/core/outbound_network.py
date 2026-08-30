from __future__ import annotations

import ipaddress
import os
import socket
import urllib.request as urllib_request
from urllib.parse import urlsplit


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
