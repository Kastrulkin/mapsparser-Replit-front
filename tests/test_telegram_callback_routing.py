import asyncio

import telegram_bot


def test_registered_control_callback_is_dispatched(monkeypatch):
    calls = []

    async def handler(query, user_id, control_scope):
        calls.append((query, user_id, control_scope))

    query = object()
    scope = {"kind": "business", "id": "business-1"}
    monkeypatch.setitem(telegram_bot.CONTROL_CALLBACK_ROUTES, "test_route", handler)

    handled = asyncio.run(
        telegram_bot._dispatch_control_callback("test_route", query, "user-1", scope)
    )

    assert handled is True
    assert calls == [(query, "user-1", scope)]


def test_unknown_control_callback_falls_through():
    handled = asyncio.run(
        telegram_bot._dispatch_control_callback("unknown_route", object(), "user-1", None)
    )

    assert handled is False


def test_prefixed_control_callback_is_dispatched(monkeypatch):
    calls = []

    async def handler(query, user_id, data):
        calls.append((user_id, data))

    monkeypatch.setattr(
        telegram_bot,
        "CONTROL_PREFIX_CALLBACK_ROUTES",
        (("prefix:", handler),),
    )

    handled = asyncio.run(
        telegram_bot._dispatch_control_callback("prefix:value", object(), "user-2", None)
    )

    assert handled is True
    assert calls == [("user-2", "prefix:value")]
