from __future__ import annotations

import threading

import worker


def test_card_automation_is_cooperatively_capped_with_outreach(monkeypatch):
    monkeypatch.setenv("WORKER_ROLE", "all")
    monkeypatch.setenv("OUTREACH_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("CARD_AUTOMATION_BATCH_SIZE", "20")

    assert worker._card_automation_batch_size() == 1


def test_card_automation_keeps_standalone_default_and_configured_lower(monkeypatch):
    monkeypatch.setenv("WORKER_ROLE", "all")
    monkeypatch.delenv("OUTREACH_DISPATCH_ENABLED", raising=False)
    monkeypatch.delenv("CARD_AUTOMATION_BATCH_SIZE", raising=False)

    assert worker._card_automation_batch_size() == 20

    monkeypatch.setenv("CARD_AUTOMATION_BATCH_SIZE", "7")
    assert worker._card_automation_batch_size() == 7


def test_card_automation_cap_only_applies_to_dispatcher_role(monkeypatch):
    monkeypatch.setenv("WORKER_ROLE", "parser")
    monkeypatch.setenv("OUTREACH_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("CARD_AUTOMATION_BATCH_SIZE", "20")

    assert worker._card_automation_batch_size() == 20


def test_outreach_due_check_precedes_card_automation_in_dispatcher_loop(monkeypatch):
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

    monkeypatch.setattr(worker, "_worker_role_enabled", lambda role: role == "dispatcher")
    for callback_name in dispatcher_callbacks:
        monkeypatch.setattr(worker, callback_name, lambda name=callback_name: calls.append(name))

    worker._run_worker_polling_cycle(threading.Event())

    assert calls.index("_dispatch_outreach_queue_if_due") < calls.index(
        "_run_card_automation_if_due"
    )
    assert calls.index("_prepare_riderra_systematic_outreach_if_due") < calls.index(
        "_dispatch_outreach_queue_if_due"
    )
