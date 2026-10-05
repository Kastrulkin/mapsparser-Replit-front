import signal
import threading

import worker


def test_shutdown_after_current_callback_prevents_next_top_level_callback(monkeypatch):
    stop_event = threading.Event()
    calls = []

    def role_enabled(role):
        return role in {"parser", "dispatcher"}

    def parser_callback():
        calls.append("parser")
        stop_event.set()

    def dispatcher_callback():
        calls.append("dispatcher")

    monkeypatch.setattr(worker, "_worker_role_enabled", role_enabled)
    monkeypatch.setattr(worker, "process_queue", parser_callback)
    monkeypatch.setattr(worker, "_prepare_riderra_systematic_outreach_if_due", dispatcher_callback)

    worker._run_worker_polling_cycle(stop_event)

    assert calls == ["parser"]


def test_shutdown_between_dispatcher_callbacks_skips_remaining_callbacks(monkeypatch):
    stop_event = threading.Event()
    calls = []
    dispatcher_callbacks = (
        "_prepare_riderra_systematic_outreach_if_due",
        "_dispatch_outreach_queue_if_due",
        "_run_card_automation_if_due",
        "_run_founder_content_if_due",
        "_dispatch_social_posts_if_due",
        "_collect_social_post_metrics_if_due",
        "_process_creator_offer_distribution_if_due",
        "_dispatch_creator_notifications_if_due",
        "_notify_superadmin_outreach_replies_if_due",
        "_notify_superadmin_community_sources_if_due",
        "_dispatch_openclaw_callback_outbox_if_due",
        "_check_openclaw_callback_alerts_if_due",
    )

    def role_enabled(role):
        return role == "dispatcher"

    def stop_after_first():
        calls.append(dispatcher_callbacks[0])
        stop_event.set()

    monkeypatch.setattr(worker, "_worker_role_enabled", role_enabled)
    monkeypatch.setattr(worker, dispatcher_callbacks[0], stop_after_first)
    for callback_name in dispatcher_callbacks[1:]:
        monkeypatch.setattr(worker, callback_name, lambda name=callback_name: calls.append(name))

    worker._run_worker_polling_cycle(stop_event)

    assert calls == [dispatcher_callbacks[0]]


def test_pre_set_shutdown_event_invokes_no_callbacks(monkeypatch):
    stop_event = threading.Event()
    calls = []
    stop_event.set()

    monkeypatch.setattr(worker, "_worker_role_enabled", lambda _role: True)
    monkeypatch.setattr(worker, "process_queue", lambda: calls.append("parser"))

    worker._run_worker_polling_cycle(stop_event)

    assert calls == []


def test_pre_set_shutdown_event_skips_outer_polling_loop(monkeypatch):
    stop_event = threading.Event()
    cycles = []
    stop_event.set()

    monkeypatch.setattr(
        worker,
        "_run_worker_polling_cycle",
        lambda current_stop_event: cycles.append(current_stop_event),
    )

    worker.run_worker_polling_loop(stop_event, sleep_seconds=10)

    assert cycles == []


def test_shutdown_event_interrupts_idle_wait(monkeypatch):
    class StopEvent:
        def __init__(self):
            self.wait_calls = []
            self._set = False

        def is_set(self):
            return self._set

        def set(self):
            self._set = True

        def wait(self, seconds):
            self.wait_calls.append(seconds)
            return True

    stop_event = StopEvent()
    cycles = []

    def polling_cycle(current_stop_event):
        cycles.append(current_stop_event)

    monkeypatch.setattr(worker, "_run_worker_polling_cycle", polling_cycle)

    worker.run_worker_polling_loop(stop_event, sleep_seconds=10)

    assert cycles == [stop_event]
    assert stop_event.wait_calls == [10]


def test_callback_error_aborts_current_cycle_and_next_cycle_still_runs(monkeypatch, capsys):
    stop_event = threading.Event()
    calls = []

    def parser_callback():
        calls.append("parser")
        if len(calls) == 1:
            raise RuntimeError("synthetic callback error")
        stop_event.set()

    monkeypatch.setattr(worker, "_worker_role_enabled", lambda role: role == "parser")
    monkeypatch.setattr(worker, "process_queue", parser_callback)

    worker.run_worker_polling_loop(stop_event, sleep_seconds=0)

    assert calls == ["parser", "parser"]
    assert "Критическая ошибка worker loop: synthetic callback error" in capsys.readouterr().out


def test_all_role_callbacks_keep_canonical_order_without_shutdown(monkeypatch):
    stop_event = threading.Event()
    calls = []
    expected = (
        "process_queue",
        "_prepare_riderra_systematic_outreach_if_due",
        "_dispatch_outreach_queue_if_due",
        "_run_card_automation_if_due",
        "_run_founder_content_if_due",
        "_dispatch_social_posts_if_due",
        "_collect_social_post_metrics_if_due",
        "_process_creator_offer_distribution_if_due",
        "_dispatch_creator_notifications_if_due",
        "_notify_superadmin_outreach_replies_if_due",
        "_notify_superadmin_community_sources_if_due",
        "_dispatch_openclaw_callback_outbox_if_due",
        "_check_openclaw_callback_alerts_if_due",
        "_enrich_creator_sources_if_due",
        "_revalidate_creator_profiles_if_due",
        "_process_creator_search_if_due",
        "_process_contact_intelligence_if_due",
        "_run_telegram_opportunity_monitor_if_due",
        "_run_knowledge_telegram_monitor_if_due",
        "_refresh_outreach_pain_library_if_due",
        "_run_knowledge_embeddings_if_due",
        "_reconcile_openclaw_billing_if_due",
        "_run_yookassa_renewals_if_due",
        "_run_web_tracking_maintenance_if_due",
        "_materialize_today_priority_proposals_if_due",
        "_purge_compiled_inputs_if_due",
        "_dispatch_agent_schedules_if_due",
        "_process_agent_run_queue_if_due",
        "_process_sheet_provider_queue_if_due",
        "_process_operator_async_job_if_due",
    )

    monkeypatch.setattr(worker, "_worker_role_enabled", lambda _role: True)
    for callback_name in expected:
        monkeypatch.setattr(worker, callback_name, lambda name=callback_name: calls.append(name))

    worker._run_worker_polling_cycle(stop_event)

    assert tuple(calls) == expected


def test_sigterm_and_sigint_request_shutdown_without_raising(monkeypatch, capsys):
    handlers = {}
    stop_event = worker.WorkerStopRequest()

    def register(signum, handler):
        handlers[signum] = handler

    monkeypatch.setattr(worker.signal, "signal", register)

    worker.install_worker_shutdown_handlers(stop_event)

    handlers[signal.SIGTERM](signal.SIGTERM, None)
    handlers[signal.SIGINT](signal.SIGINT, None)

    assert stop_event.is_set() is True
    assert set(handlers) == {signal.SIGTERM, signal.SIGINT}
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_worker_stop_request_polls_idle_wait_in_bounded_intervals(monkeypatch):
    stop_event = worker.WorkerStopRequest()
    clock = [0.0]
    sleeps = []

    def monotonic():
        return clock[0]

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(worker.time, "monotonic", monotonic)
    monkeypatch.setattr(worker.time, "sleep", sleep)

    assert stop_event.wait(0.25) is False
    assert sleeps[:2] == [0.1, 0.1]
    assert round(sleeps[2], 2) == 0.05


def test_worker_stop_request_returns_when_requested_during_idle_wait(monkeypatch):
    stop_event = worker.WorkerStopRequest()
    clock = [0.0]
    sleeps = []

    def monotonic():
        return clock[0]

    def sleep(seconds):
        sleeps.append(seconds)
        stop_event.set()

    monkeypatch.setattr(worker.time, "monotonic", monotonic)
    monkeypatch.setattr(worker.time, "sleep", sleep)

    assert stop_event.wait(10) is True
    assert sleeps == [0.1]
