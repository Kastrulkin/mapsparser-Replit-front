from __future__ import annotations

import os
import urllib.request as urllib_request
from typing import Any


def resolve_telegram_http_proxy() -> str:
    for key in ("TELEGRAM_HTTP_PROXY", "TELEGRAM_API_PROXY"):
        value = str(os.getenv(key, "") or "").strip()
        if value:
            return value
    return ""


def build_requests_proxy_kwargs() -> dict[str, Any]:
    proxy = resolve_telegram_http_proxy()
    if not proxy:
        return {}
    return {
        "proxies": {
            "http": proxy,
            "https": proxy,
        }
    }


def telegram_urlopen(req, timeout: int = 10):
    proxy = resolve_telegram_http_proxy()
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
