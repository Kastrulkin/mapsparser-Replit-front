#!/usr/bin/env python3
"""Dry-run/apply the campaign-independent creator relationship ledger."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime

from psycopg2.extras import Json, RealDictCursor

from database_manager import DatabaseManager
from services.creator_portal_service import add_contact_event, ensure_relationship, set_relationship_stage


STAGE_BY_OUTCOME = {
    "interested": "interested",
    "question": "needs_details",
    "needs_details": "needs_details",
    "not_interested": "declined",
    "declined": "declined",
    "paid_only": "paid_only",
}


def value(raw, fallback):
    if raw is None:
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def stable_id(kind: str, collaboration_id: str, provider_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:creator:{kind}:{collaboration_id}:{provider_id}"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = DatabaseManager()
    cursor = db.conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT c.id, c.creator_profile_id, c.campaign_id, c.status, c.agreed_terms_json,
                   p.display_name
            FROM creator_collaborations c JOIN creator_profiles p ON p.id = c.creator_profile_id
            ORDER BY c.updated_at
            """
        )
        rows = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT candidate.id AS candidate_id, candidate.creator_profile_id,
                   campaign.id AS campaign_id, campaign.business_id, campaign.created_by,
                   campaign.offer_json
            FROM creator_campaign_candidates candidate
            JOIN creator_campaigns campaign ON campaign.id = candidate.campaign_id
            LEFT JOIN creator_collaborations collaboration ON collaboration.campaign_candidate_id = candidate.id
            WHERE collaboration.id IS NULL AND campaign.status IN ('approved', 'active')
              AND candidate.status <> 'removed'
            """
        )
        missing_collaborations = [dict(row) for row in cursor.fetchall()]
        preview = {"collaborations": len(rows), "sent": 0, "bounced": 0, "replied": 0,
                   "interested": 0, "needs_details": 0, "not_current_barter": 0,
                   "missing_collaborations": len(missing_collaborations)}
        if args.apply:
            for item in missing_collaborations:
                collaboration_id = stable_id("collaboration", str(item["candidate_id"]), str(item["campaign_id"]))
                cursor.execute(
                    """
                    INSERT INTO creator_collaborations (
                        id, campaign_id, campaign_candidate_id, business_id, creator_profile_id,
                        status, agreed_terms_json, owner_user_id, review_status
                    ) VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s, 'needs_review')
                    ON CONFLICT (campaign_candidate_id) DO NOTHING
                    """,
                    (collaboration_id, item["campaign_id"], item["candidate_id"], item["business_id"],
                     item["creator_profile_id"], Json({"offer": value(item.get("offer_json"), {})}), item.get("created_by")),
                )
        for row in rows:
            terms = value(row.get("agreed_terms_json"), {})
            outreach = value(terms.get("outreach"), {})
            response = value(terms.get("response"), {})
            failure = value(terms.get("delivery_failure"), {})
            if outreach.get("recipient") or outreach.get("sent_at"):
                preview["sent"] += 1
            if failure:
                preview["bounced"] += 1
            if response:
                preview["replied"] += 1
                outcome = str(response.get("outcome") or "")
                if outcome == "interested":
                    preview["interested"] += 1
                elif outcome in {"question", "needs_details"}:
                    preview["needs_details"] += 1
                elif outcome in {"not_interested", "paid_only"}:
                    preview["not_current_barter"] += 1
            if not args.apply:
                continue
            profile_id = str(row["creator_profile_id"])
            ensure_relationship(cursor, profile_id)
            if outreach.get("recipient") or outreach.get("sent_at"):
                cursor.execute(
                    """
                    UPDATE creator_relationships SET stage = CASE WHEN stage IN ('discovered', 'contact_ready') THEN 'contacted' ELSE stage END,
                        primary_channel = COALESCE(%s, primary_channel), contact_value = COALESCE(%s, contact_value),
                        last_contacted_at = COALESCE(%s, last_contacted_at), updated_at = NOW()
                    WHERE creator_profile_id = %s
                    """,
                    (outreach.get("channel") or "email", outreach.get("recipient"), outreach.get("sent_at"), profile_id),
                )
                provider_id = str(outreach.get("provider_message_id") or outreach.get("message_id") or row["id"])
                add_contact_event(cursor, profile_id=profile_id, event_type="sent",
                                  channel=str(outreach.get("channel") or "email"),
                                  contact=outreach.get("recipient"), body=outreach.get("message"),
                                  occurred_at=outreach.get("sent_at"), source="campaign_backfill",
                                  campaign_id=str(row["campaign_id"]), collaboration_id=str(row["id"]),
                                  provider_message_id=provider_id, metadata={"backfill_id": stable_id("sent", str(row["id"]), provider_id)})
            if failure:
                set_relationship_stage(cursor, profile_id=profile_id, stage="invalid_contact", reason=str(failure.get("reason") or failure.get("error") or "Delivery failure"))
                provider_id = str(failure.get("provider_message_id") or row["id"])
                add_contact_event(cursor, profile_id=profile_id, event_type="bounce", channel=str(outreach.get("channel") or "email"),
                                  contact=outreach.get("recipient"), classification="invalid_contact",
                                  occurred_at=failure.get("occurred_at"), source="campaign_backfill",
                                  campaign_id=str(row["campaign_id"]), collaboration_id=str(row["id"]),
                                  provider_message_id=provider_id)
            if response:
                outcome = str(response.get("outcome") or "")
                stage = STAGE_BY_OUTCOME.get(outcome, "replied")
                set_relationship_stage(cursor, profile_id=profile_id, stage=stage,
                                       reason=str(response.get("summary") or response.get("body") or "")[:1000])
                provider_id = str(response.get("provider_message_id") or response.get("message_id") or row["id"])
                add_contact_event(cursor, profile_id=profile_id, event_type="reply",
                                  channel=str(outreach.get("channel") or "email"),
                                  contact=response.get("contact_email") or outreach.get("recipient"),
                                  body=response.get("body") or response.get("text"), classification=outcome or "replied",
                                  occurred_at=response.get("received_at"), source="campaign_backfill",
                                  campaign_id=str(row["campaign_id"]), collaboration_id=str(row["id"]),
                                  provider_message_id=provider_id)
        if args.apply:
            db.conn.commit()
        else:
            db.conn.rollback()
        print(json.dumps({"mode": "apply" if args.apply else "dry-run", **preview}, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
