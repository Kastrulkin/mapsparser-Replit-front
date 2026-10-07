"""Environment-aware CORS policy shared by LocalOS Flask entrypoints."""

import ipaddress
import os
from urllib.parse import urlsplit

from flask_cors import CORS


DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _is_loopback_origin(origin: str) -> bool:
    hostname = urlsplit(origin).hostname
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def resolve_allowed_origins() -> list[str]:
    configured = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    app_env = str(os.getenv("APP_ENV", "") or "").strip().lower()
    if app_env == "production":
        return [origin for origin in origins if not _is_loopback_origin(origin)]
    return origins


def configure_cors(app) -> None:
    CORS(
        app,
        supports_credentials=True,
        origins=resolve_allowed_origins(),
        always_send=False,
    )
