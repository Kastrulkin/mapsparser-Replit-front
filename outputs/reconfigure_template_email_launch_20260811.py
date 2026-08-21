#!/usr/bin/env python3
"""Move all 19 safe LocalOS email touches to 12 Aug 10:00 MSK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from prepare_template_email_launch_20260811 import (
    SENDER_ID,
    _actor_id,
    _insert_campaign,
    _insert_touch,
    _json_bytes,
)
from services.outreach_campaign_service import (
    apply_draft_campaign_review,
    approve_campaign,
    change_campaign_status,
)


MANIFEST = Path("/app/debug_data/localos-template-email-launch-20260811.json")
BACKUP_DIR = Path("/app/debug_data/template-email-launch-backup-20260811")
TARGET_AT = datetime(2026, 8, 12, 10, 0, tzinfo=ZoneInfo("Europe/Moscow"))


def _rows(cursor: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    launches = list(manifest.get("launches") or [])
    if len(launches) != 19:
        raise RuntimeError(f"expected_19_launches_got_{len(launches)}")
    queue_ids = [str(row["queue_id"]) for row in launches]
    campaign_ids = [str(row["campaign_id"]) for row in launches]
    lead_ids = [str(row["lead_id"]) for row in launches]

    connection = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    connection.autocommit = False
    cursor = connection.cursor()
    try:
        actor_id = _actor_id(cursor)
        campaigns = _rows(
            cursor,
            "SELECT * FROM outreach_campaigns WHERE id=ANY(%s::uuid[]) ORDER BY id FOR UPDATE",
            (campaign_ids,),
        )
        touches = _rows(
            cursor,
            "SELECT * FROM outreach_campaign_touches WHERE campaign_id=ANY(%s::uuid[]) ORDER BY campaign_id,sequence_index FOR UPDATE",
            (campaign_ids,),
        )
        queues = _rows(
            cursor,
            "SELECT * FROM outreachsendqueue WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (queue_ids,),
        )
        drafts = _rows(
            cursor,
            "SELECT * FROM outreachmessagedrafts WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            ([str(row["draft_id"]) for row in queues],),
        )
        if len(campaigns) != 19 or len(touches) != 19 or len(queues) != 19 or len(drafts) != 19:
            raise RuntimeError("launch_rows_not_exactly_19")
        if any(row.get("status") != "approved" for row in campaigns):
            raise RuntimeError("campaign_not_approved")
        if any(
            row.get("delivery_status") != "queued"
            or row.get("sent_at") is not None
            or row.get("provider_message_id") is not None
            or int(row.get("attempts") or 0) != 0
            for row in queues
        ):
            raise RuntimeError("queue_not_pristine")
        inbound = _rows(
            cursor,
            "SELECT id FROM outreach_inbound_events WHERE lead_id=ANY(%s) AND COALESCE(is_human,FALSE)=TRUE",
            (lead_ids,),
        )
        suppressions = _rows(
            cursor,
            "SELECT id FROM outreach_suppressions WHERE lead_id=ANY(%s) AND (expires_at IS NULL OR expires_at>NOW())",
            (lead_ids,),
        )
        reactions = _rows(
            cursor,
            "SELECT id FROM outreachreactions WHERE lead_id=ANY(%s)",
            (lead_ids,),
        )
        if inbound or suppressions or reactions:
            raise RuntimeError(
                f"fresh_safety_blocker:inbound={len(inbound)},suppressions={len(suppressions)},reactions={len(reactions)}"
            )

        backup = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "apply" if args.apply else "dry_run",
            "campaigns": campaigns,
            "touches": touches,
            "queues": queues,
            "drafts": drafts,
            "manifest": manifest,
        }
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / (
            "all-19-same-day-prewrite.json" if args.apply else "all-19-same-day-dry-run.json"
        )
        backup_bytes = _json_bytes(backup)
        backup_path.write_bytes(backup_bytes)

        campaign_by_id = {str(row["id"]): row for row in campaigns}
        touch_by_campaign = {str(row["campaign_id"]): row for row in touches}
        new_launches = []
        superseded = []
        for launch in launches:
            old_campaign_id = str(launch["campaign_id"])
            old_campaign = campaign_by_id[old_campaign_id]
            old_touch = touch_by_campaign[old_campaign_id]
            change_campaign_status(cursor, old_campaign_id, "cancel", user_id=actor_id)
            cursor.execute(
                "SELECT COALESCE(MAX(version),0) max_version FROM outreach_campaigns WHERE workstream_id=%s",
                (old_campaign["workstream_id"],),
            )
            version = int(cursor.fetchone()["max_version"] or 0) + 1
            campaign_id = str(uuid.uuid4())
            policy = dict(old_campaign.get("policy_json") or {})
            policy.update(
                {
                    "daily_limit": 20,
                    "approval_scope": "email_first_touch_only",
                    "launch_cohort": "2026-08-12-all-19-user-approved",
                    "supervised_daily_cap": 20,
                }
            )
            _insert_campaign(
                cursor,
                old_campaign,
                campaign_id=campaign_id,
                version=version,
                actor_id=actor_id,
                policy=policy,
            )
            touch_id = str(uuid.uuid4())
            _insert_touch(
                cursor,
                old_touch,
                touch_id=touch_id,
                campaign_id=campaign_id,
                sequence_index=0,
                scheduled_at=TARGET_AT,
            )
            apply_draft_campaign_review(
                cursor,
                campaign_id=campaign_id,
                reviewed_touches=[
                    {
                        "sequence_index": 0,
                        "text": old_touch["generated_text"],
                        "subject": old_touch.get("subject"),
                        "quality_gate": old_touch["quality_gate_json"],
                    }
                ],
                user_id=actor_id,
            )
            approval = approve_campaign(cursor, campaign_id, user_id=actor_id)
            cursor.execute(
                "UPDATE outreachsendbatches SET daily_limit=20,updated_at=NOW() WHERE id=%s",
                (approval["batch_id"],),
            )
            cursor.execute(
                """SELECT id,draft_id,scheduled_at,delivery_status
                   FROM outreachsendqueue WHERE campaign_touch_id=%s""",
                (touch_id,),
            )
            queue = dict(cursor.fetchone() or {})
            if not queue:
                raise RuntimeError(f"replacement_queue_missing:{launch['name']}")
            new_launches.append(
                {
                    **launch,
                    "campaign_id": campaign_id,
                    "touch_id": touch_id,
                    "batch_id": approval["batch_id"],
                    "queue_id": str(queue["id"]),
                    "draft_id": str(queue["draft_id"]),
                    "scheduled_at": queue["scheduled_at"],
                }
            )
            superseded.append(
                {
                    "name": launch["name"],
                    "campaign_id": old_campaign_id,
                    "queue_id": launch["queue_id"],
                }
            )

        cursor.execute(
            """UPDATE outreach_sender_accounts
               SET capabilities_json=COALESCE(capabilities_json,'{}'::jsonb)
                    || jsonb_build_object('sent_label','Localos'),updated_at=NOW()
               WHERE id=%s
               RETURNING capabilities_json""",
            (SENDER_ID,),
        )
        sender_capabilities = dict(cursor.fetchone() or {}).get("capabilities_json") or {}
        if sender_capabilities.get("sent_label") != "Localos":
            raise RuntimeError("sender_label_capability_not_persisted")

        replacement_queue_ids = [str(row["queue_id"]) for row in new_launches]
        cursor.execute(
            """SELECT COUNT(*) count FROM outreachsendqueue
               WHERE id=ANY(%s) AND delivery_status='queued' AND sent_at IS NULL
                 AND scheduled_at=%s""",
            (replacement_queue_ids, TARGET_AT),
        )
        queued = int(cursor.fetchone()["count"] or 0)
        if queued != 19:
            raise RuntimeError(f"replacement_queue_count_{queued}")

        updated_manifest = {
            **manifest,
            "mode": "apply",
            "scheduled_timezone": "Europe/Moscow",
            "cohorts": [
                {
                    "scheduled_at": TARGET_AT.isoformat(),
                    "queue_ids": replacement_queue_ids,
                    "count": 19,
                    "supervised_daily_cap": 20,
                }
            ],
            "launches": new_launches,
            "superseded_email_launches": superseded,
            "email_campaigns": 19,
            "email_queues": 19,
            "approved": 19,
            "sent": 0,
            "sent_label": "Localos",
            "backup_path": str(backup_path),
            "backup_sha256": hashlib.sha256(backup_bytes).hexdigest(),
            "status": "APPLIED_ALL_19_SAME_DAY" if args.apply else "DRY_RUN_ROLLED_BACK",
        }
        canonical = json.dumps(updated_manifest, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        updated_manifest["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
        if args.apply:
            connection.commit()
            MANIFEST.write_text(
                json.dumps(updated_manifest, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        else:
            connection.rollback()
        print(json.dumps(updated_manifest, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
