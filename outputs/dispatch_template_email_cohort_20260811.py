#!/usr/bin/env python3
"""Dispatch one exact LocalOS email cohort and label only its sent messages."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database_manager import get_db_connection
from services.outreach_dispatch_service import dispatch_due_outreach_queue
from services.outreach_email_adapter import _close_imap, _imap_connection, load_mailbox_config
from services.outreach_email_reply_service import sync_email_replies
from services.outreach_personalization_ai import generation_contract_current


MANIFEST = Path("/app/debug_data/localos-template-email-launch-20260811.json")
SOURCE = Path("/app/debug_data/localos-template-review-v12-20260811.json")
RESULT_DIR = Path("/app/debug_data")
SENDER_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
SENDER_IDENTITY = "localosgo@gmail.com"
LABEL_NAME = "Localos"


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _fetch_queue(cursor: Any, queue_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT q.*,b.status AS batch_status,b.daily_limit,
               c.id AS campaign_id,c.status AS campaign_status,c.scope_type,c.policy_json,
               t.status AS touch_status,t.subject,t.generated_text,t.approved_text,
               t.quality_gate_json,t.message_brief_json,
               d.status AS draft_status,d.approved_text AS draft_approved_text,
               cp.id AS contact_id,cp.normalized_value AS recipient_email,
               cp.verification_status,cp.source_type,
               s.sender_identity,s.status AS sender_status,s.health_status,
               s.outreach_enabled,s.capabilities_json,s.reply_sync_error
        FROM outreachsendqueue q
        JOIN outreachsendbatches b ON b.id=q.batch_id
        JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
        JOIN outreach_campaigns c ON c.id=t.campaign_id
        JOIN outreachmessagedrafts d ON d.id=q.draft_id
        JOIN lead_contact_points cp ON cp.id=t.contact_point_id
        JOIN outreach_sender_accounts s ON s.id=q.sender_account_id
        WHERE q.id=%s
        """,
        (queue_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _mailbox_name(raw_line: bytes) -> str:
    line = _text(raw_line).strip()
    match = re.search(r'\)\s+"(?:[^"\\]|\\.)*"\s+("(?:[^"\\]|\\.)*"|\S+)\s*$', line)
    if not match:
        raise RuntimeError(f"imap_list_line_unparsed:{line}")
    value = match.group(1)
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1].replace(r'\"', '"').replace(r'\\', '\\')
    return value


def _uid_search(client: Any, *criteria: str) -> list[str]:
    status, data = client.uid("search", None, *criteria)
    if _text(status).upper() != "OK":
        raise RuntimeError(f"imap_search_failed:{criteria}")
    return _text(data[0] if data else "").split()


def _label_exact_message_ids(sender: dict[str, Any], message_ids: list[str]) -> dict[str, Any]:
    config = load_mailbox_config(sender)
    if config["email"].lower() != SENDER_IDENTITY:
        raise RuntimeError("mailbox_identity_mismatch")
    client = None
    try:
        client = _imap_connection(config, timeout=20)
        capabilities = {_text(value).upper() for value in client.capabilities}
        if "X-GM-EXT-1" not in capabilities:
            raise RuntimeError("gmail_extension_unavailable")
        status, data = client.list()
        if _text(status).upper() != "OK":
            raise RuntimeError("imap_list_failed")
        lines = [item for item in (data or []) if isinstance(item, bytes)]
        sent_names = [_mailbox_name(line) for line in lines if b"\\Sent" in line]
        label_names = [_mailbox_name(line) for line in lines]
        if len(sent_names) != 1 or LABEL_NAME not in label_names:
            raise RuntimeError("sent_or_localos_label_missing")
        status, _ = client.select(sent_names[0], readonly=False)
        if _text(status).upper() != "OK":
            raise RuntimeError("sent_mailbox_unavailable")
        results = []
        for message_id in message_ids:
            matched: list[str] = []
            for _attempt in range(10):
                matched = _uid_search(client, "X-GM-RAW", f'"rfc822msgid:{message_id}"')
                if matched:
                    break
                time.sleep(1)
            if len(matched) != 1:
                results.append({"provider_message_id": message_id, "status": "not_found", "matches": len(matched)})
                continue
            uid = matched[0]
            status, _ = client.uid("store", uid, "+X-GM-LABELS", f'("{LABEL_NAME}")')
            if _text(status).upper() != "OK":
                results.append({"provider_message_id": message_id, "status": "label_store_failed"})
                continue
            labeled = set(_uid_search(client, "X-GM-RAW", f'"label:{LABEL_NAME}"'))
            results.append(
                {
                    "provider_message_id": message_id,
                    "status": "labeled" if uid in labeled else "label_readback_failed",
                    "uid": uid,
                }
            )
        return {
            "label": LABEL_NAME,
            "messages": results,
            "labeled": sum(item["status"] == "labeled" for item in results),
        }
    finally:
        _close_imap(client)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=int, choices=(0, 1), required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    cohort = manifest["cohorts"][args.cohort]
    expected_by_lead = {
        str(item["lead_id"]): item["touches"][0]
        for item in source["results"]
        if item.get("touches") and item["touches"][0].get("channel") == "email"
    }
    launch_by_queue = {str(item["queue_id"]): item for item in manifest["launches"]}
    queue_ids = [str(value) for value in cohort["queue_ids"]]
    now = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "cohort": args.cohort,
        "mode": "preflight_only" if args.preflight_only else "dispatch",
        "started_at": now.isoformat(),
        "scheduled_at": cohort["scheduled_at"],
        "queue_ids": queue_ids,
        "checks": [],
        "dispatch": [],
    }
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SELECT * FROM outreach_sender_accounts WHERE id=%s", (SENDER_ID,))
        sender_row = cursor.fetchone()
        sender = dict(sender_row) if sender_row else {}
        for queue_id in queue_ids:
            row = _fetch_queue(cursor, queue_id)
            launch = launch_by_queue.get(queue_id) or {}
            expected = expected_by_lead.get(str(launch.get("lead_id"))) or {}
            checks = {
                "queue_exists": bool(row),
                "queue_identity": bool(row) and str(row.get("campaign_id")) == str(launch.get("campaign_id")),
                "queue_waiting": bool(row) and row.get("delivery_status") == "queued" and not row.get("sent_at") and not row.get("provider_message_id"),
                "schedule_exact": bool(row) and row.get("scheduled_at").isoformat() == datetime.fromisoformat(cohort["scheduled_at"]).astimezone(timezone.utc).isoformat(),
                "due": bool(row) and (args.preflight_only or row.get("scheduled_at") <= now),
                "campaign_approved": bool(row) and row.get("campaign_status") == "approved",
                "touch_scheduled": bool(row) and row.get("touch_status") == "scheduled",
                "draft_approved": bool(row) and row.get("draft_status") == "approved",
                "sender_exact": bool(row) and str(row.get("sender_account_id")) == SENDER_ID and str(row.get("sender_identity") or "").lower() == SENDER_IDENTITY,
                "content_exact": bool(row) and row.get("subject") == expected.get("subject") and row.get("approved_text") == expected.get("text") == row.get("draft_approved_text"),
                "quality_current": bool(row) and generation_contract_current(row.get("message_brief_json"), row.get("quality_gate_json")),
                "sender_ready": bool(row) and row.get("sender_status") == "connected" and row.get("health_status") == "healthy" and bool(row.get("outreach_enabled")) and bool((row.get("capabilities_json") or {}).get("direct_send")) and bool((row.get("capabilities_json") or {}).get("reply_sync")) and not row.get("reply_sync_error"),
            }
            cursor.execute(
                """SELECT
                      (SELECT COUNT(*) FROM outreach_suppressions WHERE lead_id=%s AND (expires_at IS NULL OR expires_at>NOW())) AS suppressions,
                      (SELECT COUNT(*) FROM outreach_inbound_events WHERE lead_id=%s AND COALESCE(is_human,FALSE)=TRUE) AS inbound,
                      (SELECT COUNT(*) FROM outreachreactions WHERE lead_id=%s) AS reactions""",
                (launch.get("lead_id"), launch.get("lead_id"), launch.get("lead_id")),
            )
            safety = dict(cursor.fetchone())
            checks["fresh_safety"] = not any(int(safety.get(key) or 0) for key in ("suppressions", "inbound", "reactions"))
            result["checks"].append({"queue_id": queue_id, "name": launch.get("name"), "checks": checks})
        connection.rollback()
    finally:
        connection.close()
    if not all(all(item["checks"].values()) for item in result["checks"]):
        result["status"] = "blocked_preflight"
        path = RESULT_DIR / f"template-email-cohort-{args.cohort + 1}-result.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 2
    if args.preflight_only:
        result["status"] = "preflight_passed"
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    reply_sync = sync_email_replies(sender_limit=1, per_sender_limit=250, sender_account_id=SENDER_ID)
    result["reply_sync"] = reply_sync
    if int(reply_sync.get("failed") or 0) > 0:
        result["status"] = "blocked_reply_sync_failed"
        path = RESULT_DIR / f"template-email-cohort-{args.cohort + 1}-result.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 3

    for queue_id in queue_ids:
        dispatch = dispatch_due_outreach_queue(
            batch_size=1,
            queue_id=queue_id,
            campaign_only=True,
            allow_platform=True,
            max_daily_outreach_batch=20,
        )
        result["dispatch"].append({"queue_id": queue_id, "result": dispatch})

    verify_connection = get_db_connection()
    readback = []
    try:
        cursor = verify_connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        for queue_id in queue_ids:
            row = _fetch_queue(cursor, queue_id)
            readback.append(
                {
                    "queue_id": queue_id,
                    "delivery_status": row.get("delivery_status") if row else None,
                    "sent_at": row.get("sent_at") if row else None,
                    "provider_message_id": row.get("provider_message_id") if row else None,
                    "provider_name": row.get("provider_name") if row else None,
                    "attempts": row.get("attempts") if row else None,
                }
            )
        verify_connection.rollback()
    finally:
        verify_connection.close()
    result["readback"] = readback
    sent = [
        row
        for row in readback
        if row.get("delivery_status") in {"sent", "delivered"}
        and row.get("sent_at")
        and row.get("provider_message_id")
    ]
    result["sent"] = len(sent)
    result["labeling"] = _label_exact_message_ids(
        sender,
        [str(row["provider_message_id"]) for row in sent],
    )
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["status"] = (
        "sent_and_labeled"
        if len(sent) == len(queue_ids) and result["labeling"]["labeled"] == len(queue_ids)
        else "partial_or_label_warning"
    )
    path = RESULT_DIR / f"template-email-cohort-{args.cohort + 1}-result.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] == "sent_and_labeled" else 4


if __name__ == "__main__":
    sys.exit(main())
