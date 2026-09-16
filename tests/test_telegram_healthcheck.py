from core import telegram_healthcheck


def test_disabled_bot_needs_no_network(monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN',raising=False)
    assert telegram_healthcheck.healthy()


def test_real_connectivity_success_and_failure(monkeypatch):
    from core import telegram_polling
    monkeypatch.setattr(telegram_polling,'recent_poll',lambda:True)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-secret')
    monkeypatch.setattr(telegram_healthcheck.Path,'read_bytes',lambda self:b'python src/telegram_bot.py')
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return b'{"ok":true}'
    monkeypatch.setattr(telegram_healthcheck,'telegram_urlopen',lambda *a,**kw:Response())
    assert telegram_healthcheck.healthy()
    def timeout(*a,**kw):raise TimeoutError('secret URL must never be printed')
    monkeypatch.setattr(telegram_healthcheck,'telegram_urlopen',timeout)
    assert not telegram_healthcheck.healthy()


def test_missing_bot_process_is_unhealthy(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-secret')
    monkeypatch.setattr(telegram_healthcheck.Path,'read_bytes',lambda self:b'sleep infinity')
    assert not telegram_healthcheck.healthy()


def test_accessible_api_is_not_enough_when_polling_stalled(monkeypatch):
    from core import telegram_polling
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-secret')
    monkeypatch.setattr(telegram_healthcheck.Path,'read_bytes',lambda self:b'python src/telegram_bot.py')
    monkeypatch.setattr(telegram_polling,'recent_poll',lambda:False)
    assert not telegram_healthcheck.healthy()
