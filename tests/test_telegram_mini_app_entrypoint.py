from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ENTRYPOINT = REPO_ROOT / "frontend" / "index.html"
FRONTEND_BOOTSTRAP = REPO_ROOT / "frontend" / "src" / "main.tsx"
TELEGRAM_SDK_URL = "https://telegram.org/js/telegram-web-app.js"


def test_telegram_sdk_is_loaded_only_by_the_telegram_control_bootstrap():
    html = FRONTEND_ENTRYPOINT.read_text(encoding="utf-8")
    bootstrap = FRONTEND_BOOTSTRAP.read_text(encoding="utf-8")

    assert TELEGRAM_SDK_URL not in html, "Ordinary web routes must not depend on the Telegram CDN"
    assert TELEGRAM_SDK_URL in bootstrap, "Telegram Mini App SDK bootstrap is missing"
    assert "window.location.pathname === TELEGRAM_CONTROL_PATH" in bootstrap
    assert "if (isTelegramControlRoute()) await loadTelegramSdk();" in bootstrap
    assert "renderApplication();" in bootstrap
