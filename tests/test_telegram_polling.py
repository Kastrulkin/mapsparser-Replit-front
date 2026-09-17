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
    request._last_activity=0
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


def test_network_errors_do_not_keep_receiver_healthy(monkeypatch):
    monkeypatch.setattr(telegram_polling.threading.Thread,'start',lambda self:None)
    request=telegram_polling.PollingRequest()
    request._last_success=0;request._last_activity=301
    monkeypatch.setattr(telegram_polling.time,'monotonic',lambda:301)
    class Stop:
        def wait(self,seconds):return False
    request._stop_watch=Stop()
    def exit_process(code):raise SystemExit(code)
    monkeypatch.setattr(telegram_polling.os,'_exit',exit_process)
    import pytest
    with pytest.raises(SystemExit):request._watch()


def test_bot_startup_retry_replaces_closed_event_loop():
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    module=ast.parse(Path('src/telegram_bot.py').read_text())
    entry=next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    attempts=[]
    def run():
        loop=asyncio.get_event_loop()
        assert not loop.is_closed()
        attempts.append(loop)
        loop.close()
        if len(attempts)==1:raise RuntimeError('first startup failed')
    namespace={'TELEGRAM_BOT_TOKEN':'test','asyncio':asyncio,'_run_bot_once':run,'time':SimpleNamespace(sleep=lambda _:None)}
    exec(compile(ast.Module(body=[entry],type_ignores=[]),'<bot-main-test>','exec'),namespace)
    namespace['main']()
    assert len(attempts)==2 and attempts[0] is not attempts[1]


def test_unused_transport_does_not_start_restart_watchdog(monkeypatch):
    started=[]
    monkeypatch.setattr(telegram_polling.threading.Thread,'start',lambda self:started.append(True))
    monkeypatch.setattr(telegram_polling.HTTPXRequest,'do_request',AsyncMock(return_value=(200,b'{"ok":true,"result":[]}')))
    async def check():
        request=telegram_polling.PollingRequest()
        assert not started
        await request.do_request('https://test/getMe','POST')
        assert not started
        await request.do_request('https://test/getUpdates','POST')
        assert len(started)==1
        await request.shutdown()
    asyncio.run(check())


def test_startup_backoff_does_not_hide_new_messages_for_five_minutes():
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    entry=next(node for node in ast.parse(Path('src/telegram_bot.py').read_text()).body if isinstance(node,ast.FunctionDef) and node.name=='main')
    attempts=[];delays=[]
    def run():
        attempts.append(True)
        if len(attempts)<7:raise RuntimeError('network unavailable')
    namespace={'TELEGRAM_BOT_TOKEN':'test','asyncio':asyncio,'_run_bot_once':run,'time':SimpleNamespace(sleep=delays.append)}
    exec(compile(ast.Module(body=[entry],type_ignores=[]),'<bot-main-test>','exec'),namespace)
    namespace['main']()
    assert delays==[5,10,20,30,30,30]
