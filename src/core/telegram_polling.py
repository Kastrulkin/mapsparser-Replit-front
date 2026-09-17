"""Bound long polling and restart a stalled receiver without dropping updates."""
import asyncio
import json
import os
import threading
import time
from pathlib import Path
from telegram.request import HTTPXRequest
from telegram.error import TimedOut

HEARTBEAT=Path('/tmp/localos-telegram-poll.heartbeat')
STALE_SECONDS=180


def recent_poll(now=None):
    try:
        age=(time.time() if now is None else now)-float(HEARTBEAT.read_text())
        return 0<=age<STALE_SECONDS
    except (OSError,ValueError):
        return False


class PollingRequest(HTTPXRequest):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        HEARTBEAT.unlink(missing_ok=True)
        self._last_success=time.monotonic()
        self._last_activity=self._last_success
        self._stop_watch=threading.Event()
        threading.Thread(target=self._watch,daemon=True,name='telegram-poll-watch').start()

    def _watch(self):
        while not self._stop_watch.wait(10):
            if time.monotonic()-self._last_activity>=STALE_SECONDS:
                # Independent of the event loop: restart also recovers a stuck loop.
                os.write(2,b'Telegram polling stalled; restarting receiver without dropping updates\n')
                os._exit(1)

    async def do_request(self,url,method,**kwargs):
        self._last_activity=time.monotonic()
        try:
            result=await asyncio.wait_for(super().do_request(url,method,**kwargs),timeout=65)
        except asyncio.TimeoutError:
            raise TimedOut() from None
        finally:
            self._last_activity=time.monotonic()
        if url.rsplit('/',1)[-1].lower()=='getupdates' and result[0]==200:
            try:
                success=json.loads(result[1]).get('ok') is True
            except (ValueError,AttributeError):
                success=False
            if success:
                self._last_success=time.monotonic()
                HEARTBEAT.write_text(str(time.time()))
        return result

    async def shutdown(self):
        self._stop_watch.set()
        await super().shutdown()
