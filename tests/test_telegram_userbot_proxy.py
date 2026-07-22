import asyncio

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


def test_entity_classifier_distinguishes_user_bot_channel_and_group():
    class User:
        id = 1
        username = "owner"
        first_name = "Анна"
        last_name = ""
        bot = False

    class Bot(User):
        bot = True

    class Channel:
        id = 2
        username = "cream_shop"
        title = "Cream.Shop"
        broadcast = True
        megagroup = False
        gigagroup = False

    class Megagroup(Channel):
        broadcast = False
        megagroup = True

    class Chat:
        id = 3
        username = None
        title = "Рабочая группа"

    user = telegram_userbot.classify_telegram_entity(User())
    bot = telegram_userbot.classify_telegram_entity(Bot())
    channel = telegram_userbot.classify_telegram_entity(Channel())
    group = telegram_userbot.classify_telegram_entity(Megagroup())
    chat = telegram_userbot.classify_telegram_entity(Chat())

    assert user["entity_type"] == "user"
    assert user["recipient_eligible"] is True
    assert bot["entity_type"] == "bot"
    assert bot["recipient_eligible"] is False
    assert channel["entity_type"] == "broadcast_channel"
    assert channel["signal_source_eligible"] is True
    assert group["entity_type"] == "megagroup"
    assert group["recipient_eligible"] is False
    assert chat["entity_type"] == "group_chat"


def test_entity_inspection_resolves_tme_url_through_connected_account(monkeypatch):
    requested = []

    class Channel:
        id = 42
        username = "cream_shop"
        title = "Cream.Shop"
        broadcast = True
        megagroup = False
        gigagroup = False

    class Client:
        disconnected = False

        async def is_user_authorized(self):
            return True

        async def get_entity(self, peer):
            requested.append(peer)
            return Channel()

        async def disconnect(self):
            self.disconnected = True

    client = Client()

    async def connect(_auth_data):
        return client

    monkeypatch.setattr(telegram_userbot, "_connect_client", connect)

    result = asyncio.run(
        telegram_userbot._inspect_telegram_entity_async(
            {"session_string": "ready"},
            "https://t.me/s/cream_shop/6240",
        )
    )

    assert requested == ["@cream_shop"]
    assert result["status"] == "ok"
    assert result["entity_type"] == "broadcast_channel"
    assert result["entity_id"] == "42"
    assert client.disconnected is True
