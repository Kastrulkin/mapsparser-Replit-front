from __future__ import annotations

import os
import ipaddress
import socket
import urllib.request as urllib_request
from urllib.parse import urlsplit


def validate_public_http_url(value: str) -> str:
    clean_url = str(value or '').strip()
    parsed = urlsplit(clean_url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Допустима только публичная HTTP-ссылка')
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('Допустима только публичная HTTP-ссылка')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Допустима только публичная HTTP-ссылка')
    return clean_url


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
