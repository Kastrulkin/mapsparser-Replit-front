from pathlib import Path


def test_telegram_reply_sync_reports_only_server_verified_sender_scope(monkeypatch):
    from api import admin_prospecting

    audit_generation = admin_prospecting

    monkeypatch.setattr(
        audit_generation,
        "_load_telegram_reply_sync_candidates",
        lambda **_kwargs: [{
            "id": "queue-1",
            "lead_id": "lead-1",
            "lead_name": "Creator",
            "sender_account_id": "sender-telegram",
            "provider_account_id": "external-telegram",
            "sender_external_account_id": "external-telegram",
            "sender_external_account_source": "telegram_app",
        }],
    )
    monkeypatch.setattr(
        audit_generation,
        "_sync_telegram_app_replies_for_queue_item",
        lambda _item: {
            "status": "failed",
            "reason": "telegram_sync_failed",
            "sender_account_id": "untrusted-result-value",
            "imported": 0,
            "duplicates": 0,
        },
    )

    result = audit_generation._sync_telegram_app_replies(limit=1)

    assert result["failed"] == 1
    assert result["results"][0]["sender_account_id"] == "sender-telegram"
    assert result["sender_results"] == [{
        "sender_account_id": "sender-telegram",
        "status": "failed",
        "error_code": "telegram_sync_failed",
    }]


def test_telegram_reply_sync_does_not_scope_mismatched_provider_account(monkeypatch):
    from api import admin_prospecting

    audit_generation = admin_prospecting

    item = {
        "id": "queue-1",
        "sender_account_id": "sender-telegram",
        "provider_account_id": "external-other",
        "sender_external_account_id": "external-telegram",
        "sender_external_account_source": "telegram_app",
    }
    monkeypatch.setattr(
        audit_generation,
        "_load_telegram_reply_sync_candidates",
        lambda **_kwargs: [item],
    )

    result = audit_generation._sync_telegram_app_replies(limit=1)

    assert result["failed"] == 1
    assert result["results"][0]["reason"] == "telegram_sender_scope_unverified"
    assert result["results"][0]["sender_account_id"] is None
    assert result["sender_results"][0]["sender_account_id"] is None


def test_telegram_reply_sync_does_not_scope_missing_or_wrong_channel_identity():
    from api import admin_prospecting

    audit_generation = admin_prospecting

    base = {
        "sender_account_id": "sender-telegram",
        "provider_account_id": "external-telegram",
        "sender_external_account_id": "external-telegram",
        "sender_external_account_source": "telegram_app",
    }

    assert audit_generation._trusted_telegram_reply_sender_account_id(base) == "sender-telegram"
    for unsafe in (
        {**base, "sender_account_id": ""},
        {**base, "provider_account_id": ""},
        {**base, "sender_external_account_id": ""},
        {**base, "sender_external_account_source": "email"},
    ):
        assert audit_generation._trusted_telegram_reply_sender_account_id(unsafe) is None


def test_telegram_queue_candidates_select_trusted_sender_identity():
    source = Path("src/api/prospecting/audit_generation.py").read_text(encoding="utf-8")
    start = source.index("def _load_telegram_reply_sync_candidates(")
    end = source.index("\ndef _sync_telegram_app_replies_for_queue_item(", start)
    loader = source[start:end]

    assert "q.sender_account_id," in loader
    assert "sender.external_account_id AS sender_external_account_id" in loader
    assert "account.source AS sender_external_account_source" in loader


def test_known_telegram_failure_blocks_only_that_sender_and_keeps_fresh_email_eligible():
    import worker

    scope = worker._classify_reply_sync_failures((
        {
            "failed": 1,
            "sender_results": [{
                "sender_account_id": "sender-telegram",
                "status": "failed",
            }],
        },
        {
            "failed": 0,
            "sender_results": [{
                "sender_account_id": "sender-email",
                "status": "ok",
                "receipt_complete": True,
            }],
        },
        {"failed": 0, "sender_results": []},
    ))

    assert scope == {
        "failed": 1,
        "blocked_sender_ids": ["sender-telegram"],
        "has_unscoped_failures": False,
    }


def test_worker_applies_known_telegram_failure_as_sender_only_block(monkeypatch):
    import worker
    from api import admin_prospecting
    from services import outreach_email_reply_service, outreach_vk_reply_service

    monkeypatch.setattr(
        admin_prospecting,
        "_sync_telegram_app_replies",
        lambda **_kwargs: {
            "picked": 1,
            "imported": 0,
            "failed": 1,
            "sender_results": [{
                "sender_account_id": "sender-telegram",
                "status": "failed",
            }],
        },
    )
    monkeypatch.setattr(
        outreach_email_reply_service,
        "sync_email_replies",
        lambda **_kwargs: {
            "picked": 1,
            "imported": 0,
            "failed": 0,
            "sender_results": [{
                "sender_account_id": "sender-email",
                "status": "ok",
                "receipt_complete": True,
            }],
        },
    )
    monkeypatch.setattr(
        outreach_vk_reply_service,
        "sync_vk_replies",
        lambda **_kwargs: {
            "picked": 0,
            "imported": 0,
            "failed": 0,
            "sender_results": [],
        },
    )
    monkeypatch.setattr(worker.time, "time", lambda: 10_000.0)
    monkeypatch.setenv("OUTREACH_REPLY_SYNC_FAIL_CLOSED", "true")
    monkeypatch.setenv("OUTREACH_YOUGILE_SYNC_ENABLED", "false")
    worker._LAST_OUTREACH_REPLY_SYNC_AT = 0.0

    state = worker._sync_outreach_replies_if_due()

    assert state["healthy"] is False
    assert state["global_block"] is False
    assert state["blocked_sender_ids"] == ["sender-telegram"]


def test_unknown_reply_sync_failure_remains_globally_fail_closed():
    import worker

    scope = worker._classify_reply_sync_failures((
        {"failed": 1, "sender_results": []},
    ))

    assert scope["failed"] == 1
    assert scope["blocked_sender_ids"] == []
    assert scope["has_unscoped_failures"] is True


def test_reply_sync_failure_count_and_identity_mismatches_remain_unscoped():
    import worker

    cases = (
        {"failed": 0, "sender_results": [{"sender_account_id": "sender-1", "status": "failed"}]},
        {"failed": 2, "sender_results": [{"sender_account_id": "sender-1", "status": "failed"}]},
        {"failed": 1, "sender_results": [{"sender_account_id": "", "status": "failed"}]},
        {"failed": "1", "sender_results": [{"sender_account_id": "sender-1", "status": "failed"}]},
        {"failed": True, "sender_results": [{"sender_account_id": "sender-1", "status": "failed"}]},
        {"failed": 1.5, "sender_results": [{"sender_account_id": "sender-1", "status": "failed"}]},
        {"sender_results": []},
    )

    for result in cases:
        scope = worker._classify_reply_sync_failures((result,))
        assert scope["has_unscoped_failures"] is True
