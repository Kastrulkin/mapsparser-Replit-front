import asyncio
import time

import requests

import telegram_bot


class _FakeMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str, **_kwargs):
        self.replies.append(text)


class _FakeUpdate:
    def __init__(self) -> None:
        self.effective_message = _FakeMessage()
        self.callback_query = None


def test_bind_timeout_keeps_bot_responsive_and_hides_internal_address(monkeypatch) -> None:
    def slow_timeout(*_args, **_kwargs):
        time.sleep(0.05)
        raise requests.exceptions.ReadTimeout(
            "HTTPConnectionPool(host='app', port=8000): Read timed out. (read timeout=10)"
        )

    monkeypatch.setattr(telegram_bot.requests, 'post', slow_timeout)
    update = _FakeUpdate()

    async def exercise() -> float:
        loop = asyncio.get_running_loop()
        started_at = loop.time()

        async def bot_heartbeat() -> float:
            await asyncio.sleep(0.01)
            return loop.time() - started_at

        heartbeat = asyncio.create_task(bot_heartbeat())
        await telegram_bot.handle_bind_token(update, None, 'expired-token', '850480769')
        return await heartbeat

    heartbeat_delay = asyncio.run(exercise())
    reply = update.effective_message.replies[-1]
    failures: list[str] = []
    if heartbeat_delay >= 0.035:
        failures.append(f'event loop blocked for {heartbeat_delay:.3f}s')
    if "host='app'" in reply or 'HTTPConnectionPool' in reply:
        failures.append('internal service address leaked to the user')

    assert not failures, '; '.join(failures)
