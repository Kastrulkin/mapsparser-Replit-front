"""Reconcile one provider-observed send and release the untouched second pilot queue.

This script never calls a delivery provider. It consumes a fresh read-only Gmail
proof produced by ``reconcile_unknown_sent.py`` and updates only the two pinned
queue records plus the native campaign/learning records for the observed send.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg2.extras import Json

from pg_db_utils import get_db_connection
from services.outreach_safety_service import record_touch_learning_event


APPROVAL_TOKEN = "APPROVE_LOCALOS_CREATOR_INCIDENT_RECOVERY_20260908"
SENDER_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
SENT_QUEUE_ID = "f2529b9a-f17a-4eeb-b6c4-e7a6d8a9faf4"
PENDING_QUEUE_ID = "779ad74c-52d5-4a05-bfb8-2f92065ca90a"
EXPECTED = {
    SENT_QUEUE_ID: {
        "recipient": "as_kotkin@mail.ru",
        "touch_id": "9c93123a-3283-4531-91bb-0332ff586c5a",
        "campaign_id": "1c160bd5-6a12-478a-a58f-7badff10781b",
        "subject": "Алексей | LocalOS | сотрудничество",
        "body_sha256": "e4f71385b2ccef500e19ff60ed345c9580583ab209daa57aa5d07c334a97eb4d",
    },
    PENDING_QUEUE_ID: {
        "recipient": "info@cozy-spb.ru",
        "touch_id": "87fa2596-87ab-4ee2-b3eb-792da087fb62",
        "campaign_id": "4f11b9ee-1c69-49a6-ba4b-e452a340e9c6",
        "subject": "Татьяна и Яна | LocalOS | сотрудничество",
        "body_sha256": "b04c7ac6f5b1ea7996a8c358570690516cdb677c46b130af0fc9edfe9316f178",
    },
}


def parse_utc(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_missing_timezone")
    return parsed.astimezone(timezone.utc)


def validate_proof(payload: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    if payload.get("mailbox") != "localosgo@gmail.com":
        raise ValueError("proof_mailbox_mismatch")
    if payload.get("scope") != "exact_two_approved_messages_read_only":
        raise ValueError("proof_scope_mismatch")
    observed_at = parse_utc(payload.get("observed_at"))
    age_seconds = (now.astimezone(timezone.utc) - observed_at).total_seconds()
    if age_seconds < -60 or age_seconds > 600:
        raise ValueError("proof_not_fresh")
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("proof_row_count_mismatch")
    by_queue = {str(row.get("queue_id") or ""): row for row in rows}
    if set(by_queue) != set(EXPECTED):
        raise ValueError("proof_queue_set_mismatch")

    sent_row = by_queue[SENT_QUEUE_ID]
    pending_row = by_queue[PENDING_QUEUE_ID]
    sent_provider = sent_row.get("provider") or {}
    pending_provider = pending_row.get("provider") or {}
    sent_matches = sent_provider.get("matches")
    if (
        sent_provider.get("verified_sent") is not True
        or sent_provider.get("exact_match_count") != 1
        or not isinstance(sent_matches, list)
        or len(sent_matches) != 1
    ):
        raise ValueError("sent_provider_proof_mismatch")
    if (
        pending_provider.get("verified_sent") is not False
        or pending_provider.get("exact_match_count") != 0
        or pending_provider.get("matches") != []
    ):
        raise ValueError("pending_provider_proof_mismatch")

    match = sent_matches[0]
    message_id = str(match.get("message_id") or "")
    if not re.fullmatch(r'<[^<>\s"\\]+@[^<>\s"\\]+>', message_id):
        raise ValueError("provider_message_id_invalid")
    if (
        match.get("from_matches") is not True
        or match.get("recipient_matches") is not True
        or match.get("unexpected_cc_bcc") is not False
        or match.get("subject_matches") is not True
        or (match.get("body") or {}).get("matches") is not True
        or (match.get("body") or {}).get("sha256")
        != EXPECTED[SENT_QUEUE_ID]["body_sha256"]
    ):
        raise ValueError("provider_content_proof_mismatch")
    message_date = parse_utc(match.get("message_date"))
    if message_date.date() != now.astimezone(timezone.utc).date():
        raise ValueError("provider_message_date_mismatch")
    if sent_row.get("approved_body_sha256") != EXPECTED[SENT_QUEUE_ID]["body_sha256"]:
        raise ValueError("sent_approved_hash_mismatch")
    if pending_row.get("approved_body_sha256") != EXPECTED[PENDING_QUEUE_ID]["body_sha256"]:
        raise ValueError("pending_approved_hash_mismatch")
    return {
        "message_id": message_id,
        "message_date": message_date,
        "gmail_message_id": str(match.get("gmail_message_id") or ""),
        "gmail_thread_id": str(match.get("gmail_thread_id") or ""),
        "sent_uid": str(match.get("sent_uid") or ""),
        "observed_at": observed_at,
    }


def exact_rows(cursor: Any) -> dict[str, dict[str, Any]]:
    cursor.execute(
        """
        SELECT q.id::text queue_id, q.lead_id::text lead_id,
               q.sender_account_id::text sender_account_id,
               q.delivery_status, q.attempts, q.last_attempt_at,
               q.dispatch_started_at, q.preflight_at, q.preflight_reason,
               q.sent_at, q.next_retry_at, q.dlq_at, q.provider_name,
               q.provider_account_id, q.provider_message_id,
               q.recipient_kind, q.recipient_value, q.error_text,
               q.idempotency_key, t.id::text touch_id, t.status touch_status,
               t.subject, lower(p.normalized_value) recipient,
               c.id::text campaign_id, c.status campaign_status, c.version,
               encode(digest(COALESCE(d.approved_text, d.generated_text, ''), 'sha256'), 'hex') body_sha256
        FROM outreachsendqueue q
        JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
        JOIN outreach_campaigns c ON c.id=t.campaign_id
        JOIN lead_contact_points p ON p.id=t.contact_point_id
        JOIN outreachmessagedrafts d ON d.id=q.draft_id
        WHERE q.id IN (%s, %s)
        ORDER BY q.id
        FOR UPDATE OF q, t, c
        """,
        (SENT_QUEUE_ID, PENDING_QUEUE_ID),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    if len(rows) != 2:
        raise RuntimeError("database_queue_set_missing")
    return {row["queue_id"]: row for row in rows}


def validate_database_state(rows: dict[str, dict[str, Any]]) -> None:
    for queue_id, expected in EXPECTED.items():
        row = rows[queue_id]
        if (
            row["sender_account_id"] != SENDER_ID
            or row["touch_id"] != expected["touch_id"]
            or row["campaign_id"] != expected["campaign_id"]
            or row["recipient"] != expected["recipient"]
            or row["subject"] != expected["subject"]
            or row["version"] != 1
            or row["body_sha256"] != expected["body_sha256"]
            or row["idempotency_key"] != f"outreach:{expected['touch_id']}"
        ):
            raise RuntimeError("database_message_fingerprint_changed")
    sent = rows[SENT_QUEUE_ID]
    pending = rows[PENDING_QUEUE_ID]
    sent_already_reconciled = (
        sent["delivery_status"] == "sent"
        and sent["provider_name"] == "native_email"
        and str(sent["provider_account_id"] or "") == SENDER_ID
        and bool(sent["provider_message_id"])
        and sent["sent_at"] is not None
    )
    if not sent_already_reconciled and not (
        sent["delivery_status"] == "sending"
        and int(sent["attempts"] or 0) == 1
        and sent["provider_message_id"] is None
        and sent["sent_at"] is None
        and sent["error_text"] is None
        and sent["preflight_reason"] == "preflight_passed"
    ):
        raise RuntimeError("sent_queue_state_changed")
    pending_already_released = (
        pending["delivery_status"] == "queued"
        and int(pending["attempts"] or 0) == 0
        and pending["dispatch_started_at"] is None
        and pending["provider_message_id"] is None
    )
    if not pending_already_released and not (
        pending["delivery_status"] == "sending"
        and int(pending["attempts"] or 0) == 1
        and pending["provider_message_id"] is None
        and pending["sent_at"] is None
        and pending["preflight_at"] is None
        and pending["error_text"] is None
    ):
        raise RuntimeError("pending_queue_state_changed")


def run(proof_path: Path) -> dict[str, Any]:
    if os.environ.get("LOCALOS_CREATOR_INCIDENT_RECOVERY_APPROVED") != APPROVAL_TOKEN:
        raise RuntimeError("recovery_approval_token_missing")
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    provider = validate_proof(proof, now=datetime.now(timezone.utc))
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) count FROM outreachsendqueue WHERE delivery_status = 'sending' AND id NOT IN (%s, %s)",
            (SENT_QUEUE_ID, PENDING_QUEUE_ID),
        )
        if int(cursor.fetchone()["count"] or 0) != 0:
            raise RuntimeError("other_dispatch_is_inflight")
        rows = exact_rows(cursor)
        validate_database_state(rows)

        sent = rows[SENT_QUEUE_ID]
        pending = rows[PENDING_QUEUE_ID]
        if sent["delivery_status"] == "sent" and (
            sent["provider_message_id"] != provider["message_id"]
            or sent["provider_name"] != "native_email"
            or str(sent["provider_account_id"] or "") != SENDER_ID
            or sent["touch_status"] != "sent"
            or sent["campaign_status"] != "completed"
        ):
            raise RuntimeError("reconciled_sent_state_mismatch")
        if pending["delivery_status"] == "queued" and (
            pending["touch_status"] != "scheduled"
            or pending["campaign_status"] != "approved"
            or int(pending["attempts"] or 0) != 0
            or pending["dispatch_started_at"] is not None
        ):
            raise RuntimeError("released_pending_state_mismatch")
        if sent["delivery_status"] != "sent":
            cursor.execute(
                """
                UPDATE outreachsendqueue
                SET delivery_status='sent', provider_message_id=%s,
                    provider_name='native_email', provider_account_id=%s,
                    recipient_kind='email', recipient_value=%s, error_text=NULL,
                    sent_at=%s, next_retry_at=NULL, dlq_at=NULL, updated_at=NOW()
                WHERE id=%s AND delivery_status='sending' AND attempts=1
                """,
                (
                    provider["message_id"],
                    SENDER_ID,
                    EXPECTED[SENT_QUEUE_ID]["recipient"],
                    provider["message_date"],
                    SENT_QUEUE_ID,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("sent_queue_reconciliation_lost_race")
            cursor.execute(
                "UPDATE prospectingleads SET status='sent', updated_at=NOW() WHERE id=%s",
                (sent["lead_id"],),
            )
            cursor.execute(
                """
                UPDATE outreach_campaign_touches
                SET status='sent', delivery_json=delivery_json || %s, updated_at=NOW()
                WHERE id=%s AND status='scheduled'
                """,
                (
                    Json(
                        {
                            "provider_name": "native_email",
                            "provider_message_id": provider["message_id"],
                            "provider_observed": True,
                            "provider_observed_at": provider["observed_at"].isoformat(),
                            "gmail_message_id": provider["gmail_message_id"],
                            "gmail_thread_id": provider["gmail_thread_id"],
                            "sent_uid": provider["sent_uid"],
                            "reconciliation_reason": "learning_constraint_rollback_after_provider_send",
                        }
                    ),
                    EXPECTED[SENT_QUEUE_ID]["touch_id"],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("sent_touch_reconciliation_lost_race")
            cursor.execute(
                "SELECT COUNT(*) count FROM outreach_learning_events WHERE touch_id=%s AND outcome_type='sent'",
                (EXPECTED[SENT_QUEUE_ID]["touch_id"],),
            )
            if int(cursor.fetchone()["count"] or 0) == 0:
                record_touch_learning_event(
                    cursor,
                    touch_id=EXPECTED[SENT_QUEUE_ID]["touch_id"],
                    outcome_type="sent",
                    payload={
                        "provider_name": "native_email",
                        "provider_message_id": provider["message_id"],
                        "provider_observed": True,
                        "reconciliation_reason": "learning_constraint_rollback_after_provider_send",
                    },
                )
            cursor.execute(
                """
                INSERT INTO outreach_campaign_events (
                    id, campaign_id, touch_id, event_type, payload_json, created_at
                )
                SELECT %s, %s, %s, 'touch_sent', %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM outreach_campaign_events
                    WHERE touch_id=%s AND event_type='touch_sent'
                )
                """,
                (
                    str(uuid.uuid4()),
                    EXPECTED[SENT_QUEUE_ID]["campaign_id"],
                    EXPECTED[SENT_QUEUE_ID]["touch_id"],
                    Json(
                        {
                            "provider_name": "native_email",
                            "provider_message_id": provider["message_id"],
                            "provider_observed": True,
                            "reconciliation_reason": "learning_constraint_rollback_after_provider_send",
                        }
                    ),
                    provider["message_date"],
                    EXPECTED[SENT_QUEUE_ID]["touch_id"],
                ),
            )
            cursor.execute(
                "UPDATE outreach_campaigns SET status='completed', updated_at=NOW() WHERE id=%s AND status='approved'",
                (EXPECTED[SENT_QUEUE_ID]["campaign_id"],),
            )

        if pending["delivery_status"] != "queued":
            cursor.execute(
                """
                UPDATE outreachsendqueue
                SET delivery_status='queued', attempts=0, last_attempt_at=NULL,
                    dispatch_started_at=NULL, preflight_at=NULL,
                    preflight_reason=NULL, provider_name=NULL,
                    provider_account_id=NULL, provider_message_id=NULL,
                    recipient_kind=NULL, recipient_value=NULL, error_text=NULL,
                    next_retry_at=NULL, dlq_at=NULL, updated_at=NOW()
                WHERE id=%s AND delivery_status='sending' AND attempts=1
                  AND provider_message_id IS NULL AND sent_at IS NULL
                  AND preflight_at IS NULL AND error_text IS NULL
                """,
                (PENDING_QUEUE_ID,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("pending_queue_release_lost_race")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {
        "status": "pass",
        "sent_queue_reconciled": SENT_QUEUE_ID,
        "provider_message_id": provider["message_id"],
        "pending_queue_released": PENDING_QUEUE_ID,
        "provider_send_called": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(Path(arguments.proof)), default=str))


if __name__ == "__main__":
    main()
