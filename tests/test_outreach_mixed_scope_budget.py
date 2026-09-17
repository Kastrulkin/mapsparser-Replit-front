"""The complete-window budget covers both native recipient scopes."""

import json

import pytest

from services.outreach_email_adapter import EmailAdapterError
from services.outreach_email_reply_service import sync_email_replies
from tests.test_outreach_email_reply_receipt import _folder, _install_sync_fakes


@pytest.mark.parametrize(
    "author_counts,non_author_counts,requested_limit,expected_ok",
    [
        ((9, 2, 1), (9, 2, 1), 25, True),
        ((9, 2, 1), (9, 2, 1), 24, True),
        ((9, 2, 1), (9, 2, 1), 23, False),
        ((4739, 12, 188), (4739, 12, 188), 5000, False),
        ((4739, 12, 188), (4739, 12, 188), 20000, True),
        ((9900, 99, 1), (9900, 99, 1), 20000, True),
        ((9900, 99, 1), (9900, 99, 2), 20000, False),
        ((9900, 99, 1), (9900, 99, 2), 40000, False),
    ],
)
def test_mixed_recipient_scopes_respect_one_bounded_budget(
    monkeypatch, author_counts, non_author_counts, requested_limit, expected_ok
):
    _fetch_calls, connections, events = _install_sync_fakes(monkeypatch, messages=[])
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_non_author_queue_candidates",
        lambda *_args, **_kwargs: [{
            "id": "existing-sales-thread",
            "recipient_value": "business@example.net",
        }],
    )
    calls = []
    consumed = 0
    effective_limit = min(requested_limit, 20000)
    counts_by_scope = {
        ("author@example.net",): dict(zip(("all", "spam", "trash"), author_counts)),
        ("business@example.net",): dict(zip(("all", "spam", "trash"), non_author_counts)),
    }

    def bounded_fetch(_sender, *, mailbox, recipient_emails, max_messages, **_kwargs):
        nonlocal consumed
        assert max_messages == effective_limit - consumed
        scope = tuple(recipient_emails)
        count = counts_by_scope[scope][mailbox]
        calls.append((scope, mailbox, count, max_messages))
        if count > max_messages:
            raise EmailAdapterError(
                "email_imap_window_limit_exceeded", "Complete window does not fit"
            )
        consumed += count
        return {
            "messages": [],
            "folder": {
                **_folder(mailbox, candidates=count),
                "high_watermark_uid": count + 1,
            },
        }

    monkeypatch.setattr(
        "services.outreach_email_reply_service.fetch_complete_mailbox_window", bounded_fetch
    )
    result = sync_email_replies(
        sender_account_id="sender-1", complete_window_limit=requested_limit
    )

    assert result["success"] is expected_ok
    assert len(events) == 1
    event = events[0]
    assert event["payload"]["message_limit"] == effective_limit
    sync_advanced = any(
        "SET last_reply_sync_at = %s" in query
        for connection in connections
        for query, _params in connection.cursor_instance.executed
    )
    assert sync_advanced is expected_ok
    if expected_ok:
        assert len(calls) == 6
        assert consumed == sum(author_counts) + sum(non_author_counts)
        assert event["event_type"] == "reply_sync_succeeded"
        assert event["payload"]["complete"] is True
        assert event["payload"]["truncated"] is False
        assert event["payload"]["recipient_count"] == 1
        assert event["payload"]["counters"]["candidate_uid_count"] == sum(author_counts)
        assert "business@example.net" not in json.dumps(event["payload"])
    else:
        assert event["event_type"] == "reply_sync_failed"
        assert event["payload"]["complete"] is False
        assert event["payload"]["truncated"] is True
        assert result["sender_results"][0]["error_code"] == "email_imap_window_limit_exceeded"
        assert consumed <= effective_limit
