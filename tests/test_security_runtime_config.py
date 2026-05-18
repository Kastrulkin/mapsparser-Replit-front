import importlib
from pathlib import Path

import pytest


def test_compose_passes_security_runtime_env_to_app_and_worker():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    required = [
        "ALLOWED_ORIGINS: ${ALLOWED_ORIGINS:-}",
        "RATE_LIMITING_ENABLED: ${RATE_LIMITING_ENABLED:-true}",
        "RATE_LIMIT_STORAGE_URI: ${RATE_LIMIT_STORAGE_URI:-memory://}",
        "EXTERNAL_AUTH_SECRET_KEY: ${EXTERNAL_AUTH_SECRET_KEY:-}",
    ]
    for item in required:
        assert compose.count(item) == 2


def test_auth_secret_required_when_app_env_is_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("EXTERNAL_AUTH_SECRET_KEY", raising=False)

    import auth_encryption

    module = importlib.reload(auth_encryption)
    with pytest.raises(RuntimeError, match="EXTERNAL_AUTH_SECRET_KEY is required in production"):
        module._get_encryption_key()


def test_auth_secret_allows_production_when_present(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EXTERNAL_AUTH_SECRET_KEY", "x" * 32)

    import auth_encryption

    module = importlib.reload(auth_encryption)
    assert module._get_encryption_key()
