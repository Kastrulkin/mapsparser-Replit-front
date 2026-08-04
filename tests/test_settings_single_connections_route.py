from pathlib import Path


SETTINGS_PAGE = Path("frontend/src/pages/dashboard/SettingsPage.tsx")


def test_settings_has_one_canonical_connections_screen() -> None:
    source = SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "return <SettingsIntegrationsPage />;" in source
    assert "return <SettingsHubPage />;" not in source


def test_legacy_settings_routes_redirect_to_canonical_screen_with_query() -> None:
    source = SETTINGS_PAGE.read_text(encoding="utf-8")
    canonical_redirect = (
        "return <Navigate to={`/dashboard/settings${location.search}`} replace />;"
    )

    assert source.count(canonical_redirect) == 2
    assert "return <SettingsIntegrationsPage />;" not in source.split(
        "if (location.pathname.endsWith('/integrations'))", maxsplit=1
    )[1].split("}", maxsplit=1)[0]
