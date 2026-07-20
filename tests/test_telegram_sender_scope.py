from pathlib import Path

import pytest

from api.telegram_research_api import _account_for_scope, _requested_sender_scope
from services.telegram_account_permissions_service import assert_account_access


ROOT = Path(__file__).resolve().parents[1]


def test_superadmin_defaults_to_business_scope_without_explicit_platform_request():
    assert _requested_sender_scope(
        {"user_id": "admin", "is_superadmin": True},
        {},
    ) == "business"


def test_superadmin_can_explicitly_request_platform_scope():
    assert _requested_sender_scope(
        {"user_id": "admin", "is_superadmin": True},
        {"scope_type": "platform"},
    ) == "platform"


def test_business_user_cannot_request_platform_scope():
    with pytest.raises(PermissionError, match="только суперадмину"):
        _requested_sender_scope(
            {"user_id": "user", "is_superadmin": False},
            {"scope_type": "platform"},
        )


def test_telegram_ui_passes_explicit_scope_through_connection_and_permissions():
    component = (ROOT / "frontend/src/components/TelegramResearchSetup.tsx").read_text()
    admin_registry = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    settings_page = (ROOT / "frontend/src/pages/dashboard/settings/SettingsHubPage.tsx").read_text()
    integrations_page = (ROOT / "frontend/src/pages/dashboard/settings/IntegrationsPageV3.tsx").read_text()

    assert component.count("scope_type: scopeType") >= 3
    assert "status?scope_type=" in component
    assert "telegram-account?scope_type=" in component
    assert "Проверить готовность" in component
    assert "Сообщения от имени LocalOS" in component
    assert "Сообщения от вашего имени" in component
    assert "sender_scope=" in admin_registry
    assert "senderScope={senderScope}" in settings_page
    assert "Telegram для продаж LocalOS" in integrations_page
    assert "не будет доступен партнёрским кампаниям" in integrations_page
    assert "Вернуться к выбранному лиду" in integrations_page
    assert "LocalOS представляет бизнес" in admin_registry
    assert "sender_mode: senderMode" in admin_registry
    assert "selectedSenderScope" in admin_registry


class _ScopeAccountCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query, _params=None):
        return None

    def fetchall(self):
        return self.rows


def test_scope_account_loader_uses_exact_platform_binding(monkeypatch):
    cursor = _ScopeAccountCursor([
        {"account_id": "business-account", "sender_account_id": None, "has_any_binding": True},
        {"account_id": "platform-account", "sender_account_id": "sender-platform", "has_any_binding": True},
    ])
    monkeypatch.setattr(
        "api.telegram_research_api.load_userbot_account",
        lambda _cursor, **kwargs: {
            "account_id": kwargs["account_id"],
            "sender_scope": "platform" if kwargs["account_id"] == "platform-account" else "business",
        },
    )

    account = _account_for_scope(cursor, "business-1", "platform")

    assert account["account_id"] == "platform-account"


def test_scope_account_loader_does_not_reuse_bound_business_account_for_platform(monkeypatch):
    cursor = _ScopeAccountCursor([
        {"account_id": "business-account", "sender_account_id": None, "has_any_binding": True},
    ])
    monkeypatch.setattr(
        "api.telegram_research_api.load_userbot_account",
        lambda _cursor, **_kwargs: {"account_id": "business-account", "sender_scope": "business"},
    )

    assert _account_for_scope(cursor, "business-1", "platform") is None


class _BindingCursor:
    def __init__(self, binding):
        self.binding = binding

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return self.binding


def test_platform_preflight_requires_exact_connected_platform_binding(monkeypatch):
    monkeypatch.setattr(
        "services.telegram_account_permissions_service.get_account_context",
        lambda _cursor, _account_id: {
            "account_id": "telegram-1",
            "business_id": "credential-container-business",
            "is_active": True,
            "radar_enabled": True,
            "outreach_enabled": True,
        },
    )

    allowed, reason, _context = assert_account_access(
        _BindingCursor(None),
        "telegram-1",
        business_id=None,
        scope_type="platform",
        capability="outreach",
    )

    assert allowed is False
    assert reason == "sender_scope_mismatch"


def test_platform_preflight_accepts_exact_connected_platform_binding(monkeypatch):
    monkeypatch.setattr(
        "services.telegram_account_permissions_service.get_account_context",
        lambda _cursor, _account_id: {
            "account_id": "telegram-1",
            "business_id": "credential-container-business",
            "is_active": True,
            "radar_enabled": True,
            "outreach_enabled": True,
        },
    )

    allowed, reason, _context = assert_account_access(
        _BindingCursor({"id": "sender-platform"}),
        "telegram-1",
        business_id=None,
        scope_type="platform",
        capability="outreach",
    )

    assert allowed is True
    assert reason == "ready"
