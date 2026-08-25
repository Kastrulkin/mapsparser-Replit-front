#!/usr/bin/env python3
"""Dry-run/apply unambiguous known-lead bindings from recent manual sends."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pg_db_utils import get_db_connection  # noqa: E402


def normalize_external_peer(channel: str, value: object) -> str:
    raw = str(value or "").strip()
    if channel == "email":
        return raw.lower()
    if channel == "telegram":
        if raw.startswith("https://t.me/"):
            raw = raw.split("https://t.me/", 1)[1]
        return raw.lstrip("@").lower()
    return raw


def candidates(cursor, *, business_id: str, days: int) -> list[dict]:
    cursor.execute(
        """
        SELECT queue.id AS queue_id, queue.channel, queue.recipient_value,
               queue.provider_name, queue.sender_account_id AS actual_sender_id,
               queue.workstream_id, queue.lead_id, workstream.client_business_id AS business_id,
               lead.name AS lead_name, contact.id AS contact_point_id,
               contact.verification_status,
               MIN(sender.id::text) AS eligible_sender_id,
               COUNT(DISTINCT sender.id) AS eligible_sender_count,
               (
                   SELECT COUNT(DISTINCT other_queue.lead_id)
                   FROM outreachsendqueue other_queue
                   JOIN lead_workstreams other_workstream ON other_workstream.id = other_queue.workstream_id
                   WHERE other_workstream.client_business_id = workstream.client_business_id
                     AND other_queue.channel = queue.channel
                     AND LOWER(BTRIM(other_queue.recipient_value)) = LOWER(BTRIM(queue.recipient_value))
                     AND other_queue.delivery_status IN ('sent', 'delivered')
                     AND other_queue.sent_at >= NOW() - (%s || ' days')::interval
               ) AS recipient_lead_count
        FROM outreachsendqueue queue
        JOIN lead_workstreams workstream ON workstream.id = queue.workstream_id
        JOIN prospectingleads lead ON lead.id = queue.lead_id
        LEFT JOIN lead_contact_points contact
          ON contact.lead_id = queue.lead_id
         AND contact.contact_type = queue.channel
         AND LOWER(BTRIM(contact.normalized_value)) = LOWER(BTRIM(queue.recipient_value))
        LEFT JOIN outreach_sender_accounts sender
          ON (sender.business_id = workstream.client_business_id OR sender.scope_type = 'platform')
         AND sender.channel = queue.channel
         AND sender.status = 'connected' AND sender.outreach_enabled IS TRUE
        WHERE workstream.client_business_id = %s
          AND queue.channel IN ('email', 'telegram')
          AND queue.delivery_status IN ('sent', 'delivered')
          AND queue.sent_at >= NOW() - (%s || ' days')::interval
        GROUP BY queue.id, queue.channel, queue.recipient_value, queue.provider_name,
                 queue.sender_account_id, queue.workstream_id,
                 queue.lead_id, workstream.client_business_id, lead.name,
                 contact.id, contact.verification_status
        ORDER BY queue.sent_at DESC
        """,
        (days, business_id, days),
    )
    return [dict(row) for row in cursor.fetchall()]


def classify(row: dict) -> tuple[str, str | None]:
    if row.get("verification_status") == "invalid":
        return "blocked", "contact_invalid"
    if int(row.get("recipient_lead_count") or 0) != 1:
        return "blocked", "recipient_ambiguous"
    if not row.get("actual_sender_id") and int(row.get("eligible_sender_count") or 0) != 1:
        return "blocked", "sender_ambiguous" if row.get("eligible_sender_count") else "sender_missing"
    return "ready", None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.days < 1 or args.days > 365:
        raise SystemExit("days_must_be_between_1_and_365")
    os.environ.setdefault("OUTREACH_THREAD_SYNC_BUSINESS_IDS", args.business_id)
    os.environ.setdefault("OUTREACH_EMAIL_THREAD_SYNC_ENABLED", "true")
    os.environ.setdefault("OUTREACH_TELEGRAM_THREAD_SYNC_ENABLED", "true")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        rows = candidates(cursor, business_id=args.business_id, days=args.days)
        report = {"mode": "apply" if args.apply else "dry_run", "business_id": args.business_id, "days": args.days, "ready": [], "blocked": []}
        for row in rows:
            status, reason = classify(row)
            item = {
                "queue_id": str(row.get("queue_id")),
                "lead_id": str(row.get("lead_id")),
                "lead_name": row.get("lead_name"),
                "channel": row.get("channel"),
                "provider_name": row.get("provider_name"),
                "peer": row.get("recipient_value"),
                "reason": reason,
            }
            report[status].append(item)
            if status != "ready" or not args.apply:
                continue
            sender_id = str(row.get("actual_sender_id") or row.get("eligible_sender_id") or "")
            cursor.execute(
                """
                INSERT INTO lead_contact_points (
                    id, lead_id, contact_type, value, normalized_value, owner_type,
                    source_type, provider, confidence, verification_status,
                    observed_at, verified_at, metadata_json, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s, %s, 'company',
                    'history_backfill', 'provider_sent_message', 1,
                    'confirmed_source', NOW(), NOW(),
                    jsonb_build_object('queue_id', %s), NOW(), NOW()
                )
                ON CONFLICT (lead_id, contact_type, normalized_value) DO UPDATE
                SET verification_status = CASE
                        WHEN lead_contact_points.verification_status = 'invalid'
                        THEN lead_contact_points.verification_status
                        ELSE 'confirmed_source'
                    END,
                    verified_at = CASE
                        WHEN lead_contact_points.verification_status = 'invalid'
                        THEN lead_contact_points.verified_at ELSE NOW()
                    END,
                    metadata_json = lead_contact_points.metadata_json || EXCLUDED.metadata_json,
                    updated_at = NOW()
                """,
                (
                    row.get("lead_id"), row.get("channel"), row.get("recipient_value"),
                    normalize_external_peer(str(row.get("channel")), row.get("recipient_value")),
                    str(row.get("queue_id")),
                ),
            )
            cursor.execute(
                """
                INSERT INTO outreach_thread_bindings (
                    id, business_id, workstream_id, lead_id, sender_account_id,
                    channel, external_peer_id, last_processed_event_id,
                    last_processed_at, status, binding_source, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s, %s, %s, %s, NULL,
                    NULL, 'active', 'history_backfill',
                    jsonb_build_object('queue_id', %s), NOW(), NOW()
                ) ON CONFLICT DO NOTHING
                """,
                (
                    row.get("business_id"), row.get("workstream_id"), row.get("lead_id"),
                    sender_id, row.get("channel"),
                    normalize_external_peer(str(row.get("channel")), row.get("recipient_value")),
                    str(row.get("queue_id")),
                ),
            )
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        report["counts"] = {"total": len(rows), "ready": len(report["ready"]), "blocked": len(report["blocked"])}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
