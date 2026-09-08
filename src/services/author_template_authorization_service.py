"""Revocable platform approval for the exact LocalOS author invitation.

Authority comes from server-written sender permission events, never from a
creator's mutable campaign constraints or a caller-supplied approval flag.
All ordinary recipient, history, sender and daily admission gates still apply.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from psycopg2.extras import Json

from services.outreach_template_service import (
    CREATOR_NAME_ONLY_TEMPLATE_KEY,
    CREATOR_NAME_ONLY_TEMPLATE_VERSION,
    CREATOR_NAME_ONLY_SUBJECT_TEMPLATE,
    CREATOR_NAME_ONLY_BODY_TEMPLATE,
    TEMPLATE_LIBRARY_VERSION,
    render_creator_invitation_template,
)

PERMISSION_KIND = "localos_author_template"
SENDER_IDENTITY = "localosgo@gmail.com"
DAILY_LIMIT = 150
AUTHORIZATION_VERSION = 1


def template_manifest() -> dict[str, Any]:
    # Hash the same immutable text constants used by the production renderer.
    definition = {
        "key": CREATOR_NAME_ONLY_TEMPLATE_KEY,
        "version": CREATOR_NAME_ONLY_TEMPLATE_VERSION,
        "library_version": TEMPLATE_LIBRARY_VERSION,
        "subject": CREATOR_NAME_ONLY_SUBJECT_TEMPLATE,
        "body": CREATOR_NAME_ONLY_BODY_TEMPLATE,
    }
    digest = hashlib.sha256(json.dumps(
        definition, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "authorization_version": AUTHORIZATION_VERSION,
        "scope": "localos_author_first_invitation",
        "workstream_type": "creator_collaboration",
        "sender_mode": "localos_for_partner",
        "sender_identity": SENDER_IDENTITY,
        "channels": ["email"],
        "daily_limit": DAILY_LIMIT,
        "timezone": "Europe/Moscow",
        "stop_on_reply": True,
        "template_key": CREATOR_NAME_ONLY_TEMPLATE_KEY,
        "template_version": CREATOR_NAME_ONLY_TEMPLATE_VERSION,
        "template_definition_sha256": digest,
    }


def _canonical_sender(cursor: Any, sender_account_id: str | None = None) -> dict[str, Any]:
    cursor.execute(
        """SELECT id, owner_user_id, status, outreach_enabled, health_status,
                  capabilities_json
           FROM outreach_sender_accounts
           WHERE scope_type = 'platform' AND business_id IS NULL
             AND channel = 'email' AND lower(btrim(sender_identity)) = %s
             AND (%s::text IS NULL OR id::text = %s)
           ORDER BY id LIMIT 2""",
        (SENDER_IDENTITY, sender_account_id, sender_account_id),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    return rows[0] if len(rows) == 1 else {}


def _latest_event(cursor: Any, sender_account_id: str) -> dict[str, Any]:
    cursor.execute(
        """SELECT event.id, event.sender_account_id, event.actor_id,
                  event.payload_json, event.created_at,
                  COALESCE(actor.is_active, FALSE) AND
                  COALESCE(actor.is_superadmin, FALSE) AS actor_authorized
           FROM outreach_sender_account_events event
           LEFT JOIN users actor ON actor.id = event.actor_id
           WHERE event.sender_account_id = %s
             AND event.event_type = 'permission_changed'
             AND event.payload_json->>'permission_kind' = %s
           ORDER BY event.created_at DESC, event.id DESC LIMIT 1""",
        (sender_account_id, PERMISSION_KIND),
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def load_author_template_authorization(
    cursor: Any, *, sender_account_id: str | None = None,
) -> dict[str, Any]:
    sender = _canonical_sender(cursor, sender_account_id)
    if not sender:
        return {}
    event = _latest_event(cursor, str(sender["id"]))
    payload = event.get("payload_json") or {}
    if not isinstance(payload, dict):
        return {}
    if (not event.get("actor_authorized") or not event.get("created_at")
            or payload.get("state") != "active"
            or payload.get("manifest") != template_manifest()
            or payload.get("grant_id") != str(event.get("id"))):
        return {}
    capabilities = sender.get("capabilities_json") or {}
    if (sender.get("status") != "connected" or not sender.get("outreach_enabled")
            or sender.get("health_status") in {"paused", "blocked"}
            or not isinstance(capabilities, dict)
            or not capabilities.get("direct_send") or not capabilities.get("reply_sync")):
        return {}
    return {
        "id": str(event["id"]), "sender_account_id": str(sender["id"]),
        "approved_by": str(event["actor_id"]), "approved_at": event["created_at"],
        "manifest": payload["manifest"],
        "authorization_reference": payload.get("authorization_reference"),
    }


def set_author_template_authorization(
    cursor: Any, *, sender_account_id: str, actor_id: str,
    enabled: bool, authorization_reference: str,
) -> dict[str, Any]:
    """Called only with an authenticated superadmin or authorized server operator.

    API callers must derive actor_id from the authenticated request, not JSON.
    This function records the real approval source; it does not send messages.
    """
    cursor.execute(
        "SELECT id FROM users WHERE id = %s AND is_active = TRUE AND is_superadmin = TRUE",
        (actor_id,),
    )
    if not cursor.fetchone():
        raise PermissionError("author_template_superadmin_required")
    if type(enabled) is not bool or not str(authorization_reference or "").strip():
        raise ValueError("author_template_explicit_decision_required")
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"author-template:{sender_account_id}",))
    sender = _canonical_sender(cursor, sender_account_id)
    if not sender:
        raise ValueError("author_template_sender_scope_invalid")
    previous = _latest_event(cursor, sender_account_id)
    previous_payload = previous.get("payload_json") or {}
    if not isinstance(previous_payload, dict):
        previous_payload = {}
    manifest = template_manifest()
    state = "active" if enabled else "revoked"
    if (previous.get("actor_authorized") and isinstance(previous_payload, dict)
            and previous_payload.get("state") == state
            and previous_payload.get("manifest") == manifest):
        return {"id": str(previous["id"]), "state": state, "unchanged": True, "manifest": manifest}
    event_id = str(uuid.uuid4())
    payload = {
        "permission_kind": PERMISSION_KIND, "state": state,
        "grant_id": event_id if enabled else previous_payload.get("grant_id"),
        "manifest": manifest,
        "authorization_reference": str(authorization_reference).strip(),
        "replaces_event_id": str(previous["id"]) if previous else None,
    }
    cursor.execute(
        """INSERT INTO outreach_sender_account_events
           (id, sender_account_id, event_type, actor_id, payload_json, created_at)
           VALUES (%s, %s, 'permission_changed', %s, %s, clock_timestamp())""",
        (event_id, sender_account_id, actor_id, Json(payload)),
    )
    return {"id": event_id, "state": state, "unchanged": False, "manifest": manifest}


def exact_author_invitation(
    *, bridge: dict[str, Any], subject: str, body: str,
    authorization: dict[str, Any], sender_account_id: str,
    channel: str, sequence_index: int,
) -> bool:
    rendered = render_creator_invitation_template(bridge)
    return bool(
        bridge.get("status") == "ready"
        and authorization.get("id") and authorization.get("approved_by")
        and authorization.get("manifest") == template_manifest()
        and authorization.get("sender_account_id") == str(sender_account_id)
        and channel == "email" and sequence_index == 0
        and rendered and rendered.get("key") == CREATOR_NAME_ONLY_TEMPLATE_KEY
        and subject == rendered["subject"] and body == rendered["body"]
    )


def previously_contacted_author(cursor: Any, *, creator_profile_id: str, recipient: str, queue_id: str) -> bool:
    """All-time first-touch dedup, including old providers and uncertain sends."""
    import re
    normalized = re.sub(r"\s+", "", str(recipient or "")).lower()
    cursor.execute(
        """WITH history AS (
            SELECT creator.id::text AS creator_id,
                   lower(regexp_replace(COALESCE(NULLIF(queue.recipient_value, ''), contact.normalized_value, ''), '\\s+', '', 'g')) AS recipient
            FROM outreachsendqueue queue
            JOIN outreach_campaign_touches touch ON touch.id=queue.campaign_touch_id
            JOIN outreach_campaigns campaign ON campaign.id=touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id=queue.workstream_id
            JOIN prospectingleads lead ON lead.id=queue.lead_id
            JOIN creator_profiles creator ON lead.source_external_id='creator:' || creator.id::text
            LEFT JOIN lead_contact_points contact ON contact.id=touch.contact_point_id
            WHERE queue.id::text <> %s
              AND workstream.workstream_type='creator_collaboration'
              AND campaign.sender_mode='localos_for_partner'
              AND (queue.delivery_status IN ('sent', 'delivered')
                   OR lower(COALESCE(queue.error_text, '')) LIKE '%%send_uncertain%%')
            UNION ALL
            SELECT creator.id::text,
                   lower(regexp_replace(COALESCE(event.payload_json->>'recipient_value', contact.normalized_value, ''), '\\s+', '', 'g'))
            FROM outreach_campaign_events event
            JOIN outreach_campaign_touches touch ON touch.id=event.touch_id
            JOIN outreach_campaigns campaign ON campaign.id=event.campaign_id
            JOIN lead_workstreams workstream ON workstream.id=campaign.workstream_id
            JOIN prospectingleads lead ON lead.id=campaign.lead_id
            JOIN creator_profiles creator ON lead.source_external_id='creator:' || creator.id::text
            LEFT JOIN lead_contact_points contact ON contact.id=touch.contact_point_id
            WHERE workstream.workstream_type='creator_collaboration'
              AND campaign.sender_mode='localos_for_partner'
              AND event.event_type IN ('manual_sent', 'manual_reply')
        ) SELECT 1 FROM history
          WHERE creator_id=%s OR (%s <> '' AND recipient=%s) LIMIT 1""",
        (queue_id, creator_profile_id, normalized, normalized),
    )
    return bool(cursor.fetchone())
