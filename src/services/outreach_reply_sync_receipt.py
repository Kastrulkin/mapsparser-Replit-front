from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from services.outreach_email_adapter import (
    COMPLETE_REPLY_MAILBOX_ROLES,
    EmailAdapterError,
    email_recipient_hashes,
    email_recipient_scope_fingerprint,
    email_recipient_scope_fingerprint_from_hashes,
    mailbox_identity_fingerprint,
)


EMAIL_REPLY_SYNC_RECEIPT_VERSION = 2
EMAIL_REPLY_SYNC_SCOPE = "authorized_recipient_all_junk_trash_window"
EMAIL_REPLY_SYNC_PROVIDER = "native_smtp_imap"
EMAIL_REPLY_SYNC_LOOKBACK = timedelta(days=45, minutes=10)
EMAIL_REPLY_SYNC_MAX_LOOKBACK = timedelta(days=46)
EMAIL_REPLY_SYNC_MAX_MESSAGE_LIMIT = 20000


def _dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sender_scope(sender_account: dict[str, Any]) -> tuple[str, str | None]:
    scope_type = str(sender_account.get("scope_type") or "").strip()
    business_id = str(sender_account.get("business_id") or "").strip() or None
    return scope_type, business_id


def build_email_reply_sync_receipt(
    sender_account: dict[str, Any],
    *,
    recipient_emails: list[str],
    sync_started_at: datetime,
    window_started_at: datetime,
    covered_through: datetime,
    completed_at: datetime,
    folders: list[dict[str, Any]],
    counters: dict[str, int],
    message_limit: int,
) -> dict[str, Any]:
    recipient_hashes = email_recipient_hashes(recipient_emails)
    sender_scope_type, sender_business_id = _sender_scope(sender_account)
    aggregate_keys = (
        "candidate_uid_count",
        "header_checked_uid_count",
        "matched_uid_count",
        "fetched_uid_count",
        "body_checked_uid_count",
    )
    receipt_counters = {key: int(value) for key, value in counters.items()}
    receipt_counters.update({
        key: sum(int(folder.get(key) or 0) for folder in folders)
        for key in aggregate_keys
    })
    safe_message_limit = int(message_limit)
    if (
        safe_message_limit < 1
        or safe_message_limit > EMAIL_REPLY_SYNC_MAX_MESSAGE_LIMIT
        or not _folder_receipt_valid(folders, len(recipient_hashes))
        or not _receipt_counters_valid(receipt_counters, folders)
        or receipt_counters["candidate_uid_count"] > safe_message_limit
        or sync_started_at - window_started_at < EMAIL_REPLY_SYNC_LOOKBACK
        or sync_started_at - window_started_at > EMAIL_REPLY_SYNC_MAX_LOOKBACK
        or covered_through < sync_started_at
        or completed_at < covered_through
    ):
        raise EmailAdapterError(
            "email_reply_sync_receipt_invalid",
            "Email reply sync could not prove a complete bounded recipient window",
        )
    return {
        "receipt_version": EMAIL_REPLY_SYNC_RECEIPT_VERSION,
        "sender_account_id": str(sender_account.get("id") or ""),
        "sender_scope_type": sender_scope_type,
        "sender_business_id": sender_business_id,
        "channel": "email",
        "provider": EMAIL_REPLY_SYNC_PROVIDER,
        "provider_identity_fingerprint": mailbox_identity_fingerprint(sender_account),
        "scope": EMAIL_REPLY_SYNC_SCOPE,
        "recipient_hashes": recipient_hashes,
        "recipient_count": len(recipient_hashes),
        "recipient_scope_hash": email_recipient_scope_fingerprint(sender_account, recipient_emails),
        "message_limit": safe_message_limit,
        "window_started_at": window_started_at.astimezone(timezone.utc).isoformat(),
        "covered_through": covered_through.astimezone(timezone.utc).isoformat(),
        "sync_started_at": sync_started_at.astimezone(timezone.utc).isoformat(),
        "completed_at": completed_at.astimezone(timezone.utc).isoformat(),
        "complete": True,
        "truncated": False,
        "failure_count": 0,
        "folders": folders,
        "counters": receipt_counters,
    }


def _folder_receipt_valid(folders: Any, recipient_count: int) -> bool:
    if not isinstance(folders, list) or len(folders) != len(COMPLETE_REPLY_MAILBOX_ROLES):
        return False
    roles: set[str] = set()
    names: set[str] = set()
    for folder in folders:
        if not isinstance(folder, dict):
            return False
        role = str(folder.get("role") or "")
        name = str(folder.get("name") or "")
        count_keys = (
            "uidvalidity",
            "high_watermark_uid",
            "candidate_uid_count",
            "header_checked_uid_count",
            "matched_uid_count",
            "fetched_uid_count",
            "body_checked_uid_count",
            "window_message_count",
            "recipient_scope_count",
        )
        counts = {key: folder.get(key) for key in count_keys}
        if role not in COMPLETE_REPLY_MAILBOX_ROLES or role in roles or not name or name in names:
            return False
        if any(isinstance(value, bool) or not isinstance(value, int) for value in counts.values()):
            return False
        if counts["uidvalidity"] < 1 or counts["high_watermark_uid"] < 0:
            return False
        if any(counts[key] < 0 for key in count_keys[2:]):
            return False
        if counts["candidate_uid_count"] != counts["header_checked_uid_count"]:
            return False
        if counts["matched_uid_count"] != counts["fetched_uid_count"]:
            return False
        if counts["body_checked_uid_count"] < counts["fetched_uid_count"]:
            return False
        if counts["window_message_count"] != counts["fetched_uid_count"]:
            return False
        if counts["recipient_scope_count"] != recipient_count:
            return False
        roles.add(role)
        names.add(name)
    return roles == set(COMPLETE_REPLY_MAILBOX_ROLES) and len(names) == len(COMPLETE_REPLY_MAILBOX_ROLES)


def _receipt_counters_valid(counters: Any, folders: list[dict[str, Any]]) -> bool:
    if not isinstance(counters, dict):
        return False
    aggregate_keys = (
        "candidate_uid_count",
        "header_checked_uid_count",
        "matched_uid_count",
        "fetched_uid_count",
        "body_checked_uid_count",
    )
    if any(
        isinstance(counters.get(key), bool)
        or not isinstance(counters.get(key), int)
        or counters.get(key) < 0
        for key in aggregate_keys
    ):
        return False
    expected = {
        key: sum(int(folder.get(key) or 0) for folder in folders)
        for key in aggregate_keys
    }
    if any(counters.get(key) != expected[key] for key in aggregate_keys):
        return False
    return (
        counters["candidate_uid_count"] == counters["header_checked_uid_count"]
        and counters["matched_uid_count"] == counters["fetched_uid_count"]
    )


def load_trusted_email_reply_sync_receipt(
    cursor: Any,
    sender_account_id: str,
    *,
    required_recipient_emails: list[str],
    required_covered_through: datetime | None = None,
    max_age_seconds: int = 120,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return a fresh complete receipt that includes every required recipient hash."""
    sender_id = str(sender_account_id or "").strip()
    if not sender_id or max_age_seconds < 1:
        return None
    try:
        required_hashes = set(email_recipient_hashes(required_recipient_emails))
    except (EmailAdapterError, ValueError, TypeError):
        return None
    cursor.execute(
        """
        SELECT id, scope_type, business_id, channel, sender_identity, auth_data_encrypted
        FROM outreach_sender_accounts
        WHERE id = %s
        """,
        (sender_id,),
    )
    sender = _dict(cursor.fetchone())
    if str(sender.get("id") or "") != sender_id or sender.get("channel") != "email":
        return None
    cursor.execute(
        """
        SELECT id, event_type, payload_json, created_at
        FROM outreach_sender_account_events
        WHERE sender_account_id = %s
          AND event_type IN ('reply_sync_succeeded', 'reply_sync_failed')
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (sender_id,),
    )
    event = _dict(cursor.fetchone())
    if event.get("event_type") != "reply_sync_succeeded":
        return None
    payload = event.get("payload_json")
    if not isinstance(payload, dict):
        return None
    sender_scope_type, sender_business_id = _sender_scope(sender)
    recipient_hashes = payload.get("recipient_hashes")
    if not isinstance(recipient_hashes, list):
        return None
    try:
        current_scope_hash = email_recipient_scope_fingerprint_from_hashes(sender, recipient_hashes)
    except (EmailAdapterError, ValueError, TypeError):
        return None
    folders = payload.get("folders")
    message_limit = payload.get("message_limit")
    if (
        payload.get("receipt_version") != EMAIL_REPLY_SYNC_RECEIPT_VERSION
        or payload.get("sender_account_id") != sender_id
        or payload.get("sender_scope_type") != sender_scope_type
        or payload.get("sender_business_id") != sender_business_id
        or payload.get("channel") != "email"
        or payload.get("provider") != EMAIL_REPLY_SYNC_PROVIDER
        or payload.get("scope") != EMAIL_REPLY_SYNC_SCOPE
        or payload.get("complete") is not True
        or payload.get("truncated") is not False
        or payload.get("failure_count") != 0
        or isinstance(message_limit, bool)
        or not isinstance(message_limit, int)
        or message_limit < 1
        or message_limit > EMAIL_REPLY_SYNC_MAX_MESSAGE_LIMIT
        or payload.get("recipient_count") != len(recipient_hashes)
        or not required_hashes.issubset(recipient_hashes)
        or payload.get("recipient_scope_hash") != current_scope_hash
        or not _folder_receipt_valid(folders, len(recipient_hashes))
        or not _receipt_counters_valid(payload.get("counters"), folders)
    ):
        return None
    sync_started_at = _utc_datetime(payload.get("sync_started_at"))
    window_started_at = _utc_datetime(payload.get("window_started_at"))
    covered_through = _utc_datetime(payload.get("covered_through"))
    completed_at = _utc_datetime(payload.get("completed_at"))
    current_time = _utc_datetime(now) or datetime.now(timezone.utc)
    if not all((sync_started_at, window_started_at, covered_through, completed_at)):
        return None
    if not (window_started_at <= sync_started_at <= covered_through <= completed_at):
        return None
    lookback = sync_started_at - window_started_at
    if lookback < EMAIL_REPLY_SYNC_LOOKBACK or lookback > EMAIL_REPLY_SYNC_MAX_LOOKBACK:
        return None
    if payload["counters"]["candidate_uid_count"] > message_limit:
        return None
    if completed_at < current_time - timedelta(seconds=max_age_seconds):
        return None
    if completed_at > current_time + timedelta(seconds=5):
        return None
    required_cutoff = _utc_datetime(required_covered_through)
    if required_covered_through is not None and not required_cutoff:
        return None
    if required_cutoff and covered_through < required_cutoff:
        return None
    try:
        current_fingerprint = mailbox_identity_fingerprint(sender)
    except (EmailAdapterError, ValueError, TypeError):
        return None
    if payload.get("provider_identity_fingerprint") != current_fingerprint:
        return None
    return payload
