from core import telegram_userbot


class FakeSocks:
    SOCKS5 = 2
    SOCKS4 = 1
    HTTP = 3


def test_userbot_accepts_openclaw_proxy_env_alias(monkeypatch):
    monkeypatch.setattr(telegram_userbot, "socks", FakeSocks)
    monkeypatch.delenv("TELEGRAM_USERBOT_PROXY", raising=False)
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "socks5://192.168.0.177:10808")

    proxy = telegram_userbot._resolve_proxy()

    assert proxy is not None
    assert proxy[1] == "192.168.0.177"
    assert proxy[2] == 10808


def test_userbot_specific_proxy_has_priority(monkeypatch):
    monkeypatch.setattr(telegram_userbot, "socks", FakeSocks)
    monkeypatch.setenv("TELEGRAM_USERBOT_PROXY", "socks5://127.0.0.1:10808")
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "socks5://192.168.0.177:10808")

    proxy = telegram_userbot._resolve_proxy()

    assert proxy is not None
    assert proxy[1] == "127.0.0.1"
    assert proxy[2] == 10808
