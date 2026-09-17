from datetime import datetime, timedelta, timezone
import sys

import pytest

from services.outreach_email_adapter import EmailAdapterError, fetch_complete_mailbox_window


NOW = datetime(2026, 9, 7, 11, 0, tzinfo=timezone.utc)


def _sender():
    return {
        "id": "sender-1",
        "scope_type": "platform",
        "business_id": None,
        "channel": "email",
        "sender_identity": "founder@example.org",
        "auth_data_encrypted": "encrypted",
    }


def _metadata(uid, *, inside_window=True):
    date = "07-Sep-2026 10:00:00 +0000" if inside_window else "05-Sep-2026 10:00:00 +0000"
    return f'{uid} (UID {uid} INTERNALDATE "{date}")'.encode()


def _message(uid):
    return (
        b"From: Author <author@example.net>\r\n"
        b"To: Founder <founder@example.org>\r\n"
        b"Date: Mon, 07 Sep 2026 10:00:00 +0000\r\n"
        + f"Message-ID: <reply-{uid}@example.net>\r\n".encode()
        + b"Subject: Re: hello\r\n\r\nInterested"
    )


class _BatchImap:
    def __init__(
        self,
        uids,
        *,
        recipient_uids=(),
        outside_window_uids=(),
        header_fault=None,
        clock=None,
    ):
        self.uids = list(uids)
        self.recipient_uids = set(recipient_uids)
        self.outside_window_uids = set(outside_window_uids)
        self.header_fault = header_fault
        self.clock = clock
        self.header_calls = []
        self.body_calls = []
        self.status_calls = 0

    def list(self):
        return "OK", [b'(\\HasNoChildren \\All) "/" "All Mail"']

    def select(self, folder, readonly=False):
        assert folder == '"All Mail"'
        assert readonly is True
        return "OK", [str(len(self.uids)).encode()]

    def response(self, name):
        if name == "UIDVALIDITY":
            return name, [b"77"]
        return name, [str(max(self.uids, default=0) + 2).encode()]

    def status(self, folder, query):
        assert folder == '"All Mail"'
        assert query == "(UIDVALIDITY)"
        self.status_calls += 1
        return "OK", [b'"All Mail" (UIDVALIDITY 77)']

    def uid(self, command, message_set, *criteria):
        if command == "search":
            return "OK", [" ".join(str(uid) for uid in reversed(self.uids)).encode()]
        raw_message_set = (
            message_set.decode("ascii")
            if isinstance(message_set, bytes)
            else message_set
        )
        requested = [int(value) for value in raw_message_set.split(",")]
        query = criteria[0]
        if "HEADER.FIELDS" in query:
            self.header_calls.append(requested)
            records = [
                (
                    _metadata(uid, inside_window=uid not in self.outside_window_uids),
                    (
                        b"From: Author <author@example.net>\r\n\r\n"
                        if uid in self.recipient_uids
                        else b"From: Private <private@example.net>\r\n\r\n"
                    ),
                )
                for uid in reversed(requested)
            ]
            if self.header_fault == "missing":
                records = records[1:]
            elif self.header_fault == "extra":
                records.append((_metadata(max(self.uids) + 1), b"From: Private <private@example.net>\r\n\r\n"))
            elif self.header_fault == "duplicate":
                records.append(records[0])
            if self.clock is not None:
                self.clock[0] = 2.0
            return "OK", records
        self.body_calls.append(requested)
        return "OK", [
            (_metadata(uid), _message(uid))
            for uid in reversed(requested)
        ]

    def logout(self):
        return None


def _fetch(monkeypatch, client, **kwargs):
    monkeypatch.setattr(
        "services.outreach_email_adapter.load_mailbox_config",
        lambda _sender_account: {},
    )
    monkeypatch.setattr(
        "services.outreach_email_adapter._imap_connection",
        lambda _config, timeout: client,
    )
    return fetch_complete_mailbox_window(
        _sender(),
        mailbox="all",
        since_at=NOW - timedelta(days=1),
        until_at=NOW,
        recipient_emails=["author@example.net"],
        max_messages=20000,
        **kwargs,
    )


def _capture_email_error(callback):
    try:
        callback()
    except EmailAdapterError:
        return sys.exception()
    raise AssertionError("EmailAdapterError was not raised")


def test_complete_window_batches_headers_250_and_sparse_bodies_20_in_uid_order(monkeypatch):
    client = _BatchImap(
        range(1, 504),
        recipient_uids=set(range(1, 22)).union({251, 252, 503}),
        outside_window_uids={252},
    )

    result = _fetch(monkeypatch, client)

    assert [len(batch) for batch in client.header_calls] == [250, 250, 3]
    assert [len(batch) for batch in client.body_calls] == [20, 3]
    assert client.body_calls[0] == list(range(1, 21))
    assert client.body_calls[1] == [21, 251, 503]
    assert [message["mailbox_uid"] for message in result["messages"]] == [
        *[str(uid) for uid in range(1, 22)],
        "251",
        "503",
    ]
    assert result["folder"] == {
        "role": "all",
        "name": "All Mail",
        "uidvalidity": 77,
        "high_watermark_uid": 504,
        "candidate_uid_count": 503,
        "header_checked_uid_count": 503,
        "matched_uid_count": 23,
        "fetched_uid_count": 23,
        "body_checked_uid_count": 23,
        "window_message_count": 23,
        "recipient_scope_count": 1,
    }
    assert client.status_calls == 1


@pytest.mark.parametrize("fault", ["missing", "extra", "duplicate"])
def test_complete_window_fails_closed_on_non_exact_batch_uid_response(monkeypatch, fault):
    client = _BatchImap(range(1, 4), recipient_uids={1}, header_fault=fault)

    error = _capture_email_error(lambda: _fetch(monkeypatch, client))

    assert error.code == "email_imap_fetch_failed"
    assert client.body_calls == []
    assert client.status_calls == 0


def test_complete_window_total_deadline_fails_closed_before_body_fetch(monkeypatch):
    clock = [0.0]
    client = _BatchImap(range(1, 4), recipient_uids={1}, clock=clock)
    monkeypatch.setattr("services.outreach_email_adapter.time.monotonic", lambda: clock[0])

    error = _capture_email_error(
        lambda: _fetch(monkeypatch, client, total_timeout=1)
    )

    assert error.code == "email_imap_deadline_exceeded"
    assert error.retryable is True
    assert client.body_calls == []
    assert client.status_calls == 0
