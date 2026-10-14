from threading import Event,Thread
from services.outreach_dispatch_loop import SerializedDispatchLoop


def test_slow_unrelated_work_cannot_hold_send_loop_and_legacy_calls_do_not_duplicate():
    entered=Event();release=Event();calls=[]
    def callback():
        calls.append(1);entered.set();assert release.wait(2)
    loop=SerializedDispatchLoop(callback)
    thread=Thread(target=loop.tick);thread.start()
    try:
        assert entered.wait(2)
        assert loop.tick() is False
        assert calls==[1]
    finally:
        release.set();thread.join(2)
    assert not thread.is_alive()


def test_exception_releases_owner_for_next_native_cycle():
    calls=[]
    def callback():
        calls.append(1)
        if len(calls)==1:raise ValueError('provider_down')
    loop=SerializedDispatchLoop(callback)
    try:loop.tick()
    except ValueError:pass
    assert loop.tick() is True and len(calls)==2


def test_start_is_idempotent_and_loop_stops_cleanly():
    loop=SerializedDispatchLoop(lambda:None,interval=.01)
    first=loop.start()
    try:assert loop.start() is first
    finally:loop._stop.set();first.join(2)
    assert not first.is_alive()


def test_agent_queue_and_schedule_share_an_owner_independent_of_maintenance():
    from pathlib import Path
    source = Path('src/worker.py').read_text()
    assert '_AGENT_WORK_LOOP = SerializedDispatchLoop(_agent_work_cycle, interval=2)' in source
    assert '_AGENT_WORK_LOOP.start()' in source
    assert '_AGENT_WORK_LOOP.tick()' in source
    cycle = source.split('def _agent_work_cycle():', 1)[1].split('_AGENT_WORK_LOOP =', 1)[0]
    assert '_dispatch_agent_schedules_if_due()' in cycle
    assert '_process_agent_run_queue_if_due()' in cycle
    assert '_process_contact_intelligence_if_due' not in cycle
