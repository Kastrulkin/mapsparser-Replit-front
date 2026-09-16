"""Read-only Telegram connectivity probe; never consumes updates or prints secrets."""
import json
import os
from pathlib import Path
from core.telegram_network import telegram_urlopen


def healthy():
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
    if not token:
        return True
    if b'telegram_bot.py' not in Path('/proc/1/cmdline').read_bytes():
        return False
    from core.telegram_polling import recent_poll
    if not recent_poll():
        return False
    try:
        with telegram_urlopen('https://api.telegram.org/bot'+token+'/getMe',timeout=8) as response:
            return response.status==200 and json.loads(response.read(65536)).get('ok') is True
    except Exception:
        return False


if __name__=='__main__':
    raise SystemExit(0 if healthy() else 1)
