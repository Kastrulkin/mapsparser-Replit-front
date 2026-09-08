import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from services.outreach_email_adapter import EmailAdapterError, fetch_complete_mailbox_window
from services.outreach_email_reply_service import (
    _load_non_author_queue_candidates,
    sync_email_replies,
)
from services.outreach_reply_sync_receipt import (
    build_email_reply_sync_receipt,
    load_trusted_email_reply_sync_receipt,
)


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


def _folder(role, *, candidates=0, matched=0):
    return {
        "role": role,
        "name": {"all": "All Mail", "spam": "Spam", "trash": "Trash"}[role],
        "uidvalidity": 77,
        "high_watermark_uid": 10,
        "candidate_uid_count": candidates,
        "header_checked_uid_count": candidates,
        "matched_uid_count": matched,
        "fetched_uid_count": matched,
        "body_checked_uid_count": matched,
        "window_message_count": matched,
        "recipient_scope_count": 1,
    }


def test_imap_overmatch_never_fetches_unrelated_message_body(monkeypatch):
    body_fetch_uids = []
    selected = []
    search_calls = []

    class FakeImap:
        def list(self):
            return "OK", [
                b'(\\HasNoChildren \\All) "/" "All Mail"',
                b'(\\HasNoChildren \\Junk) "/" "Spam"',
                b'(\\HasNoChildren \\Trash) "/" "Trash"',
            ]

        def select(self, folder, readonly=False):
            selected.append((folder, readonly))
            return "OK", [b"2"]

        def response(self, name):
            return name, [b"77" if name == "UIDVALIDITY" else b"3"]

        def status(self, folder, query):
            assert folder == '"All Mail"'
            assert query == "(UIDVALIDITY)"
            return "OK", [b'"All Mail" (UIDVALIDITY 77)']

        def uid(self, command, uid, *criteria):
            if command == "search":
                search_calls.append(criteria)
                return "OK", [b"1 2"]
            query = criteria[0]
            uid_text = uid.decode("ascii")
            metadata = f'{uid_text} (UID {uid_text} INTERNALDATE "07-Sep-2026 10:00:00 +0000")'.encode()
            if "HEADER.FIELDS" in query:
                if uid_text == "1":
                    return "OK", [(metadata, b"From: Author <author@example.net>\r\n\r\n")]
                return "OK", [(
                    metadata,
                    b'From: "author@example.net billing" <private@example.net>\r\n\r\n',
                )]
            body_fetch_uids.append(uid_text)
            message = (
                b"From: Author <author@example.net>\r\n"
                b"To: Founder <founder@example.org>\r\n"
                b"Date: Mon, 07 Sep 2026 10:00:00 +0000\r\n"
                b"Message-ID: <reply-1@example.net>\r\n"
                b"Subject: Re: hello\r\n\r\nInterested"
            )
            return "OK", [(metadata, message)]

        def logout(self):
            return None

    monkeypatch.setattr(
        "services.outreach_email_adapter.load_mailbox_config",
        lambda _sender: {"imap_folder": "INBOX"},
    )
    monkeypatch.setattr(
        "services.outreach_email_adapter._imap_connection",
        lambda _config, timeout: FakeImap(),
    )

    result = fetch_complete_mailbox_window(
        _sender(),
        mailbox="all",
        since_at=NOW - timedelta(days=1),
        until_at=NOW,
        recipient_emails=[" Author@Example.NET "],
        max_messages=10,
    )

    assert selected == [('"All Mail"', True)]
    assert search_calls == [("UID", "1:2", "SINCE", "06-Sep-2026")]
    assert body_fetch_uids == ["1"]
    assert [message["from_email"] for message in result["messages"]] == ["author@example.net"]
    assert result["folder"]["candidate_uid_count"] == 2
    assert result["folder"]["header_checked_uid_count"] == 2
    assert result["folder"]["matched_uid_count"] == 1
    assert result["folder"]["fetched_uid_count"] == 1
    assert result["folder"]["body_checked_uid_count"] == 1


def test_complete_window_includes_mailer_daemon_dsn_for_exact_original_recipient(monkeypatch):
    body_fetch_uids = []

    class FakeImap:
        def list(self):
            return "OK", [
                b'(\\HasNoChildren \\All) "/" "All Mail"',
                b'(\\HasNoChildren \\Junk) "/" "Spam"',
                b'(\\HasNoChildren \\Trash) "/" "Trash"',
            ]

        def select(self, _folder, readonly=False):
            return "OK", [b"2"]

        def response(self, name):
            return name, [b"77" if name == "UIDVALIDITY" else b"3"]

        def status(self, folder, query):
            assert folder == '"All Mail"'
            assert query == "(UIDVALIDITY)"
            return "OK", [b'"All Mail" (UIDVALIDITY 77)']

        def uid(self, command, uid, *criteria):
            if command == "search":
                return "OK", [b"1 2"]
            uid_text = uid.decode("ascii")
            metadata = f'{uid_text} (UID {uid_text} INTERNALDATE "07-Sep-2026 10:00:00 +0000")'.encode()
            if "HEADER.FIELDS" in criteria[0]:
                if uid_text == "1":
                    return "OK", [(
                        metadata,
                        b"From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>\r\n"
                        b"Subject: Delivery Status Notification (Failure)\r\n"
                        b"Auto-Submitted: auto-replied\r\n"
                        b"Content-Type: multipart/report; report-type=delivery-status; boundary=dsn\r\n\r\n",
                    )]
                return "OK", [(
                    metadata,
                    b"From: Other <other@example.org>\r\nSubject: unrelated\r\n\r\n",
                )]
            body_fetch_uids.append(uid_text)
            raw = (
                b"From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>\r\n"
                b"To: Founder <founder@example.org>\r\n"
                b"Date: Mon, 07 Sep 2026 10:00:00 +0000\r\n"
                b"Message-ID: <dsn-1@googlemail.com>\r\n"
                b"Subject: Delivery Status Notification (Failure)\r\n"
                b"Auto-Submitted: auto-replied\r\n"
                b"Content-Type: multipart/report; report-type=delivery-status; boundary=dsn\r\n\r\n"
                b"--dsn\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nAddress rejected\r\n"
                b"--dsn\r\nContent-Type: message/delivery-status\r\n\r\n"
                b"Final-Recipient: rfc822; author@example.net\r\n"
                b"Action: failed\r\nStatus: 5.1.1\r\n"
                b"Original-Message-ID: <outbound-1@localos.pro>\r\n\r\n"
                b"--dsn--\r\n"
            )
            return "OK", [(metadata, raw)]

        def logout(self):
            return None

    monkeypatch.setattr(
        "services.outreach_email_adapter.load_mailbox_config",
        lambda _sender: {"imap_folder": "INBOX"},
    )
    monkeypatch.setattr(
        "services.outreach_email_adapter._imap_connection",
        lambda _config, timeout: FakeImap(),
    )

    result = fetch_complete_mailbox_window(
        _sender(),
        mailbox="all",
        since_at=NOW - timedelta(days=1),
        until_at=NOW,
        recipient_emails=["author@example.net"],
        max_messages=10,
    )

    assert body_fetch_uids == ["1"]
    assert len(result["messages"]) == 1
    message = result["messages"][0]
    assert message["from_email"] == "mailer-daemon@googlemail.com"
    assert message["dsn_recipient_emails"] == ["author@example.net"]
    assert message["dsn_original_message_ids"] == ["<outbound-1@localos.pro>"]
    assert message["dsn_classification"] == "permanent_delivery_failure"
    assert result["folder"]["candidate_uid_count"] == 2
    assert result["folder"]["header_checked_uid_count"] == 2
    assert result["folder"]["matched_uid_count"] == 1
    assert result["folder"]["body_checked_uid_count"] == 1


def test_complete_window_fails_closed_on_unparseable_potential_dsn(monkeypatch):
    class FakeImap:
        def list(self):
            return "OK", [b'(\\HasNoChildren \\All) "/" "All Mail"']

        def select(self, _folder, readonly=False):
            return "OK", [b"1"]

        def response(self, name):
            return name, [b"77" if name == "UIDVALIDITY" else b"2"]

        def uid(self, command, uid, *criteria):
            if command == "search":
                return "OK", [b"1"]
            metadata = b'1 (UID 1 INTERNALDATE "07-Sep-2026 10:00:00 +0000")'
            if "HEADER.FIELDS" in criteria[0]:
                return "OK", [(
                    metadata,
                    b"From: Mailer Daemon <mailer-daemon@example.org>\r\n"
                    b"Subject: Delivery report\r\n\r\n",
                )]
            return "OK", [(
                metadata,
                b"From: Mailer Daemon <mailer-daemon@example.org>\r\n"
                b"To: Founder <founder@example.org>\r\n"
                b"Date: Mon, 07 Sep 2026 10:00:00 +0000\r\n"
                b"Message-ID: <ambiguous-dsn@example.org>\r\n"
                b"Subject: Delivery report\r\n\r\n"
                b"No machine-readable delivery status is present.\r\n",
            )]

        def logout(self):
            return None

    monkeypatch.setattr(
        "services.outreach_email_adapter.load_mailbox_config",
        lambda _sender: {"imap_folder": "INBOX"},
    )
    monkeypatch.setattr(
        "services.outreach_email_adapter._imap_connection",
        lambda _config, timeout: FakeImap(),
    )

    with pytest.raises(EmailAdapterError) as exc_info:
        fetch_complete_mailbox_window(
            _sender(),
            mailbox="all",
            since_at=NOW - timedelta(days=1),
            until_at=NOW,
            recipient_emails=["author@example.net"],
            max_messages=10,
        )

    assert exc_info.value.code == "email_imap_dsn_scope_unverified"


def test_complete_window_quotes_gmail_special_use_folder_with_spaces(monkeypatch):
    selected = []

    class FakeImap:
        def list(self):
            return "OK", [b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"']

        def select(self, folder, readonly=False):
            selected.append((folder, readonly))
            assert folder == '"[Gmail]/All Mail"'
            return "OK", [b"0"]

        def response(self, name):
            return name, [b"77" if name == "UIDVALIDITY" else b"1"]

        def status(self, folder, query):
            assert folder == '"[Gmail]/All Mail"'
            assert query == "(UIDVALIDITY)"
            return "OK", [b'"[Gmail]/All Mail" (UIDVALIDITY 77)']

        def logout(self):
            return None

    monkeypatch.setattr("services.outreach_email_adapter.load_mailbox_config", lambda _sender: {})
    monkeypatch.setattr("services.outreach_email_adapter._imap_connection", lambda _config, timeout: FakeImap())

    result = fetch_complete_mailbox_window(
        _sender(), mailbox="all", since_at=NOW - timedelta(days=1), until_at=NOW,
        recipient_emails=["author@example.net"], max_messages=10,
    )

    assert selected == [('"[Gmail]/All Mail"', True)]
    assert result["folder"]["window_message_count"] == 0


def test_complete_window_uses_status_for_final_uidvalidity_after_response_is_consumed(monkeypatch):
    responses = {"UIDVALIDITY": [b"77"], "UIDNEXT": [b"1"]}

    class FakeImap:
        def list(self):
            return "OK", [b'(\\HasNoChildren \\Junk) "/" "Spam"']

        def select(self, _folder, readonly=False):
            return "OK", [b"0"]

        def response(self, name):
            return name, responses.pop(name, None)

        def status(self, folder, query):
            assert folder == "Spam"
            assert query == "(UIDVALIDITY)"
            return "OK", [b'Spam (UIDVALIDITY 77)']

        def logout(self):
            return None

    monkeypatch.setattr("services.outreach_email_adapter.load_mailbox_config", lambda _sender: {})
    monkeypatch.setattr("services.outreach_email_adapter._imap_connection", lambda _config, timeout: FakeImap())

    result = fetch_complete_mailbox_window(
        _sender(), mailbox="spam", since_at=NOW - timedelta(days=1), until_at=NOW,
        recipient_emails=["author@example.net"], max_messages=10,
    )

    assert result["folder"]["uidvalidity"] == 77


def test_complete_window_still_fails_closed_when_status_uidvalidity_changes(monkeypatch):
    class FakeImap:
        def list(self):
            return "OK", [b'(\\HasNoChildren \\Junk) "/" "Spam"']

        def select(self, _folder, readonly=False):
            return "OK", [b"0"]

        def response(self, name):
            return name, [b"77" if name == "UIDVALIDITY" else b"1"]

        def status(self, _folder, _query):
            return "OK", [b'Spam (UIDVALIDITY 78)']

        def logout(self):
            return None

    monkeypatch.setattr("services.outreach_email_adapter.load_mailbox_config", lambda _sender: {})
    monkeypatch.setattr("services.outreach_email_adapter._imap_connection", lambda _config, timeout: FakeImap())

    with pytest.raises(EmailAdapterError) as exc_info:
        fetch_complete_mailbox_window(
            _sender(), mailbox="spam", since_at=NOW - timedelta(days=1), until_at=NOW,
            recipient_emails=["author@example.net"], max_messages=10,
        )

    assert exc_info.value.code == "email_imap_uidvalidity_changed"


def test_complete_inbox_window_applies_recipient_scope_before_body_fetch(monkeypatch):
    body_fetch_uids = []

    class FakeImap:
        def select(self, folder, readonly=False):
            assert folder == "INBOX"
            return "OK", [b"2"]

        def response(self, name):
            return name, [b"77" if name == "UIDVALIDITY" else b"3"]

        def status(self, folder, query):
            return "OK", [b'INBOX (UIDVALIDITY 77)']

        def uid(self, command, uid, *criteria):
            if command == "search":
                return "OK", [b"1 2"]
            uid_text = uid.decode("ascii")
            metadata = f'{uid_text} (UID {uid_text} INTERNALDATE "07-Sep-2026 10:00:00 +0000")'.encode()
            if "HEADER.FIELDS" in criteria[0]:
                from_email = "author@example.net" if uid_text == "1" else "private@example.net"
                return "OK", [(metadata, f"From: <{from_email}>\r\n\r\n".encode())]
            body_fetch_uids.append(uid_text)
            return "OK", [(metadata, (
                b"From: Author <author@example.net>\r\nTo: Founder <founder@example.org>\r\n"
                b"Date: Mon, 07 Sep 2026 10:00:00 +0000\r\nMessage-ID: <reply@example.net>\r\n\r\nInterested"
            ))]

        def logout(self):
            return None

    monkeypatch.setattr("services.outreach_email_adapter.load_mailbox_config", lambda _sender: {"imap_folder": "INBOX"})
    monkeypatch.setattr("services.outreach_email_adapter._imap_connection", lambda _config, timeout: FakeImap())

    result = fetch_complete_mailbox_window(
        _sender(), mailbox="inbox", since_at=NOW - timedelta(days=1), until_at=NOW,
        recipient_emails=["author@example.net"], max_messages=10,
    )

    assert body_fetch_uids == ["1"]
    assert [message["from_email"] for message in result["messages"]] == ["author@example.net"]


def test_complete_sent_window_scopes_outbound_messages_by_to_header(monkeypatch):
    body_fetch_uids = []

    class FakeImap:
        def list(self):
            return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

        def select(self, folder, readonly=False):
            assert folder == '"[Gmail]/Sent Mail"'
            return "OK", [b"2"]

        def response(self, name):
            return name, [b"77" if name == "UIDVALIDITY" else b"3"]

        def status(self, folder, query):
            assert folder == '"[Gmail]/Sent Mail"'
            return "OK", [b'"[Gmail]/Sent Mail" (UIDVALIDITY 77)']

        def uid(self, command, uid, *criteria):
            if command == "search":
                return "OK", [b"1 2"]
            uid_text = uid.decode("ascii")
            metadata = f'{uid_text} (UID {uid_text} INTERNALDATE "07-Sep-2026 10:00:00 +0000")'.encode()
            if "HEADER.FIELDS" in criteria[0]:
                to_email = "author@example.net" if uid_text == "1" else "private@example.net"
                return "OK", [(metadata, f"From: Founder <founder@example.org>\r\nTo: <{to_email}>\r\n\r\n".encode())]
            body_fetch_uids.append(uid_text)
            return "OK", [(metadata, (
                b"From: Founder <founder@example.org>\r\nTo: Author <author@example.net>\r\n"
                b"Date: Mon, 07 Sep 2026 10:00:00 +0000\r\nMessage-ID: <sent@example.org>\r\n\r\nHello"
            ))]

        def logout(self):
            return None

    monkeypatch.setattr("services.outreach_email_adapter.load_mailbox_config", lambda _sender: {})
    monkeypatch.setattr("services.outreach_email_adapter._imap_connection", lambda _config, timeout: FakeImap())

    result = fetch_complete_mailbox_window(
        _sender(), mailbox="sent", since_at=NOW - timedelta(days=1), until_at=NOW,
        recipient_emails=["author@example.net"], max_messages=10,
    )

    assert body_fetch_uids == ["1"]
    assert result["messages"][0]["to_emails"] == ["author@example.net"]


class _ReceiptCursor:
    def __init__(self, sender, event):
        self.rows = [sender, event]

    def execute(self, _query, _params):
        return None

    def fetchone(self):
        return self.rows.pop(0)


def test_receipt_is_hashed_current_complete_and_latest_failure_wins(monkeypatch):
    monkeypatch.setattr(
        "services.outreach_reply_sync_receipt.mailbox_identity_fingerprint",
        lambda _sender: "mailbox-identity",
    )
    folders = [_folder("all"), _folder("spam"), _folder("trash")]
    receipt = build_email_reply_sync_receipt(
        _sender(),
        recipient_emails=["author@example.net"],
        sync_started_at=NOW,
        window_started_at=NOW - timedelta(days=45, minutes=10),
        covered_through=NOW,
        completed_at=NOW + timedelta(seconds=1),
        folders=folders,
        message_limit=5000,
        counters={"imported": 0, "duplicates": 0, "unmatched": 0},
    )
    serialized = json.dumps(receipt)

    assert receipt["receipt_version"] == 2
    assert "author@example.net" not in serialized
    assert receipt["recipient_count"] == 1
    assert receipt["counters"]["matched_uid_count"] == 0
    assert receipt["counters"]["fetched_uid_count"] == 0

    success_event = {
        "id": "event-1",
        "event_type": "reply_sync_succeeded",
        "payload_json": receipt,
        "created_at": NOW + timedelta(seconds=1),
    }
    trusted = load_trusted_email_reply_sync_receipt(
        _ReceiptCursor(_sender(), success_event),
        "sender-1",
        required_recipient_emails=["AUTHOR@example.net"],
        required_covered_through=NOW,
        max_age_seconds=120,
        now=NOW + timedelta(seconds=2),
    )
    missing_recipient = load_trusted_email_reply_sync_receipt(
        _ReceiptCursor(_sender(), success_event),
        "sender-1",
        required_recipient_emails=["different@example.net"],
        now=NOW + timedelta(seconds=2),
    )
    newer_failure = load_trusted_email_reply_sync_receipt(
        _ReceiptCursor(_sender(), {
            "id": "event-2",
            "event_type": "reply_sync_failed",
            "payload_json": {"receipt_version": 2},
            "created_at": NOW + timedelta(seconds=2),
        }),
        "sender-1",
        required_recipient_emails=["author@example.net"],
        now=NOW + timedelta(seconds=3),
    )
    short_window_payload = copy.deepcopy(receipt)
    short_window_payload["window_started_at"] = (NOW - timedelta(seconds=1)).isoformat()
    short_window = load_trusted_email_reply_sync_receipt(
        _ReceiptCursor(_sender(), {**success_event, "payload_json": short_window_payload}),
        "sender-1",
        required_recipient_emails=["author@example.net"],
        now=NOW + timedelta(seconds=2),
    )
    duplicate_folder_payload = copy.deepcopy(receipt)
    duplicate_folder_payload["folders"][1]["name"] = duplicate_folder_payload["folders"][0]["name"]
    duplicate_folder = load_trusted_email_reply_sync_receipt(
        _ReceiptCursor(_sender(), {**success_event, "payload_json": duplicate_folder_payload}),
        "sender-1",
        required_recipient_emails=["author@example.net"],
        now=NOW + timedelta(seconds=2),
    )
    over_cap_payload = copy.deepcopy(receipt)
    over_cap_payload["message_limit"] = 1
    over_cap_payload["folders"][0]["candidate_uid_count"] = 2
    over_cap_payload["folders"][0]["header_checked_uid_count"] = 2
    over_cap_payload["counters"]["candidate_uid_count"] = 2
    over_cap_payload["counters"]["header_checked_uid_count"] = 2
    over_cap = load_trusted_email_reply_sync_receipt(
        _ReceiptCursor(_sender(), {**success_event, "payload_json": over_cap_payload}),
        "sender-1",
        required_recipient_emails=["author@example.net"],
        now=NOW + timedelta(seconds=2),
    )

    assert trusted == receipt
    assert missing_recipient is None
    assert newer_failure is None
    assert short_window is None
    assert duplicate_folder is None
    assert over_cap is None


class _DbCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query, params):
        self.executed.append((query, params))


class _DbConnection:
    def __init__(self):
        self.cursor_instance = _DbCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        return None


def test_non_author_scope_keeps_old_sent_conversations_but_is_bounded(monkeypatch):
    class CandidateCursor:
        def __init__(self):
            self.query = ""

        def execute(self, query, _params):
            self.query = query

        def fetchall(self):
            return [{
                "id": "old-sales-touch",
                "recipient_value": "business@example.net",
                "sent_at": NOW - timedelta(days=180),
            }]

    cursor = CandidateCursor()

    class CandidateConnection:
        def cursor(self):
            return cursor

        def close(self):
            return None

    monkeypatch.setattr(
        "services.outreach_email_reply_service.get_db_connection",
        lambda: CandidateConnection(),
    )

    candidates = _load_non_author_queue_candidates("sender-1")

    assert candidates[0]["id"] == "old-sales-touch"
    assert "q.sent_at >=" not in cursor.query
    assert "LIMIT 1001" in cursor.query


def _install_sync_fakes(monkeypatch, *, messages, messages_by_recipient=None):
    sender = _sender()
    sender.update({"status": "connected", "outreach_enabled": True})
    connections = []
    events = []
    fetch_calls = []
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_email_senders",
        lambda *_args, **_kwargs: [sender],
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_email_reply_scope_candidates",
        lambda *_args, **_kwargs: [{
            "id": "queue-new",
            "delivery_status": "queued",
            "sent_at": None,
            "recipient_value": "author@example.net",
        }],
    )

    def fake_fetch(_sender, *, mailbox, recipient_emails, **_kwargs):
        fetch_calls.append((mailbox, recipient_emails))
        scoped_messages = (
            (messages_by_recipient or {}).get(tuple(recipient_emails), messages)
        )
        role_messages = scoped_messages if mailbox == "all" else []
        return {
            "messages": role_messages,
            "folder": {
                **_folder(mailbox, candidates=len(role_messages), matched=len(role_messages)),
                "recipient_scope_count": len(recipient_emails),
            },
        }

    monkeypatch.setattr(
        "services.outreach_email_reply_service.fetch_complete_mailbox_window",
        fake_fetch,
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._sync_known_email_threads",
        lambda *_args, **_kwargs: {
            "bound": 0,
            "imported": 0,
            "duplicates": 0,
            "processed_event_ids": set(),
        },
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_queue_candidates",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_non_author_queue_candidates",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service.mailbox_identity_fingerprint",
        lambda _sender: "mailbox-identity",
    )
    monkeypatch.setattr(
        "services.outreach_reply_sync_receipt.mailbox_identity_fingerprint",
        lambda _sender: "mailbox-identity",
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._record_sender_sync_event",
        lambda _cursor, **kwargs: events.append(kwargs),
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service.record_sender_health_event",
        lambda *_args, **_kwargs: None,
    )

    def connection_factory():
        connection = _DbConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(
        "services.outreach_email_reply_service.get_db_connection",
        connection_factory,
    )
    return fetch_calls, connections, events


def test_clean_first_contact_scope_checks_all_special_folders_and_records_zero_receipt(monkeypatch):
    fetch_calls, connections, events = _install_sync_fakes(monkeypatch, messages=[])

    result = sync_email_replies(sender_account_id="sender-1")

    assert result["success"] is True
    assert fetch_calls == [
        ("all", ["author@example.net"]),
        ("spam", ["author@example.net"]),
        ("trash", ["author@example.net"]),
    ]
    assert events[0]["event_type"] == "reply_sync_succeeded"
    assert events[0]["payload"]["recipient_count"] == 1
    assert events[0]["payload"]["counters"]["matched_uid_count"] == 0
    assert any("SET last_reply_sync_at = %s" in query for query, _params in connections[0].cursor_instance.executed)


def test_unmatched_exact_scoped_message_records_failure_and_does_not_advance_sync(monkeypatch):
    message = {
        "provider_event_id": "email:sender-1:all:1",
        "message_id": "<incoming@example.net>",
        "from_email": "author@example.net",
        "body": "Hello",
        "occurred_at": NOW,
    }
    _fetch_calls, connections, events = _install_sync_fakes(monkeypatch, messages=[message])

    result = sync_email_replies(sender_account_id="sender-1")

    assert result["success"] is False
    assert result["sender_results"][0]["error_code"] == "email_reply_unmatched_scoped_message"
    assert events[0]["event_type"] == "reply_sync_failed"
    executed_sql = [query for connection in connections for query, _params in connection.cursor_instance.executed]
    assert not any("SET last_reply_sync_at = %s" in query for query in executed_sql)


def test_non_author_sender_keeps_legacy_reply_import_path(monkeypatch):
    legacy_calls = []
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_email_senders",
        lambda *_args, **_kwargs: [_sender()],
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_email_reply_scope_candidates",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._sync_legacy_non_author_sender",
        lambda *_args, **kwargs: legacy_calls.append(kwargs) or {
            "fetched": 1,
            "matched": 1,
            "imported": 1,
            "technical": 0,
            "duplicates": 0,
            "unmatched": 0,
            "failed": 0,
            "bound": 0,
        },
    )

    result = sync_email_replies(sender_account_id="sender-non-author")

    assert result["success"] is True
    assert result["sender_results"] == [{
        "sender_account_id": "sender-1",
        "status": "ok",
        "scope": "legacy_non_author",
        "fetched": 1,
        "imported": 1,
    }]
    assert legacy_calls == [{"campaign_id": None, "limit": 100}]


def test_mixed_sender_syncs_author_receipt_and_non_author_reply_in_separate_scopes(monkeypatch):
    business_reply = {
        "provider_event_id": "email:sender-1:all:2",
        "message_id": "<business-reply@example.net>",
        "from_email": "business@example.net",
        "body": "Interested",
        "occurred_at": NOW,
    }
    fetch_calls, connections, events = _install_sync_fakes(
        monkeypatch,
        messages=[],
        messages_by_recipient={
            ("author@example.net",): [],
            ("business@example.net",): [business_reply],
        },
    )
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_non_author_queue_candidates",
        lambda *_args, **_kwargs: [{
            "id": "existing-sales-thread",
            "recipient_value": "business@example.net",
        }],
    )
    known_thread_calls = []

    def sync_known_threads(_sender, *, sent_messages, inbox_messages):
        known_thread_calls.append((sent_messages, inbox_messages))
        processed = {
            message["provider_event_id"]
            for message in inbox_messages
            if message.get("from_email") == "business@example.net"
        }
        return {
            "bound": 0,
            "imported": len(processed),
            "duplicates": 0,
            "processed_event_ids": processed,
        }

    monkeypatch.setattr(
        "services.outreach_email_reply_service._sync_known_email_threads",
        sync_known_threads,
    )

    result = sync_email_replies(sender_account_id="sender-1")

    assert result["success"] is True
    assert fetch_calls == [
        ("all", ["author@example.net"]),
        ("spam", ["author@example.net"]),
        ("trash", ["author@example.net"]),
        ("all", ["business@example.net"]),
        ("spam", ["business@example.net"]),
        ("trash", ["business@example.net"]),
    ]
    assert known_thread_calls == [([], [business_reply])]
    assert result["imported"] == 1
    assert result["sender_results"][0]["scope"] == "author_and_non_author_scoped"
    assert result["sender_results"][0]["author_recipient_count"] == 1
    assert result["sender_results"][0]["non_author_recipient_count"] == 1
    assert events[0]["event_type"] == "reply_sync_succeeded"
    assert events[0]["payload"]["recipient_count"] == 1
    assert "business@example.net" not in json.dumps(events[0]["payload"])
    assert any(
        "SET last_reply_sync_at = %s" in query
        for connection in connections
        for query, _params in connection.cursor_instance.executed
    )


def test_mixed_sender_non_author_read_failure_invalidates_author_receipt(monkeypatch):
    _fetch_calls, connections, events = _install_sync_fakes(monkeypatch, messages=[])
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_non_author_queue_candidates",
        lambda *_args, **_kwargs: [{
            "id": "existing-sales-thread",
            "recipient_value": "business@example.net",
        }],
    )

    def fail_non_author_fetch(_sender, *, mailbox, recipient_emails, **_kwargs):
        if recipient_emails == ["business@example.net"]:
            raise EmailAdapterError("email_imap_search_failed", "search failed")
        return {"messages": [], "folder": _folder(mailbox)}

    monkeypatch.setattr(
        "services.outreach_email_reply_service.fetch_complete_mailbox_window",
        fail_non_author_fetch,
    )

    result = sync_email_replies(sender_account_id="sender-1")

    assert result["success"] is False
    assert result["sender_results"][0]["error_code"] == "email_imap_search_failed"
    assert [event["event_type"] for event in events] == ["reply_sync_failed"]
    assert events[0]["payload"]["recipient_count"] == 1
    assert events[0]["payload"]["complete"] is False
    assert not any(
        "SET last_reply_sync_at = %s" in query
        for connection in connections
        for query, _params in connection.cursor_instance.executed
    )


def test_mixed_sender_rejects_recipient_shared_by_author_and_sales_before_provider_read(monkeypatch):
    fetch_calls, _connections, events = _install_sync_fakes(monkeypatch, messages=[])
    monkeypatch.setattr(
        "services.outreach_email_reply_service._load_non_author_queue_candidates",
        lambda *_args, **_kwargs: [{
            "id": "existing-sales-thread",
            "recipient_value": "AUTHOR@example.net",
        }],
    )

    result = sync_email_replies(sender_account_id="sender-1")

    assert result["success"] is False
    assert result["sender_results"][0]["error_code"] == "email_reply_sync_recipient_scope_overlap"
    assert fetch_calls == []
    assert [event["event_type"] for event in events] == ["reply_sync_failed"]
