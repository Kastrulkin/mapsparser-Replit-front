from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ENTRYPOINT = REPO_ROOT / "frontend" / "index.html"
TELEGRAM_SDK_URL = "https://telegram.org/js/telegram-web-app.js"


def test_telegram_sdk_loads_before_the_frontend_bundle():
    html = FRONTEND_ENTRYPOINT.read_text(encoding="utf-8")

    sdk_position = html.find(TELEGRAM_SDK_URL)
    bundle_position = html.find('type="module"')
    head_end = html.find("</head>")

    assert sdk_position >= 0, "Telegram Mini App SDK is missing"
    assert sdk_position < head_end, "Telegram Mini App SDK must load in <head>"
    assert sdk_position < bundle_position, "Telegram Mini App SDK must load before the frontend bundle"
