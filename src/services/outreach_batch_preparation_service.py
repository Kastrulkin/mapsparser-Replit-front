"""Resumable, draft-only outreach preparation for LocalOS operators.

The module is intentionally not a delivery surface. It can inventory workstreams,
enqueue contact intelligence, and persist versioned campaign drafts. It never
approves campaigns, creates send batches, or writes to the delivery queue.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from pg_db_utils import get_db_connection
from services.contact_intelligence_service import enqueue_enrichment_job
from services.outreach_campaign_service import (
    SENDER_MODE_LOCALOS,
    SENDER_MODE_LOCALOS_FOR_PARTNER,
    build_preview,
    persist_preview,
    record_campaign_event,
)
from services.outreach_personalization_ai import (
    PROMPT_VERSION,
    REVIEW_PROMPT_VERSION,
    generation_contract_current,
)


TERMINAL_STATES = {
    "replied",
    "converted",
    "closed_lost",
    "not_relevant",
    "suppressed",
    "unsubscribed",
    "hard_no",
    "closed",
}
ACTIVE_ENRICHMENT_STATES = {
    "queued",
    "collecting",
    "verifying",
    "researching",
    "drafting",
    "retry_wait",
}
BLOCKING_CAMPAIGN_STATES = {"approved", "active", "paused"}
DEFAULT_BATCH_SIZE = 25
DEFAULT_FRESHNESS_DAYS = 7


def _text(value: Any) -> str:
    return str(value or "").strip()


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _scope_sender_mode(workstream_type: str) -> str:
    if workstream_type == "localos_sales":
        return SENDER_MODE_LOCALOS
    if workstream_type == "client_partnership":
        return SENDER_MODE_LOCALOS_FOR_PARTNER
    raise ValueError("Unsupported workstream_type")


def _load_actor_id(cursor: Any, requested_actor_id: str | None) -> str:
    if requested_actor_id:
        cursor.execute(
            "SELECT id FROM users WHERE id = %s AND is_superadmin = TRUE AND is_active = TRUE",
            (requested_actor_id,),
        )
    else:
        cursor.execute(
            """
            SELECT id FROM users
            WHERE is_superadmin = TRUE AND is_active = TRUE
            ORDER BY updated_at DESC NULLS LAST, created_at ASC
            LIMIT 1
            """
        )
    row = cursor.fetchone()
    if not row:
        raise LookupError("Active superadmin actor not found")
    return _text(row.get("id"))


def _load_platform_email_sender(cursor: Any) -> str | None:
    cursor.execute(
        """
        SELECT id
        FROM outreach_sender_accounts
        WHERE scope_type = 'platform'
          AND channel = 'email'
          AND sender_identity = 'localosgo@gmail.com'
          AND status = 'connected'
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return _text(row.get("id")) if row else None


def _sequence(email_sender_id: str | None) -> list[dict[str, Any]]:
    email_touch: dict[str, Any] = {
        "channel": "email",
        "day_offset": 3,
        "angle": "founder_story",
    }
    if email_sender_id:
        email_touch["sender_account_id"] = email_sender_id
    return [
        {"channel": "telegram", "day_offset": 0, "angle": "signal"},
        email_touch,
        {"channel": "next", "day_offset": 7, "angle": "proof"},
        {"channel": "next", "day_offset": 12, "angle": "respectful_close"},
    ]


def _candidate_query(
    workstream_type: str,
    business_ids: list[str],
    workstream_ids: list[str],
    limit: int | None,
) -> tuple[str, list[Any]]:
    filters = ["ws.workstream_type = %s"]
    params: list[Any] = [workstream_type]
    if workstream_type == "client_partnership":
        if not business_ids:
            raise ValueError("At least one business_id is required for client_partnership")
        filters.append("ws.client_business_id = ANY(%s)")
        params.append(business_ids)
    if workstream_ids:
        filters.append("ws.id::text = ANY(%s)")
        params.append(workstream_ids)
    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT %s"
        params.append(max(1, limit))
    query = f"""
        SELECT ws.id, ws.lead_id, ws.workstream_type, ws.client_business_id,
               ws.lifecycle_status, ws.status AS workstream_status,
               ws.last_contact_at AS workstream_last_contact_at,
               lead.name AS lead_name, lead.pipeline_status, lead.status AS lead_status,
               lead.last_contact_at AS lead_last_contact_at,
               latest_job.status AS enrichment_status,
               latest_job.updated_at AS enrichment_updated_at,
               COALESCE(contact_counts.contact_count, 0) AS contact_count,
               COALESCE(research_counts.evidence_count, 0) AS evidence_count,
               research_counts.message_readiness_json,
               latest_campaign.id AS latest_campaign_id,
               latest_campaign.status AS latest_campaign_status,
               latest_campaign.stop_reason AS latest_campaign_stop_reason,
               latest_campaign.last_reply_at AS latest_campaign_last_reply_at,
               EXISTS (
                   SELECT 1 FROM outreach_campaigns active_campaign
                   WHERE active_campaign.workstream_id = ws.id
                     AND active_campaign.status IN ('approved', 'active', 'paused')
               ) AS has_blocking_campaign,
               EXISTS (
                   SELECT 1 FROM outreach_suppressions suppression
                   WHERE suppression.lead_id = ws.lead_id
                     AND (suppression.expires_at IS NULL OR suppression.expires_at > NOW())
                     AND (
                         suppression.scope_type = 'platform_safety'
                         OR (
                             suppression.scope_type = CASE
                                 WHEN ws.workstream_type = 'localos_sales' THEN 'platform'
                                 ELSE 'business'
                             END
                             AND COALESCE(suppression.business_id, '') = COALESCE(ws.client_business_id, '')
                         )
                     )
               ) AS suppressed
        FROM lead_workstreams ws
        JOIN prospectingleads lead ON lead.id = ws.lead_id
        LEFT JOIN LATERAL (
            SELECT job.status, job.updated_at
            FROM lead_enrichment_jobs job
            WHERE job.workstream_id = ws.id
            ORDER BY job.created_at DESC
            LIMIT 1
        ) latest_job ON TRUE
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS contact_count
            FROM lead_contact_points contact
            WHERE contact.lead_id = ws.lead_id
              AND contact.verification_status NOT IN ('invalid', 'stale')
        ) contact_counts ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_array_length(COALESCE(research.evidence_json, '[]'::jsonb)) AS evidence_count,
                   research.message_readiness_json
            FROM lead_workstream_research research
            WHERE research.workstream_id = ws.id
            ORDER BY research.researched_at DESC NULLS LAST, research.created_at DESC
            LIMIT 1
        ) research_counts ON TRUE
        LEFT JOIN LATERAL (
            SELECT campaign.id, campaign.status, campaign.stop_reason,
                   campaign.last_reply_at, campaign.version
            FROM outreach_campaigns campaign
            WHERE campaign.workstream_id = ws.id
            ORDER BY campaign.version DESC
            LIMIT 1
        ) latest_campaign ON TRUE
        WHERE {' AND '.join(filters)}
        ORDER BY ws.updated_at ASC, ws.id
        {limit_sql}
    """
    return query, params


def _blocked_reason(row: dict[str, Any], now: datetime) -> str | None:
    states = {
        _text(row.get("lifecycle_status")).lower(),
        _text(row.get("workstream_status")).lower(),
        _text(row.get("pipeline_status")).lower(),
        _text(row.get("lead_status")).lower(),
    }
    if states.intersection(TERMINAL_STATES):
        return "terminal_state"
    if row.get("suppressed"):
        return "suppressed"
    if row.get("has_blocking_campaign"):
        return "campaign_already_active"
    if row.get("latest_campaign_last_reply_at"):
        return "recipient_replied"
    if _text(row.get("latest_campaign_stop_reason")) == "recipient_replied":
        return "recipient_replied"
    cutoff = now - timedelta(hours=24)
    for key in ("workstream_last_contact_at", "lead_last_contact_at"):
        value = row.get(key)
        if isinstance(value, datetime):
            current = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            if current.astimezone(timezone.utc) > cutoff:
                return "contact_cooldown"
    return None


def _preparation_contract(sender_mode: str) -> str:
    return f"{PROMPT_VERSION}:{REVIEW_PROMPT_VERSION}:{sender_mode}"


def _preparation_prerequisite(row: dict[str, Any], sender_mode: str) -> str | None:
    """Return a recoverable data blocker before spending an AI generation call."""
    enrichment_status = _text(row.get("enrichment_status")).lower()
    if enrichment_status in ACTIVE_ENRICHMENT_STATES:
        return "enrichment_in_progress"
    if not int(row.get("contact_count") or 0):
        return "needs_contact"
    if not int(row.get("evidence_count") or 0):
        return "needs_evidence"
    readiness = (
        row.get("message_readiness_json")
        if isinstance(row.get("message_readiness_json"), dict)
        else {}
    )
    if (
        readiness.get("source") == "outreach_batch_preparation"
        and readiness.get("contract") == _preparation_contract(sender_mode)
        and _text(readiness.get("code"))
        in {"needs_evidence", "invalid_sequence"}
    ):
        return _text(readiness.get("code"))
    return None


def _save_preparation_blocker(
    cursor: Any,
    *,
    workstream_id: str,
    sender_mode: str,
    preview: dict[str, Any],
) -> None:
    quality_gate = preview.get("quality_gate") if isinstance(preview.get("quality_gate"), dict) else {}
    payload = {
        "code": _text(preview.get("status")) or "needs_evidence",
        "label": "Нужна дополнительная проверка перед черновиком",
        "missing": list(preview.get("missing") or []),
        "reason_codes": list(quality_gate.get("reason_codes") or []),
        "source": "outreach_batch_preparation",
        "sender_mode": sender_mode,
        "contract": _preparation_contract(sender_mode),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    cursor.execute(
        """
        UPDATE lead_workstream_research
        SET message_readiness_json = %s,
            researched_at = COALESCE(researched_at, NOW())
        WHERE id = (
            SELECT id FROM lead_workstream_research
            WHERE workstream_id = %s
            ORDER BY researched_at DESC NULLS LAST, created_at DESC
            LIMIT 1
        )
        """,
        (Json(payload), workstream_id),
    )


def _enforce_complete_sequence(preview: dict[str, Any]) -> dict[str, Any]:
    """Reject previews that cannot represent the approved four-touch cadence.

    ``build_preview`` may legitimately return ``needs_channel_setup`` with only
    the channels that exist for the recipient.  Such a preview is useful in the
    UI, but it is not a complete campaign draft and must not be versioned by the
    bulk runner.  Persisting it also made every following run regenerate the
    same workstream because a current campaign requires four touches.
    """
    touches = preview.get("touches") if isinstance(preview.get("touches"), list) else []
    status = _text(preview.get("status")) or "unknown"
    if not touches and status not in {"ready", "needs_channel_setup"}:
        return preview
    indexes = [touch.get("sequence_index") for touch in touches if isinstance(touch, dict)]
    if len(touches) == 4 and indexes == [0, 1, 2, 3]:
        return preview
    missing = list(preview.get("missing") or [])
    if "four_touch_sequence" not in missing:
        missing.append("four_touch_sequence")
    return {
        **preview,
        "status": "invalid_sequence",
        "missing": missing,
    }


def _sequence_is_complete(preview: dict[str, Any]) -> bool:
    touches = preview.get("touches") if isinstance(preview.get("touches"), list) else []
    indexes = [touch.get("sequence_index") for touch in touches if isinstance(touch, dict)]
    return len(touches) == 4 and indexes == [0, 1, 2, 3]


def _load_candidates(
    cursor: Any,
    *,
    workstream_type: str,
    business_ids: list[str],
    workstream_ids: list[str],
    limit: int | None,
) -> list[dict[str, Any]]:
    query, params = _candidate_query(
        workstream_type,
        business_ids,
        workstream_ids,
        limit,
    )
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def _campaign_is_current(cursor: Any, campaign_id: str, sender_mode: str) -> bool:
    cursor.execute(
        "SELECT policy_json FROM outreach_campaigns WHERE id = %s AND status = 'draft'",
        (campaign_id,),
    )
    row = cursor.fetchone()
    if not row:
        return False
    policy = row.get("policy_json") if isinstance(row.get("policy_json"), dict) else {}
    if _text(policy.get("sender_mode")) != sender_mode:
        return False
    cursor.execute(
        """
        SELECT message_brief_json, quality_gate_json
        FROM outreach_campaign_touches
        WHERE campaign_id = %s
        ORDER BY sequence_index
        """,
        (campaign_id,),
    )
    touches = [dict(item) for item in cursor.fetchall()]
    return len(touches) == 4 and all(
        generation_contract_current(
            touch.get("message_brief_json"),
            touch.get("quality_gate_json"),
        )
        for touch in touches
    )


def inventory(
    *,
    workstream_type: str,
    business_ids: list[str] | None = None,
    workstream_ids: list[str] | None = None,
    limit: int | None = None,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        rows = _load_candidates(
            cursor,
            workstream_type=workstream_type,
            business_ids=business_ids or [],
            workstream_ids=workstream_ids or [],
            limit=limit,
        )
        now = datetime.now(timezone.utc)
        freshness_cutoff = now - timedelta(days=max(1, freshness_days))
        counts: Counter[str] = Counter()
        items = []
        sender_mode = _scope_sender_mode(workstream_type)
        for row in rows:
            blocked = _blocked_reason(row, now)
            readiness = (
                row.get("message_readiness_json")
                if isinstance(row.get("message_readiness_json"), dict)
                else {}
            )
            readiness_code = ""
            if (
                readiness.get("source") == "outreach_batch_preparation"
                and readiness.get("contract") == _preparation_contract(sender_mode)
            ):
                readiness_code = _text(readiness.get("code"))
            latest_campaign_id = _text(row.get("latest_campaign_id"))
            current_draft = bool(
                not blocked
                and latest_campaign_id
                and row.get("latest_campaign_status") == "draft"
                and _campaign_is_current(cursor, latest_campaign_id, sender_mode)
            )
            updated_at = row.get("enrichment_updated_at")
            enrichment_fresh = False
            if isinstance(updated_at, datetime):
                current_updated = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
                enrichment_fresh = current_updated.astimezone(timezone.utc) >= freshness_cutoff
            if blocked:
                state = blocked
            elif current_draft:
                state = "draft_current"
            elif readiness_code == "invalid_sequence":
                state = "needs_contact"
            elif readiness_code == "needs_evidence":
                state = "needs_evidence"
            elif row.get("latest_campaign_status") == "draft":
                state = "draft_requires_regeneration"
            elif row.get("enrichment_status") == "ready" and enrichment_fresh:
                state = "ready_for_campaign"
            elif not int(row.get("contact_count") or 0):
                state = "needs_contact"
            elif not int(row.get("evidence_count") or 0):
                state = "needs_evidence"
            else:
                state = "needs_refresh"
            counts[state] += 1
            items.append({
                "workstream_id": _text(row.get("id")),
                "lead_id": _text(row.get("lead_id")),
                "lead_name": _text(row.get("lead_name")),
                "state": state,
                "enrichment_status": row.get("enrichment_status"),
                "contact_count": int(row.get("contact_count") or 0),
                "evidence_count": int(row.get("evidence_count") or 0),
                "latest_campaign_id": latest_campaign_id or None,
            })
        return {
            "mode": "inventory",
            "workstream_type": workstream_type,
            "business_ids": business_ids or [],
            "total": len(items),
            "counts": dict(sorted(counts.items())),
            "items": items,
        }
    finally:
        conn.close()


def enqueue_enrichment(
    *,
    workstream_type: str,
    business_ids: list[str] | None = None,
    workstream_ids: list[str] | None = None,
    limit: int | None = None,
    execute: bool = False,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
) -> dict[str, Any]:
    snapshot = inventory(
        workstream_type=workstream_type,
        business_ids=business_ids,
        workstream_ids=workstream_ids,
        limit=limit,
        freshness_days=freshness_days,
    )
    eligible_states = {"needs_contact", "needs_evidence", "needs_refresh"}
    targets = [item for item in snapshot["items"] if item["state"] in eligible_states]
    result: dict[str, Any] = {
        "mode": "enqueue_enrichment",
        "execute": execute,
        "planned": len(targets),
        "queued": 0,
        "reused": 0,
        "skipped_active": 0,
        "errors": [],
        "job_ids": [],
    }
    if not execute:
        return result
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        for item in targets:
            try:
                cursor.execute(
                    """
                    SELECT status FROM lead_enrichment_jobs
                    WHERE workstream_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (item["workstream_id"],),
                )
                latest = cursor.fetchone()
                if latest and _text(latest.get("status")) in ACTIVE_ENRICHMENT_STATES:
                    result["skipped_active"] += 1
                    continue
                job = enqueue_enrichment_job(
                    cursor,
                    item["workstream_id"],
                    force=True,
                    allow_paid_enrichment=False,
                )
                conn.commit()
                result["job_ids"].append(_text(job.get("id")))
                if job.get("reused"):
                    result["reused"] += 1
                else:
                    result["queued"] += 1
            except Exception as exc:
                conn.rollback()
                result["errors"].append({
                    "workstream_id": item["workstream_id"],
                    "error": str(exc),
                })
        return result
    finally:
        conn.close()


def prepare_campaigns(
    *,
    workstream_type: str,
    business_ids: list[str] | None = None,
    workstream_ids: list[str] | None = None,
    limit: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    execute: bool = False,
    actor_id: str | None = None,
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        actor = _load_actor_id(cursor, actor_id)
        email_sender_id = _load_platform_email_sender(cursor)
        rows = _load_candidates(
            cursor,
            workstream_type=workstream_type,
            business_ids=business_ids or [],
            workstream_ids=workstream_ids or [],
            limit=limit,
        )
    finally:
        conn.close()

    now = datetime.now(timezone.utc)
    sender_mode = _scope_sender_mode(workstream_type)
    result: dict[str, Any] = {
        "mode": "prepare_campaigns",
        "execute": execute,
        "workstream_type": workstream_type,
        "business_ids": business_ids or [],
        "planned": len(rows),
        "attempted": 0,
        "batch_size": max(1, batch_size),
        "created": 0,
        "already_current": 0,
        "superseded": 0,
        "blocked": Counter(),
        "preview_states": Counter(),
        "campaigns": [],
        "errors": [],
        "email_sender_id": email_sender_id,
    }
    for row in rows:
        blocked = _blocked_reason(row, now)
        if blocked:
            result["blocked"][blocked] += 1
            continue
        prerequisite = _preparation_prerequisite(row, sender_mode)
        if prerequisite:
            result["blocked"][prerequisite] += 1
            continue
        latest_campaign_id = _text(row.get("latest_campaign_id"))
        latest_campaign_status = _text(row.get("latest_campaign_status"))
        item_conn = get_db_connection()
        try:
            item_cursor = item_conn.cursor(cursor_factory=RealDictCursor)
            item_cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"outreach-draft:{_text(row.get('id'))}",),
            )
            if (
                latest_campaign_id
                and latest_campaign_status == "draft"
                and _campaign_is_current(item_cursor, latest_campaign_id, sender_mode)
            ):
                item_conn.rollback()
                result["already_current"] += 1
                continue
            if result["attempted"] >= max(1, batch_size):
                item_conn.rollback()
                break
            result["attempted"] += 1
            if not execute:
                item_conn.rollback()
                result["preview_states"]["would_preview"] += 1
                continue
            preflight_preview = build_preview(
                item_cursor,
                _text(row.get("id")),
                sequence=_sequence(email_sender_id),
                sender_mode=sender_mode,
                generate_ai=False,
            )
            preflight_preview = _enforce_complete_sequence(preflight_preview)
            preflight_status = _text(preflight_preview.get("status")) or "unknown"
            # The deterministic, AI-disabled text can fail the content gate even
            # when evidence and all four channels are present.  Its only job here
            # is structural channel preflight; complete sequences still proceed
            # to the canonical AI generation and semantic review.
            if (
                not _sequence_is_complete(preflight_preview)
                and preflight_status not in {"ready", "needs_channel_setup"}
            ):
                result["preview_states"][preflight_status] += 1
                _save_preparation_blocker(
                    item_cursor,
                    workstream_id=_text(row.get("id")),
                    sender_mode=sender_mode,
                    preview=preflight_preview,
                )
                item_conn.commit()
                continue
            preview = build_preview(
                item_cursor,
                _text(row.get("id")),
                sequence=_sequence(email_sender_id),
                sender_mode=sender_mode,
            )
            preview = _enforce_complete_sequence(preview)
            preview_status = _text(preview.get("status")) or "unknown"
            result["preview_states"][preview_status] += 1
            if preview_status not in {"ready", "needs_channel_setup"}:
                _save_preparation_blocker(
                    item_cursor,
                    workstream_id=_text(row.get("id")),
                    sender_mode=sender_mode,
                    preview=preview,
                )
                item_conn.commit()
                continue
            campaign = persist_preview(item_cursor, preview, user_id=actor)
            if latest_campaign_id and latest_campaign_status == "draft":
                item_cursor.execute(
                    """
                    UPDATE outreach_campaigns
                    SET status = 'cancelled',
                        stop_reason = 'superseded_generation_contract',
                        updated_at = NOW()
                    WHERE id = %s AND status = 'draft'
                    """,
                    (latest_campaign_id,),
                )
                if item_cursor.rowcount:
                    record_campaign_event(
                        item_cursor,
                        latest_campaign_id,
                        "campaign_superseded",
                        actor_id=actor,
                        payload={"replacement_campaign_id": campaign["id"]},
                    )
                    result["superseded"] += 1
            item_conn.commit()
            result["created"] += 1
            result["campaigns"].append({
                "campaign_id": campaign["id"],
                "version": campaign["version"],
                "workstream_id": _text(row.get("id")),
                "lead_id": _text(row.get("lead_id")),
                "lead_name": _text(row.get("lead_name")),
                "preview_status": preview_status,
            })
        except Exception as exc:
            item_conn.rollback()
            result["errors"].append({
                "workstream_id": _text(row.get("id")),
                "lead_id": _text(row.get("lead_id")),
                "error": str(exc),
            })
        finally:
            item_conn.close()
    result["blocked"] = dict(sorted(result["blocked"].items()))
    result["preview_states"] = dict(sorted(result["preview_states"].items()))
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory, enrich, or prepare draft-only LocalOS outreach campaigns",
    )
    parser.add_argument(
        "--action",
        choices=("inventory", "enqueue-enrichment", "prepare"),
        default="inventory",
    )
    parser.add_argument(
        "--workstream-type",
        choices=("localos_sales", "client_partnership"),
        required=True,
    )
    parser.add_argument("--business-id", action="append", default=[])
    parser.add_argument("--workstream-id", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--freshness-days", type=int, default=DEFAULT_FRESHNESS_DAYS)
    parser.add_argument("--actor-id")
    parser.add_argument("--execute", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    effective_limit = args.limit
    if args.action == "inventory":
        result = inventory(
            workstream_type=args.workstream_type,
            business_ids=args.business_id,
            workstream_ids=args.workstream_id,
            limit=effective_limit,
            freshness_days=args.freshness_days,
        )
    elif args.action == "enqueue-enrichment":
        result = enqueue_enrichment(
            workstream_type=args.workstream_type,
            business_ids=args.business_id,
            workstream_ids=args.workstream_id,
            limit=effective_limit,
            execute=args.execute,
            freshness_days=args.freshness_days,
        )
    else:
        result = prepare_campaigns(
            workstream_type=args.workstream_type,
            business_ids=args.business_id,
            workstream_ids=args.workstream_id,
            limit=effective_limit,
            batch_size=max(1, min(args.batch_size, 100)),
            execute=args.execute,
            actor_id=args.actor_id,
        )
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
