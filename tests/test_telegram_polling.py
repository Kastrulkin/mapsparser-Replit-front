import asyncio
import json
from unittest.mock import AsyncMock
from core import telegram_polling


def test_poll_freshness_and_missing_file(tmp_path,monkeypatch):
    p=tmp_path/'heartbeat';monkeypatch.setattr(telegram_polling,'HEARTBEAT',p)
    assert not telegram_polling.recent_poll(1000)
    p.write_text('900');assert telegram_polling.recent_poll(1000)
    assert not telegram_polling.recent_poll(1100)


def test_only_successful_poll_updates_heartbeat(tmp_path,monkeypatch):
    p=tmp_path/'heartbeat';monkeypatch.setattr(telegram_polling,'HEARTBEAT',p)
    monkeypatch.setattr(telegram_polling.threading.Thread,'start',lambda self:None)
    mock=AsyncMock(return_value=(200,b'{"ok":true,"result":[]}'))
    monkeypatch.setattr(telegram_polling.HTTPXRequest,'do_request',mock)
    async def check():
        request=telegram_polling.PollingRequest()
        await request.do_request('https://api.telegram.org/botfake/getMe','POST');assert not p.exists()
        await request.do_request('https://api.telegram.org/botfake/getUpdates','POST');assert telegram_polling.recent_poll()
        p.unlink();mock.return_value=(200,b'{"ok":false}')
        await request.do_request('https://api.telegram.org/botfake/getUpdates','POST');assert not p.exists()
        await request.shutdown()
    asyncio.run(check())


def test_timeout_is_bounded_and_reported(monkeypatch):
    monkeypatch.setattr(telegram_polling.threading.Thread,'start',lambda self:None)
    monkeypatch.setattr(telegram_polling.HTTPXRequest,'do_request',AsyncMock(return_value=(200,b'{}')))
    async def timeout(awaitable,timeout):
        assert timeout==65
        awaitable.close()
        raise asyncio.TimeoutError()
    monkeypatch.setattr(telegram_polling.asyncio,'wait_for',timeout)
    async def check():
        import pytest
        request=telegram_polling.PollingRequest()
        with pytest.raises(telegram_polling.TimedOut):await request.do_request('https://test/getUpdates','POST')
        await request.shutdown()
    asyncio.run(check())


def test_watchdog_exits_on_stale_receiver(monkeypatch):
    monkeypatch.setattr(telegram_polling.threading.Thread,'start',lambda self:None)
    request=telegram_polling.PollingRequest()
    request._last_success=0
    monkeypatch.setattr(telegram_polling.time,'monotonic',lambda:181)
    class Stop:
        def wait(self,seconds):return False
    request._stop_watch=Stop()
    def exit_process(code):raise SystemExit(code)
    monkeypatch.setattr(telegram_polling.os,'_exit',exit_process)
    import pytest
    with pytest.raises(SystemExit):request._watch()


def test_startup_preserves_pending_updates():
    from pathlib import Path
    source=Path('src/telegram_bot.py').read_text()
    assert 'drop_pending_updates=True' not in source
    assert 'drop_pending_updates=False' in source
