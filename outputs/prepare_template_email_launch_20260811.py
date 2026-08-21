#!/usr/bin/env python3
"""Split the reviewed 50-chain pack and queue its safe email first touches.

Default mode executes the full transaction and rolls it back. ``--apply`` commits.
Telegram, VK and phone touches remain in separate draft-only campaigns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from services.outreach_campaign_service import (
    apply_draft_campaign_review,
    approve_campaign,
    record_campaign_event,
)


SOURCE = Path("/app/debug_data/localos-template-review-v12-20260811.json")
OUTPUT = Path("/app/debug_data/localos-template-email-launch-20260811.json")
BACKUP_DIR = Path("/app/debug_data/template-email-launch-backup-20260811")
SENDER_ID = "912646e4-1c3f-45d8-91da-e6080eef23db"
SENDER_IDENTITY = "localosgo@gmail.com"
BLOCKED_LEAD_IDS = {"7999e5da-11e7-4d8d-8f51-050508e924b9"}
MAP_SOURCE_EMAIL_EXCEPTIONS = {
    "007dad1a-90e4-405d-afcf-47ea36f5f378",
    "9b1d0daf-5f54-422a-8dbe-13362c5270b2",
    "f2fa2241-fc35-40ee-9fa7-727c6fb81416",
}
MOSCOW = ZoneInfo("Europe/Moscow")
FIRST_COHORT_AT = datetime(2026, 8, 12, 10, 0, tzinfo=MOSCOW)
SECOND_COHORT_AT = datetime(2026, 8, 13, 10, 0, tzinfo=MOSCOW)


def _rows(cursor: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def _actor_id(cursor: Any) -> str:
    cursor.execute(
        """SELECT id FROM users
           WHERE COALESCE(is_superadmin,FALSE)=TRUE AND is_active=TRUE
           ORDER BY updated_at DESC NULLS LAST LIMIT 1"""
    )
    row = cursor.fetchone()
    if not row:
        raise RuntimeError("active_superadmin_not_found")
    return str(row["id"])


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _insert_campaign(
    cursor: Any,
    source_campaign: dict[str, Any],
    *,
    campaign_id: str,
    version: int,
    actor_id: str,
    policy: dict[str, Any],
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_campaigns (
            id,workstream_id,lead_id,scope_type,business_id,sender_profile_id,
            version,status,policy_json,created_by,recipient_key,sender_mode,
            selected_offer_json,trust_strategy,decision_snapshot_json,created_at,updated_at
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s,%s,NOW(),NOW()
        )
        """,
        (
            campaign_id,
            source_campaign["workstream_id"],
            source_campaign["lead_id"],
            source_campaign["scope_type"],
            source_campaign.get("business_id"),
            source_campaign.get("sender_profile_id"),
            version,
            Json(policy),
            actor_id,
            source_campaign.get("recipient_key"),
            source_campaign["sender_mode"],
            Json(source_campaign.get("selected_offer_json") or {}),
            source_campaign.get("trust_strategy"),
            Json(source_campaign.get("decision_snapshot_json") or {}),
        ),
    )


def _insert_touch(
    cursor: Any,
    source_touch: dict[str, Any],
    *,
    touch_id: str,
    campaign_id: str,
    sequence_index: int,
    scheduled_at: datetime,
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_campaign_touches (
            id,campaign_id,sequence_index,channel,contact_point_id,sender_account_id,
            angle_type,scheduled_at,status,subject,generated_text,message_brief_json,
            quality_gate_json,delivery_json,strategy_fingerprint,strategy_json,
            created_at,updated_at
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s,%s,'{}'::jsonb,%s,%s,NOW(),NOW()
        )
        """,
        (
            touch_id,
            campaign_id,
            sequence_index,
            source_touch["channel"],
            source_touch.get("contact_point_id"),
            source_touch.get("sender_account_id"),
            source_touch["angle_type"],
            scheduled_at,
            source_touch.get("subject"),
            source_touch["generated_text"],
            Json(source_touch.get("message_brief_json") or {}),
            Json(source_touch.get("quality_gate_json") or {}),
            source_touch.get("strategy_fingerprint"),
            Json(source_touch.get("strategy_json") or {}),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    candidates = [
        item
        for item in source["results"]
        if item.get("classification") == "content_ready"
        and item.get("touches")
        and item["touches"][0].get("channel") == "email"
    ]
    if len(candidates) != 20:
        raise RuntimeError(f"expected_20_email_first_got_{len(candidates)}")
    selected = [item for item in candidates if str(item["lead_id"]) not in BLOCKED_LEAD_IDS]
    if len(selected) != 19:
        raise RuntimeError(f"expected_19_safe_email_first_got_{len(selected)}")
    selected_by_ws = {str(item["workstream_id"]): item for item in selected}
    workstream_ids = list(selected_by_ws)
    lead_ids = [str(item["lead_id"]) for item in selected]

    connection = psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
    )
    connection.autocommit = False
    cursor = connection.cursor()
    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry_run",
        "source_sha256": source.get("canonical_sha256"),
        "scheduled_timezone": "Europe/Moscow",
        "cohorts": [],
        "blocked_email_candidates": [
            {
                "name": item["name"],
                "lead_id": item["lead_id"],
                "reason": "recipient_domain_routes_to_blackhole_mx",
            }
            for item in candidates
            if str(item["lead_id"]) in BLOCKED_LEAD_IDS
        ],
    }
    try:
        actor_id = _actor_id(cursor)
        cursor.execute(
            """
            SELECT c.*
            FROM outreach_campaigns c
            WHERE c.id IN (
                SELECT DISTINCT ON (latest.workstream_id) latest.id
                FROM outreach_campaigns latest
                WHERE latest.workstream_id=ANY(%s::uuid[])
                ORDER BY latest.workstream_id,latest.version DESC,latest.created_at DESC
            )
            ORDER BY c.workstream_id
            FOR UPDATE
            """,
            (workstream_ids,),
        )
        latest = [dict(row) for row in cursor.fetchall()]
        latest_by_ws = {str(row["workstream_id"]): row for row in latest}
        if len(latest_by_ws) != 19 or any(row.get("status") != "draft" for row in latest):
            raise RuntimeError("latest_campaign_not_exactly_19_drafts")
        campaign_ids = [str(row["id"]) for row in latest]
        touches = _rows(
            cursor,
            """SELECT * FROM outreach_campaign_touches
               WHERE campaign_id=ANY(%s::uuid[])
               ORDER BY campaign_id,sequence_index FOR UPDATE""",
            (campaign_ids,),
        )
        touches_by_campaign: dict[str, list[dict[str, Any]]] = {}
        for touch in touches:
            touches_by_campaign.setdefault(str(touch["campaign_id"]), []).append(touch)

        inbound = _rows(
            cursor,
            """SELECT id,lead_id FROM outreach_inbound_events
               WHERE lead_id=ANY(%s) AND COALESCE(is_human,FALSE)=TRUE""",
            (lead_ids,),
        )
        suppressions = _rows(
            cursor,
            """SELECT id,lead_id FROM outreach_suppressions
               WHERE lead_id=ANY(%s) AND (expires_at IS NULL OR expires_at>NOW())""",
            (lead_ids,),
        )
        active_queue = _rows(
            cursor,
            """SELECT id,lead_id,delivery_status,sent_at FROM outreachsendqueue
               WHERE lead_id=ANY(%s)
                 AND (sent_at IS NOT NULL OR delivery_status IN ('queued','retry','sending','sent','delivered'))
               FOR UPDATE""",
            (lead_ids,),
        )
        active_campaigns = _rows(
            cursor,
            """SELECT id,lead_id,status FROM outreach_campaigns
               WHERE lead_id=ANY(%s) AND status IN ('approved','active','paused')
               FOR UPDATE""",
            (lead_ids,),
        )
        reactions = _rows(
            cursor,
            "SELECT id,lead_id FROM outreachreactions WHERE lead_id=ANY(%s)",
            (lead_ids,),
        )
        if inbound or suppressions or active_queue or active_campaigns or reactions:
            raise RuntimeError(
                "fresh_safety_blocker:"
                + json.dumps(
                    {
                        "inbound": len(inbound),
                        "suppressions": len(suppressions),
                        "queue_or_sent": len(active_queue),
                        "active_campaigns": len(active_campaigns),
                        "reactions": len(reactions),
                    },
                    ensure_ascii=False,
                )
            )

        cursor.execute(
            """SELECT * FROM outreach_sender_accounts WHERE id=%s FOR UPDATE""",
            (SENDER_ID,),
        )
        sender = dict(cursor.fetchone() or {})
        capabilities = sender.get("capabilities_json") or {}
        if not (
            sender.get("channel") == "email"
            and str(sender.get("sender_identity") or "").lower() == SENDER_IDENTITY
            and sender.get("status") == "connected"
            and sender.get("health_status") == "healthy"
            and sender.get("outreach_enabled")
            and capabilities.get("direct_send")
            and capabilities.get("reply_sync")
            and not sender.get("reply_sync_error")
        ):
            raise RuntimeError("email_sender_not_ready")

        contact_ids: list[str] = []
        for item in selected:
            campaign = latest_by_ws[str(item["workstream_id"])]
            actual = touches_by_campaign.get(str(campaign["id"]), [])
            expected = item["touches"]
            actual_bytes = [
                (touch["channel"], touch.get("subject"), touch["generated_text"])
                for touch in actual
            ]
            expected_bytes = [
                (touch["channel"], touch.get("subject"), touch["text"])
                for touch in expected
            ]
            if actual_bytes != expected_bytes or actual[0].get("sender_account_id") != SENDER_ID:
                raise RuntimeError(f"campaign_bytes_or_sender_mismatch:{item['name']}")
            if not all(bool((touch.get("quality_gate_json") or {}).get("passed")) for touch in actual):
                raise RuntimeError(f"quality_gate_failed:{item['name']}")
            contact_ids.append(str(actual[0]["contact_point_id"]))

        contacts = _rows(
            cursor,
            """SELECT id,lead_id,contact_type,normalized_value,verification_status,metadata_json
               FROM lead_contact_points WHERE id=ANY(%s::uuid[]) FOR UPDATE""",
            (contact_ids,),
        )
        if len(contacts) != 19:
            raise RuntimeError(f"contact_count_{len(contacts)}")
        normalized_recipients = []
        for contact in contacts:
            if not (
                contact.get("contact_type") == "email"
                and (
                    contact.get("verification_status") in {"verified", "confirmed_source"}
                    or (
                        str(contact.get("id")) in MAP_SOURCE_EMAIL_EXCEPTIONS
                        and contact.get("verification_status") == "valid_format"
                    )
                )
            ):
                raise RuntimeError(f"email_contact_not_ready:{contact.get('id')}")
            normalized_recipients.append(str(contact.get("normalized_value") or "").lower())
        if len(set(normalized_recipients)) != 19:
            raise RuntimeError("duplicate_email_recipient_in_cohort")

        all_campaigns = _rows(
            cursor,
            "SELECT * FROM outreach_campaigns WHERE workstream_id=ANY(%s::uuid[]) ORDER BY workstream_id,version",
            (workstream_ids,),
        )
        all_campaign_ids = [str(row["id"]) for row in all_campaigns]
        all_touches = _rows(
            cursor,
            "SELECT * FROM outreach_campaign_touches WHERE campaign_id=ANY(%s::uuid[]) ORDER BY campaign_id,sequence_index",
            (all_campaign_ids,),
        )
        backup = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": result["mode"],
            "campaigns": all_campaigns,
            "touches": all_touches,
        }
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / ("prewrite.json" if args.apply else "dry-run-prewrite.json")
        backup_bytes = _json_bytes(backup)
        backup_path.write_bytes(backup_bytes)
        result["backup_path"] = str(backup_path)
        result["backup_sha256"] = hashlib.sha256(backup_bytes).hexdigest()

        launch_rows: list[dict[str, Any]] = []
        remainder_rows: list[dict[str, Any]] = []
        for index, item in enumerate(selected):
            workstream_id = str(item["workstream_id"])
            old_campaign = latest_by_ws[workstream_id]
            old_touches = touches_by_campaign[str(old_campaign["id"])]
            scheduled_at = FIRST_COHORT_AT if index < 10 else SECOND_COHORT_AT
            cursor.execute(
                "SELECT COALESCE(MAX(version),0) AS max_version FROM outreach_campaigns WHERE workstream_id=%s",
                (workstream_id,),
            )
            max_version = int(cursor.fetchone()["max_version"] or 0)
            cursor.execute(
                """UPDATE outreach_campaigns
                   SET status='cancelled',stop_reason='superseded_by_stepwise_channel_launch',updated_at=NOW()
                   WHERE id=%s""",
                (old_campaign["id"],),
            )
            cursor.execute(
                """UPDATE outreach_campaign_touches
                   SET status='cancelled',updated_at=NOW() WHERE campaign_id=%s""",
                (old_campaign["id"],),
            )

            email_campaign_id = str(uuid.uuid4())
            email_policy = dict(old_campaign.get("policy_json") or {})
            email_policy.update(
                {
                    "stop_on_reply": True,
                    "daily_limit": 10,
                    "minimum_cadence_hours": 24,
                    "approval_scope": "email_first_touch_only",
                    "launch_cohort": "2026-08-12" if index < 10 else "2026-08-13",
                }
            )
            _insert_campaign(
                cursor,
                old_campaign,
                campaign_id=email_campaign_id,
                version=max_version + 1,
                actor_id=actor_id,
                policy=email_policy,
            )
            email_touch_id = str(uuid.uuid4())
            _insert_touch(
                cursor,
                old_touches[0],
                touch_id=email_touch_id,
                campaign_id=email_campaign_id,
                sequence_index=0,
                scheduled_at=scheduled_at,
            )
            apply_draft_campaign_review(
                cursor,
                campaign_id=email_campaign_id,
                reviewed_touches=[
                    {
                        "sequence_index": 0,
                        "text": old_touches[0]["generated_text"],
                        "subject": old_touches[0].get("subject"),
                        "quality_gate": old_touches[0]["quality_gate_json"],
                    }
                ],
                user_id=actor_id,
            )
            approval = approve_campaign(cursor, email_campaign_id, user_id=actor_id)
            cursor.execute(
                """SELECT q.id AS queue_id,q.batch_id,q.scheduled_at,q.delivery_status,
                          q.draft_id,q.campaign_touch_id
                   FROM outreachsendqueue q WHERE q.campaign_touch_id=%s""",
                (email_touch_id,),
            )
            queue = dict(cursor.fetchone() or {})
            if not queue:
                raise RuntimeError(f"queue_missing:{item['name']}")
            launch_rows.append(
                {
                    "name": item["name"],
                    "lead_id": item["lead_id"],
                    "workstream_id": workstream_id,
                    "campaign_id": email_campaign_id,
                    "touch_id": email_touch_id,
                    "batch_id": approval["batch_id"],
                    "queue_id": queue["queue_id"],
                    "draft_id": queue["draft_id"],
                    "scheduled_at": queue["scheduled_at"],
                    "subject": old_touches[0].get("subject"),
                    "recipient_contact_id": str(old_touches[0]["contact_point_id"]),
                }
            )

            if len(old_touches) > 1:
                remainder_campaign_id = str(uuid.uuid4())
                remainder_policy = dict(old_campaign.get("policy_json") or {})
                remainder_policy.update(
                    {
                        "approval_scope": "remaining_sequence_after_email",
                        "no_auto_dispatch": True,
                        "manual_review_required": True,
                        "stop_on_reply": True,
                    }
                )
                _insert_campaign(
                    cursor,
                    old_campaign,
                    campaign_id=remainder_campaign_id,
                    version=max_version + 2,
                    actor_id=actor_id,
                    policy=remainder_policy,
                )
                remainder_review: list[dict[str, Any]] = []
                for new_index, old_touch in enumerate(old_touches[1:]):
                    day_offset = int(item["touches"][new_index + 1].get("day_offset") or 0)
                    _insert_touch(
                        cursor,
                        old_touch,
                        touch_id=str(uuid.uuid4()),
                        campaign_id=remainder_campaign_id,
                        sequence_index=new_index,
                        scheduled_at=scheduled_at + timedelta(days=day_offset),
                    )
                    remainder_review.append(
                        {
                            "sequence_index": new_index,
                            "text": old_touch["generated_text"],
                            "subject": old_touch.get("subject"),
                            "quality_gate": old_touch["quality_gate_json"],
                        }
                    )
                apply_draft_campaign_review(
                    cursor,
                    campaign_id=remainder_campaign_id,
                    reviewed_touches=remainder_review,
                    user_id=actor_id,
                )
                record_campaign_event(
                    cursor,
                    remainder_campaign_id,
                    "remaining_sequence_preserved_as_draft",
                    actor_id=actor_id,
                    payload={"source_campaign_id": str(old_campaign["id"]), "touch_count": len(old_touches) - 1},
                )
                remainder_rows.append(
                    {
                        "name": item["name"],
                        "campaign_id": remainder_campaign_id,
                        "touch_count": len(old_touches) - 1,
                        "status": "draft",
                    }
                )

        cursor.execute(
            """SELECT COUNT(*) AS count FROM outreachsendqueue
               WHERE id=ANY(%s) AND delivery_status='queued' AND sent_at IS NULL""",
            ([str(row["queue_id"]) for row in launch_rows],),
        )
        queued_count = int(cursor.fetchone()["count"] or 0)
        if queued_count != 19:
            raise RuntimeError(f"queued_count_{queued_count}")
        result.update(
            {
                "status": "APPLIED" if args.apply else "DRY_RUN_ROLLED_BACK",
                "email_campaigns": 19,
                "email_queues": queued_count,
                "remaining_draft_campaigns": len(remainder_rows),
                "approved": 19,
                "sent": 0,
                "launches": launch_rows,
                "remaining": remainder_rows,
            }
        )
        result["cohorts"] = [
            {
                "scheduled_at": FIRST_COHORT_AT.isoformat(),
                "queue_ids": [str(row["queue_id"]) for row in launch_rows[:10]],
                "count": 10,
            },
            {
                "scheduled_at": SECOND_COHORT_AT.isoformat(),
                "queue_ids": [str(row["queue_id"]) for row in launch_rows[10:]],
                "count": 9,
            },
        ]
        canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        result["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
        if args.apply:
            connection.commit()
            OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        else:
            connection.rollback()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
