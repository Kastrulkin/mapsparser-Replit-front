from services.social_post_service import (
    default_publish_mode,
    next_action_for_social_post,
    openclaw_browser_available,
)


def test_default_publish_mode_uses_api_for_connected_social_channels(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)

    assert default_publish_mode("telegram") == "api"
    assert default_publish_mode("vk") == "api"
    assert default_publish_mode("google_business") == "api"


def test_default_publish_mode_keeps_yandex_manual_when_browser_capability_is_absent(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)
    monkeypatch.delenv("OPENCLAW_CAPABILITY_CATALOG_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_BASE_URL", raising=False)

    assert default_publish_mode("yandex_maps") == "manual"
    assert default_publish_mode("two_gis") == "manual"


def test_openclaw_browser_available_detects_live_catalog_action(monkeypatch):
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_ENABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_BROWSER_USE_AVAILABLE", raising=False)

    def fetcher():
        return {
            "actions": [
                {
                    "openclaw_action_ref": "openclaw.browser.fill_form",
                    "title": "Browser supervised publish",
                    "service": "browser",
                    "localos_capability": "social.post.publish_supervised_browser",
                    "status": "available",
                }
            ]
        }

    assert openclaw_browser_available(fetcher=fetcher) is True


def test_next_action_separates_review_api_and_supervised_states():
    assert next_action_for_social_post({"status": "needs_review", "platform": "telegram"}) == "review_required"
    assert next_action_for_social_post({"status": "approved", "platform": "telegram"}) == "wait_for_api_publish"
    assert next_action_for_social_post({"status": "approved", "platform": "yandex_maps"}) == "start_supervised_publish"
    assert next_action_for_social_post({"status": "needs_supervised_publish", "platform": "two_gis"}) == "open_supervised_publish"
