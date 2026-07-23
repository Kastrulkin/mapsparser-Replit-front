"""Cross-channel safety, inbound classification, sender health and learning helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json

from services.outreach_personalization_ai import generation_contract_current


HUMAN_REPLY_CLASSIFICATIONS = {
    "interested",
    "question",
    "not_interested",
    "unsubscribe",
    "complaint",
    "human_unknown",
}
TERMINAL_REPLY_CLASSIFICATIONS = HUMAN_REPLY_CLASSIFICATIONS
TECHNICAL_CLASSIFICATIONS = {
    "out_of_office",
    "bounce",
    "temporary_delivery_failure",
    "permanent_delivery_failure",
    "system_acknowledgement",
}
SUPPRESSION_CLASSIFICATIONS = {"not_interested", "unsubscribe", "complaint"}
SENDER_BLOCKING_HEALTH = {"paused", "blocked"}


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _canonical_payload(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, prefix: str = "") -> str:
    digest = hashlib.sha256(_canonical_payload(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest}"


def normalized_contact_hash(contact_type: str, normalized_value: str) -> str:
    kind = str(contact_type or "").strip().lower()
    value = re.sub(r"\s+", "", str(normalized_value or "").strip().lower())
    return stable_hash({"type": kind, "value": value}, "contact:")


def recipient_key(lead_id: str, normalized_contacts: list[dict[str, Any]] | None = None) -> str:
    clean_lead_id = str(lead_id or "").strip()
    if clean_lead_id:
        return f"lead:{clean_lead_id}"
    contact_keys = sorted(
        normalized_contact_hash(item.get("contact_type"), item.get("normalized_value"))
        for item in (normalized_contacts or [])
        if item.get("contact_type") and item.get("normalized_value")
    )
    return stable_hash(contact_keys, "recipient:") if contact_keys else ""


def strategy_fingerprint(strategy: dict[str, Any]) -> str:
    dimensions = {
        "workstream_type": strategy.get("workstream_type"),
        "sender_mode": strategy.get("sender_mode"),
        "represented_business_id": strategy.get("represented_business_id"),
        "segment": strategy.get("segment"),
        "recipient_role": strategy.get("recipient_role"),
        "signal_kind": strategy.get("signal_kind"),
        "freshness": strategy.get("freshness"),
        "founder_story_id": strategy.get("founder_story_id"),
        "proof_id": strategy.get("proof_id"),
        "bridge_type": strategy.get("bridge_type"),
        "offer_id": strategy.get("offer_id"),
        "offer": strategy.get("offer"),
        "trust_strategy": strategy.get("trust_strategy"),
        "trust_statement": strategy.get("trust_statement"),
        "cta": strategy.get("cta"),
        "channel": strategy.get("channel"),
        "sequence_index": strategy.get("sequence_index"),
        "day_offset": strategy.get("day_offset"),
        "angle": strategy.get("angle"),
    }
    return stable_hash(dimensions, "strategy:")


def sender_scope_preflight_reason(item: dict[str, Any]) -> str | None:
    """Validate campaign identity against the concrete sender account scope."""
    policy = item.get("policy_json") if isinstance(item.get("policy_json"), dict) else {}
    sender_mode = str(policy.get("sender_mode") or "").strip().lower()
    if not sender_mode:
        sender_mode = "localos" if item.get("scope_type") == "platform" else "partner_business"
    if sender_mode == "localos_for_partner":
        if item.get("scope_type") != "business":
            return "sender_mode_scope_mismatch"
        if item.get("sender_scope_type") != "platform" or item.get("sender_business_id"):
            return "sender_scope_mismatch"
        represented_business_id = str(policy.get("represented_business_id") or "")
        if not represented_business_id or represented_business_id != str(item.get("business_id") or ""):
            return "represented_business_mismatch"
        return None
    if sender_mode == "localos":
        if item.get("scope_type") != "platform" or item.get("business_id"):
            return "sender_mode_scope_mismatch"
    elif sender_mode == "partner_business":
        if item.get("scope_type") != "business" or not item.get("business_id"):
            return "sender_mode_scope_mismatch"
    else:
        return "sender_mode_invalid"
    if sender_mode in {"localos", "partner_business"}:
        if item.get("sender_scope_type") != item.get("scope_type"):
            return "sender_scope_mismatch"
        if str(item.get("sender_business_id") or "") != str(item.get("business_id") or ""):
            return "sender_business_mismatch"
        return None
    return None


def approval_snapshot_hash(campaign: dict[str, Any], touches: list[dict[str, Any]]) -> str:
    snapshot = {
        "campaign_id": str(campaign.get("id") or ""),
        "version": int(campaign.get("version") or 0),
        "workstream_id": str(campaign.get("workstream_id") or ""),
        "lead_id": str(campaign.get("lead_id") or ""),
        "scope_type": campaign.get("scope_type"),
        "business_id": campaign.get("business_id"),
        "sender_profile_id": str(campaign.get("sender_profile_id") or ""),
        "policy": campaign.get("policy_json") or campaign.get("policy") or {},
        "touches": [
            {
                "id": str(touch.get("id") or ""),
                "sequence_index": int(touch.get("sequence_index") or 0),
                "channel": touch.get("channel"),
                "contact_point_id": str(touch.get("contact_point_id") or ""),
                "sender_account_id": str(touch.get("sender_account_id") or ""),
                "angle_type": touch.get("angle_type"),
                "scheduled_at": touch.get("scheduled_at"),
                "generated_text": touch.get("generated_text"),
                "subject": touch.get("subject"),
                "quality_gate_json": touch.get("quality_gate_json") or {},
            }
            for touch in sorted(touches, key=lambda item: int(item.get("sequence_index") or 0))
        ],
    }
    return stable_hash(snapshot, "approval:")


def classify_inbound_event(payload: dict[str, Any]) -> dict[str, Any]:
    explicit = str(payload.get("classification") or payload.get("event_type") or "").strip().lower()
    explicit_aliases = {
        "interested": "interested",
        "positive": "interested",
        "question": "question",
        "not_interested": "not_interested",
        "hard_no": "not_interested",
        "unsubscribe": "unsubscribe",
        "complaint": "complaint",
        "spam_complaint": "complaint",
        "out_of_office": "out_of_office",
        "auto_reply": "out_of_office",
        "bounce": "bounce",
        "temporary_delivery_failure": "temporary_delivery_failure",
        "permanent_delivery_failure": "permanent_delivery_failure",
        "system_acknowledgement": "system_acknowledgement",
    }
    classification = explicit_aliases.get(explicit)
    text = " ".join(
        str(payload.get(key) or "")
        for key in ("subject", "text", "body", "raw_reply", "reason")
    ).strip().lower()
    auto_submitted = str(payload.get("auto_submitted") or payload.get("Auto-Submitted") or "").strip().lower()
    precedence = str(payload.get("precedence") or payload.get("Precedence") or "").strip().lower()

    if not classification and (
        auto_submitted not in {"", "no"}
        or precedence in {"auto_reply", "bulk", "junk"}
        or re.search(r"\b(out of office|automatic reply|автоответ|в отпуске|отсутствую до)\b", text)
    ):
        classification = "out_of_office"
    if not classification and re.search(r"\b(mailbox unavailable|user unknown|address rejected|недоставлено|адрес не существует)\b", text):
        classification = "permanent_delivery_failure"
    if not classification and re.search(r"\b(temporarily unavailable|try again later|временно недоступ)\b", text):
        classification = "temporary_delivery_failure"
    if not classification and re.search(r"\b(unsubscribe|отпис|не пишите|удалите.*контакт)\b", text):
        classification = "unsubscribe"
    if not classification and re.search(r"\b(spam|жалоб|abuse)\b", text):
        classification = "complaint"
    if not classification and re.search(r"\b(не интерес|не актуал|откаж|no thanks|not interested)\b", text):
        classification = "not_interested"
    if not classification and "?" in text:
        classification = "question"
    if not classification and re.search(r"\b(интерес|давайте|пришлите|расскажите|готов обсудить|let's talk)\b", text):
        classification = "interested"
    if not classification:
        classification = "human_unknown"

    is_human = classification in HUMAN_REPLY_CLASSIFICATIONS
    return {
        "classification": classification,
        "is_human": is_human,
        "stops_campaign": classification in TERMINAL_REPLY_CLASSIFICATIONS,
        "creates_suppression": classification in SUPPRESSION_CLASSIFICATIONS,
        "confidence": 1.0 if explicit in explicit_aliases else (0.9 if classification in TECHNICAL_CLASSIFICATIONS else 0.7),
    }


def sender_health(metrics: dict[str, Any]) -> dict[str, Any]:
    sent = max(0, int(metrics.get("sent_count") or 0))
    bounce_count = max(0, int(metrics.get("bounce_count") or 0))
    complaint_count = max(0, int(metrics.get("complaint_count") or 0))
    rate_limit_count = max(0, int(metrics.get("rate_limit_count") or 0))
    flood_wait_seconds = max(0, int(metrics.get("flood_wait_seconds") or 0))
    blocked = bool(metrics.get("blocked"))
    auth_invalid = bool(metrics.get("auth_invalid"))
    bounce_rate = (bounce_count / sent) if sent else 0.0
    complaint_rate = (complaint_count / sent) if sent else 0.0
    score = 100
    score -= min(50, int(round(bounce_rate * 250)))
    score -= min(50, int(round(complaint_rate * 1000)))
    score -= min(30, rate_limit_count * 5)
    score -= min(30, flood_wait_seconds // 120)
    score = max(0, min(100, score))
    reasons: list[str] = []
    if blocked:
        reasons.append("provider_blocked")
    if auth_invalid:
        reasons.append("authorization_invalid")
    if complaint_rate >= 0.02:
        reasons.append("complaint_rate_critical")
    if bounce_rate >= 0.15:
        reasons.append("bounce_rate_critical")
    if flood_wait_seconds >= 900:
        reasons.append("provider_flood_wait")
    if blocked or auth_invalid:
        status = "blocked"
    elif complaint_rate >= 0.02 or bounce_rate >= 0.15 or flood_wait_seconds >= 900:
        status = "paused"
    elif complaint_rate >= 0.01 or bounce_rate >= 0.08 or rate_limit_count >= 3:
        status = "degraded"
    elif complaint_count > 0 or bounce_rate >= 0.03 or rate_limit_count > 0:
        status = "warning"
    else:
        status = "healthy"
    return {
        "status": status,
        "score": score,
        "reasons": reasons,
        "metrics": {
            **metrics,
            "bounce_rate": round(bounce_rate, 4),
            "complaint_rate": round(complaint_rate, 4),
        },
    }


def learning_sample_status(delivered_count: int) -> str:
    delivered = max(0, int(delivered_count or 0))
    if delivered < 20:
        return "insufficient_data"
    if delivered < 100:
        return "preliminary"
    return "reliable"


def learning_stat_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Derive comparable outcome rates without treating a small sample as proof."""
    sample_count = max(
        int(row.get("delivered_count") or 0),
        int(row.get("sent_count") or 0),
    )
    denominator = max(1, sample_count)
    positive_rate = int(row.get("positive_reply_count") or 0) / denominator
    hard_no_rate = int(row.get("hard_no_count") or 0) / denominator
    unsubscribe_rate = int(row.get("unsubscribe_count") or 0) / denominator
    complaint_rate = int(row.get("complaint_count") or 0) / denominator
    no_reply_rate = int(row.get("no_reply_count") or 0) / denominator
    meeting_rate = int(row.get("meeting_count") or 0) / denominator
    conversion_rate = int(row.get("converted_count") or 0) / denominator
    health_score = int(row.get("sender_health_score") or 100)
    health_factor = max(0.0, min(1.0, health_score / 100))
    safety_penalty = hard_no_rate + (2 * unsubscribe_rate) + (4 * complaint_rate)
    recommendation_status = row.get("recommendation_status")
    if row.get("sender_health_status") in {"degraded", "paused", "blocked"}:
        recommendation_status = "review_sender_health"
    return {
        "positive_reply_rate": round(positive_rate, 4),
        "hard_no_rate": round(hard_no_rate, 4),
        "unsubscribe_rate": round(unsubscribe_rate, 4),
        "complaint_rate": round(complaint_rate, 4),
        "no_reply_rate": round(no_reply_rate, 4),
        "meeting_rate": round(meeting_rate, 4),
        "conversion_rate": round(conversion_rate, 4),
        "health_adjusted_score": round(
            max(-1.0, min(1.0, (positive_rate - safety_penalty) * health_factor)),
            4,
        ),
        "recommendation_status": recommendation_status,
    }


def wilson_lower_bound(success_count: int, total_count: int, z_score: float = 1.96) -> float:
    successes = max(0, int(success_count or 0))
    total = max(0, int(total_count or 0))
    if total < 1:
        return 0.0
    proportion = min(1.0, successes / total)
    denominator = 1 + (z_score * z_score / total)
    center = proportion + (z_score * z_score / (2 * total))
    margin = z_score * math.sqrt(
        (proportion * (1 - proportion) / total) + (z_score * z_score / (4 * total * total))
    )
    return max(0.0, min(1.0, (center - margin) / denominator))


def run_dispatch_preflight(cursor: Any, queue_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT q.id, q.lead_id, q.workstream_id, q.campaign_touch_id,
               q.sender_account_id, q.delivery_status, q.recipient_key AS queue_recipient_key,
               t.id AS touch_id, t.status AS touch_status, t.channel,
               t.contact_point_id, t.strategy_fingerprint, t.sequence_index,
               c.id AS campaign_id, c.status AS campaign_status, c.scope_type,
               c.business_id, c.recipient_key AS campaign_recipient_key,
               c.version, c.workstream_id AS campaign_workstream_id,
               c.sender_profile_id, c.approved_at, c.approved_snapshot_hash, c.last_reply_at,
               c.policy_json, s.scope_type AS sender_scope_type,
               s.business_id AS sender_business_id, s.status AS sender_status,
               s.health_status, s.external_account_id, s.outreach_enabled AS sender_outreach_enabled,
               s.capabilities_json AS sender_capabilities_json,
               permission.outreach_enabled AS telegram_outreach_enabled,
               contact.contact_type, contact.normalized_value,
               contact.verification_status AS contact_verification_status
        FROM outreachsendqueue q
        LEFT JOIN outreach_campaign_touches t ON t.id = q.campaign_touch_id
        LEFT JOIN outreach_campaigns c ON c.id = t.campaign_id
        LEFT JOIN outreach_sender_accounts s ON s.id = q.sender_account_id
        LEFT JOIN telegram_account_permissions permission ON permission.account_id = s.external_account_id
        LEFT JOIN lead_contact_points contact ON contact.id = t.contact_point_id
        WHERE q.id = %s
        FOR UPDATE OF q
        """,
        (queue_id,),
    )
    item = _dict(cursor.fetchone())
    if not item:
        return {"allowed": False, "reason_code": "queue_item_missing"}
    if not item.get("campaign_touch_id"):
        return {"allowed": False, "reason_code": "campaign_approval_required", "item": item}
    if item.get("campaign_status") not in {"approved", "active"}:
        return {"allowed": False, "reason_code": "campaign_not_active", "item": item}
    if item.get("touch_status") not in {"approved", "scheduled", "queued"}:
        return {"allowed": False, "reason_code": "touch_not_sendable", "item": item}
    if not item.get("approved_at") or not item.get("approved_snapshot_hash"):
        return {"allowed": False, "reason_code": "approval_snapshot_missing", "item": item}
    cursor.execute(
        "SELECT * FROM outreach_campaign_touches WHERE campaign_id = %s ORDER BY sequence_index",
        (item.get("campaign_id"),),
    )
    current_touches = [_dict(row) for row in cursor.fetchall()]
    if not all(
        generation_contract_current(
            touch.get("message_brief_json"),
            touch.get("quality_gate_json"),
        )
        for touch in current_touches
    ):
        return {"allowed": False, "reason_code": "generation_contract_outdated", "item": item}
    current_snapshot = approval_snapshot_hash(
        {
            "id": item.get("campaign_id"),
            "version": item.get("version"),
            "workstream_id": item.get("campaign_workstream_id"),
            "lead_id": item.get("lead_id"),
            "scope_type": item.get("scope_type"),
            "business_id": item.get("business_id"),
            "sender_profile_id": item.get("sender_profile_id"),
            "policy_json": item.get("policy_json") or {},
        },
        current_touches,
    )
    if current_snapshot != item.get("approved_snapshot_hash"):
        return {"allowed": False, "reason_code": "approval_version_changed", "item": item}
    cursor.execute(
        """
        SELECT id, status, channel, sequence_index
        FROM outreach_campaign_touches
        WHERE campaign_id = %s
          AND sequence_index < %s
          AND channel IN ('max', 'whatsapp', 'sms', 'manual')
          AND status NOT IN ('manual_sent', 'manual_skipped')
        ORDER BY sequence_index DESC
        LIMIT 1
        """,
        (item.get("campaign_id"), int(item.get("sequence_index") or 0)),
    )
    pending_manual = _dict(cursor.fetchone())
    if pending_manual:
        return {
            "allowed": False,
            "reason_code": "prior_manual_touch_pending",
            "pending_manual_touch_id": str(pending_manual.get("id") or ""),
            "pending_manual_status": pending_manual.get("status"),
            "item": item,
        }
    if not item.get("sender_account_id"):
        return {"allowed": False, "reason_code": "sender_account_missing", "item": item}
    if item.get("sender_status") != "connected":
        return {"allowed": False, "reason_code": "sender_not_connected", "item": item}
    if item.get("health_status") in SENDER_BLOCKING_HEALTH:
        return {"allowed": False, "reason_code": f"sender_{item.get('health_status')}", "item": item}
    sender_scope_reason = sender_scope_preflight_reason(item)
    if sender_scope_reason:
        return {"allowed": False, "reason_code": sender_scope_reason, "item": item}
    if item.get("channel") == "telegram" and not bool(item.get("telegram_outreach_enabled")):
        return {"allowed": False, "reason_code": "sender_permission_revoked", "item": item}
    if item.get("channel") in {"email", "vk"} and not bool(item.get("sender_outreach_enabled")):
        return {"allowed": False, "reason_code": "sender_permission_revoked", "item": item}
    capabilities = item.get("sender_capabilities_json") or {}
    if item.get("channel") in {"telegram", "email", "vk"} and (
        not isinstance(capabilities, dict)
        or not capabilities.get("direct_send")
        or not capabilities.get("reply_sync")
    ):
        return {"allowed": False, "reason_code": "sender_adapter_incomplete", "item": item}
    if item.get("contact_verification_status") in {"invalid", "stale"}:
        return {"allowed": False, "reason_code": "recipient_contact_invalid", "item": item}
    if item.get("last_reply_at"):
        return {"allowed": False, "reason_code": "recipient_replied", "item": item}

    current_recipient_key = str(
        item.get("queue_recipient_key")
        or item.get("campaign_recipient_key")
        or recipient_key(str(item.get("lead_id") or ""))
    )
    contact_hash = ""
    if item.get("contact_type") and item.get("normalized_value"):
        contact_hash = normalized_contact_hash(
            str(item.get("contact_type")), str(item.get("normalized_value"))
        )
    cursor.execute(
        """
        SELECT reason_code
        FROM outreach_suppressions suppression
        WHERE (suppression.expires_at IS NULL OR suppression.expires_at > NOW())
          AND (
              suppression.scope_type = 'platform_safety'
              OR (
                  suppression.scope_type = %s
                  AND COALESCE(suppression.business_id, '') = COALESCE(%s, '')
              )
          )
          AND (
              suppression.lead_id = %s
              OR NULLIF(suppression.recipient_key, '') = %s
              OR (%s <> '' AND NULLIF(suppression.normalized_contact_hash, '') = %s)
          )
        ORDER BY suppression.created_at DESC
        LIMIT 1
        """,
        (
            item.get("scope_type"), item.get("business_id"), item.get("lead_id"),
            current_recipient_key, contact_hash, contact_hash,
        ),
    )
    suppression = _dict(cursor.fetchone())
    if suppression:
        return {
            "allowed": False,
            "reason_code": "suppressed_contact",
            "suppression_reason": suppression.get("reason_code"),
            "item": item,
        }

    cursor.execute(
        """
        SELECT classification
        FROM outreach_inbound_events
        WHERE lead_id = %s AND stops_campaign = TRUE
        ORDER BY occurred_at DESC
        LIMIT 1
        """,
        (item.get("lead_id"),),
    )
    inbound = _dict(cursor.fetchone())
    if inbound:
        return {
            "allowed": False,
            "reason_code": "recipient_replied",
            "reply_classification": inbound.get("classification"),
            "item": item,
        }

    cursor.execute(
        """
        SELECT classification
        FROM outreach_inbound_events
        WHERE lead_id = %s
          AND channel = %s
          AND classification IN ('permanent_delivery_failure', 'bounce')
        ORDER BY occurred_at DESC
        LIMIT 1
        """,
        (item.get("lead_id"), item.get("channel")),
    )
    permanent_failure = _dict(cursor.fetchone())
    if permanent_failure:
        return {
            "allowed": False,
            "reason_code": "channel_permanently_unavailable",
            "failure_classification": permanent_failure.get("classification"),
            "item": item,
        }

    cursor.execute(
        """
        SELECT conflicting.id
        FROM outreach_campaigns conflicting
        WHERE conflicting.id <> %s
          AND conflicting.status IN ('approved', 'active')
          AND conflicting.scope_type = %s
          AND COALESCE(conflicting.business_id, '') = COALESCE(%s, '')
          AND (
              conflicting.lead_id = %s
              OR NULLIF(conflicting.recipient_key, '') = %s
              OR (
                  %s <> '' AND %s <> '' AND EXISTS (
                      SELECT 1
                      FROM outreach_campaign_touches conflicting_touch
                      JOIN lead_contact_points conflicting_contact
                        ON conflicting_contact.id = conflicting_touch.contact_point_id
                      WHERE conflicting_touch.campaign_id = conflicting.id
                        AND lower(conflicting_contact.contact_type) = lower(%s)
                        AND lower(regexp_replace(conflicting_contact.normalized_value, '\\s+', '', 'g'))
                            = lower(regexp_replace(%s, '\\s+', '', 'g'))
                  )
              )
          )
        LIMIT 1
        """,
        (
            item.get("campaign_id"), item.get("scope_type"), item.get("business_id"),
            item.get("lead_id"), current_recipient_key,
            item.get("contact_type") or "", item.get("normalized_value") or "",
            item.get("contact_type") or "", item.get("normalized_value") or "",
        ),
    )
    if cursor.fetchone():
        return {"allowed": False, "reason_code": "conflicting_active_campaign", "item": item}

    policy = item.get("policy_json") if isinstance(item.get("policy_json"), dict) else {}
    daily_limit = max(1, int(policy.get("daily_limit") or 10))
    cursor.execute(
        """
        SELECT COUNT(*) AS sent_count
        FROM outreachsendqueue
        WHERE sender_account_id = %s
          AND sent_at >= CURRENT_DATE
          AND delivery_status IN ('sent', 'delivered')
        """,
        (item.get("sender_account_id"),),
    )
    sent_today_row = _dict(cursor.fetchone())
    if int(sent_today_row.get("sent_count") or 0) >= daily_limit:
        return {"allowed": False, "reason_code": "sender_daily_limit_reached", "item": item}
    cadence_hours = max(1, int(policy.get("minimum_cadence_hours") or 24))
    cursor.execute(
        """
        SELECT previous.id
        FROM outreachsendqueue previous
        LEFT JOIN outreach_campaign_touches previous_touch ON previous_touch.id = previous.campaign_touch_id
        LEFT JOIN outreach_campaigns previous_campaign ON previous_campaign.id = previous_touch.campaign_id
        WHERE previous.id <> %s
          AND previous.sent_at > NOW() - (%s * INTERVAL '1 hour')
          AND previous.delivery_status IN ('sent', 'delivered')
          AND (
              previous.lead_id = %s
              OR NULLIF(previous.recipient_key, '') = %s
              OR NULLIF(previous_campaign.recipient_key, '') = %s
          )
          AND (
              previous_campaign.id IS NULL
              OR (
                  previous_campaign.scope_type = %s
                  AND COALESCE(previous_campaign.business_id, '') = COALESCE(%s, '')
              )
          )
        LIMIT 1
        """,
        (
            queue_id, cadence_hours, item.get("lead_id"), current_recipient_key,
            current_recipient_key, item.get("scope_type"), item.get("business_id"),
        ),
    )
    if cursor.fetchone():
        return {
            "allowed": False,
            "reason_code": "cross_channel_cooldown",
            "retry_after_hours": cadence_hours,
            "item": item,
        }
    return {
        "allowed": True,
        "reason_code": "preflight_passed",
        "recipient_key": current_recipient_key,
        "item": item,
    }


def persist_preflight_result(cursor: Any, queue_id: str, result: dict[str, Any]) -> None:
    reason_code = str(result.get("reason_code") or "preflight_failed")
    cursor.execute(
        """
        UPDATE outreachsendqueue
        SET preflight_at = NOW(), preflight_reason = %s,
            recipient_key = COALESCE(NULLIF(recipient_key, ''), NULLIF(%s, '')),
            updated_at = NOW()
        WHERE id = %s
        """,
        (reason_code, result.get("recipient_key") or "", queue_id),
    )
    item = result.get("item") if isinstance(result.get("item"), dict) else {}
    touch_id = item.get("touch_id")
    if touch_id:
        cursor.execute(
            """
            UPDATE outreach_campaign_touches
            SET preflight_at = NOW(), preflight_reason = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (reason_code, touch_id),
        )


def block_queue_item_after_preflight(cursor: Any, queue_id: str, result: dict[str, Any]) -> None:
    reason_code = str(result.get("reason_code") or "preflight_failed")
    terminal = reason_code in {
        "recipient_replied",
        "suppressed_contact",
        "sender_permission_revoked",
        "recipient_contact_invalid",
        "sender_scope_mismatch",
        "sender_business_mismatch",
        "approval_snapshot_missing",
        "approval_version_changed",
        "campaign_approval_required",
        "channel_permanently_unavailable",
        "conflicting_active_campaign",
    }
    queue_status = "failed" if terminal else "paused"
    touch_status = "reply_cancelled" if reason_code == "recipient_replied" else "paused"
    cursor.execute(
        """
        UPDATE outreachsendqueue
        SET delivery_status = %s, error_text = %s, preflight_at = NOW(),
            preflight_reason = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (queue_status, reason_code, reason_code, queue_id),
    )
    item = result.get("item") if isinstance(result.get("item"), dict) else {}
    if item.get("touch_id"):
        cursor.execute(
            """
            UPDATE outreach_campaign_touches
            SET status = %s, preflight_at = NOW(), preflight_reason = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (touch_status, reason_code, item.get("touch_id")),
        )
    if item.get("campaign_id"):
        cursor.execute(
            """
            UPDATE outreach_campaigns
            SET status = CASE WHEN %s = 'recipient_replied' THEN 'stopped' ELSE 'paused' END,
                stop_reason = %s,
                needs_attention_reason = CASE WHEN %s = 'recipient_replied' THEN NULL ELSE %s END,
                updated_at = NOW()
            WHERE id = %s AND status IN ('approved', 'active')
            """,
            (reason_code, reason_code, reason_code, reason_code, item.get("campaign_id")),
        )
        cursor.execute(
            """
            INSERT INTO outreach_campaign_events (
                id, campaign_id, touch_id, event_type, reason_code,
                payload_json, created_at
            ) VALUES (%s, %s, %s, 'touch_preflight_blocked', %s, %s, NOW())
            """,
            (
                str(uuid.uuid4()), item.get("campaign_id"), item.get("touch_id"),
                reason_code, Json({key: value for key, value in result.items() if key != "item"}),
            ),
        )


def record_learning_event(
    cursor: Any,
    *,
    campaign: dict[str, Any],
    touch: dict[str, Any],
    outcome_type: str,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> str:
    fingerprint = str(touch.get("strategy_fingerprint") or "").strip()
    if not fingerprint:
        fingerprint = strategy_fingerprint(touch.get("strategy_json") or {})
    event_id = str(uuid.uuid4())
    dimensions = touch.get("strategy_json") if isinstance(touch.get("strategy_json"), dict) else {}
    cursor.execute(
        """
        INSERT INTO outreach_learning_events (
            id, scope_type, business_id, workstream_type, campaign_id, touch_id,
            strategy_fingerprint, outcome_type, dimensions_json, payload_json,
            occurred_at, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            event_id, campaign.get("scope_type"), campaign.get("business_id"),
            campaign.get("workstream_type"), campaign.get("id"), touch.get("id"),
            fingerprint, outcome_type, Json(dimensions), Json(payload or {}),
            occurred_at or datetime.now(timezone.utc),
        ),
    )
    refresh_strategy_stats(
        cursor,
        scope_type=str(campaign.get("scope_type") or ""),
        business_id=campaign.get("business_id"),
        workstream_type=str(campaign.get("workstream_type") or ""),
        fingerprint=fingerprint,
    )
    return event_id


def confirmed_reply_learning_outcome(outcome: str | None) -> str | None:
    """Translate a human-confirmed legacy reaction into the learning contract."""
    return {
        "positive": "positive_reply",
        "question": "question",
        "hard_no": "hard_no",
    }.get(str(outcome or "").strip().lower())


def reconcile_reaction_learning_event(
    cursor: Any,
    *,
    reaction_id: str,
    confirmed_outcome: str,
    user_id: str | None,
) -> dict[str, Any]:
    """Keep a corrected reply, lead lifecycle and strategy statistics consistent.

    A reaction can exist outside the versioned campaign flow. In that case the
    legacy CRM result remains valid, but there is no strategy touch to learn from.
    Safety outcomes are deliberately never downgraded here: removing an
    unsubscribe/complaint suppression requires a separate explicit safety action.
    """
    desired_outcome = confirmed_reply_learning_outcome(confirmed_outcome)
    if not desired_outcome:
        return {
            "updated": False,
            "reason_code": "outcome_not_attributable",
        }

    cursor.execute(
        """
        SELECT reaction.id AS reaction_id, reaction.lead_id,
               queue.workstream_id, queue.campaign_touch_id,
               touch.*, campaign.scope_type, campaign.business_id,
               campaign.workstream_id AS campaign_workstream_id,
               workstream.workstream_type
        FROM outreachreactions reaction
        JOIN outreachsendqueue queue ON queue.id = reaction.queue_id
        LEFT JOIN outreach_campaign_touches touch ON touch.id = queue.campaign_touch_id
        LEFT JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
        LEFT JOIN lead_workstreams workstream ON workstream.id = campaign.workstream_id
        WHERE reaction.id = %s
        FOR UPDATE OF reaction
        """,
        (reaction_id,),
    )
    context = _dict(cursor.fetchone())
    if not context or not context.get("campaign_touch_id") or not context.get("strategy_fingerprint"):
        return {
            "updated": False,
            "reason_code": "campaign_touch_missing",
        }

    cursor.execute(
        """
        SELECT id, outcome_type
        FROM outreach_learning_events
        WHERE campaign_id = %s
          AND touch_id = %s
          AND payload_json->>'reaction_id' = %s
        ORDER BY occurred_at DESC, created_at DESC
        LIMIT 1
        FOR UPDATE
        """,
        (context.get("campaign_id"), context.get("campaign_touch_id"), reaction_id),
    )
    existing = _dict(cursor.fetchone())
    previous_outcome = str(existing.get("outcome_type") or "").strip()
    safety_outcome_retained = previous_outcome in {"unsubscribe", "complaint"}
    effective_outcome = previous_outcome if safety_outcome_retained else desired_outcome

    if existing and not safety_outcome_retained:
        cursor.execute(
            """
            UPDATE outreach_learning_events
            SET outcome_type = %s,
                payload_json = payload_json || %s,
                occurred_at = NOW()
            WHERE id = %s
            """,
            (
                desired_outcome,
                Json({
                    "human_confirmed_outcome": confirmed_outcome,
                    "human_confirmed_by": user_id,
                    "previous_learning_outcome": previous_outcome,
                }),
                existing.get("id"),
            ),
        )
        refresh_strategy_stats(
            cursor,
            scope_type=str(context.get("scope_type") or ""),
            business_id=context.get("business_id"),
            workstream_type=str(context.get("workstream_type") or ""),
            fingerprint=str(context.get("strategy_fingerprint") or ""),
        )
        learning_event_id = str(existing.get("id") or "")
    elif existing:
        learning_event_id = str(existing.get("id") or "")
    else:
        learning_event_id = record_learning_event(
            cursor,
            campaign={
                "id": context.get("campaign_id"),
                "scope_type": context.get("scope_type"),
                "business_id": context.get("business_id"),
                "workstream_type": context.get("workstream_type"),
            },
            touch=context,
            outcome_type=desired_outcome,
            payload={
                "reaction_id": reaction_id,
                "source": "human_confirmation",
                "human_confirmed_outcome": confirmed_outcome,
                "human_confirmed_by": user_id,
            },
        )

    classification = {
        "positive_reply": "interested",
        "question": "question",
        "hard_no": "not_interested",
        "unsubscribe": "unsubscribe",
        "complaint": "complaint",
    }.get(effective_outcome, "human_unknown")
    next_step = {
        "interested": "Ответить получателю и согласовать следующий шаг",
        "question": "Ответить на вопрос получателя",
        "not_interested": "Контакт отказался — больше не писать",
        "unsubscribe": "Контакт отписался — больше не писать",
        "complaint": "Проверить жалобу и остановить отправки",
    }.get(classification, "Ответить получателю вручную")
    workstream_id = context.get("campaign_workstream_id") or context.get("workstream_id")
    cursor.execute(
        """
        UPDATE lead_workstreams
        SET lifecycle_status = 'replied', status_reason = %s,
            next_step = %s, state_changed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (classification, next_step, workstream_id),
    )

    if effective_outcome == "hard_no":
        cursor.execute(
            """
            INSERT INTO outreach_suppressions (
                id, lead_id, workstream_id, scope_type, business_id,
                recipient_key, channel, reason_code, source, created_by,
                created_at, updated_at
            )
            SELECT %s, %s, %s, %s, %s, %s, %s,
                   'not_interested', 'human_confirmation', %s, NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1
                FROM outreach_suppressions suppression
                WHERE suppression.lead_id = %s
                  AND suppression.workstream_id = %s
                  AND suppression.reason_code IN ('not_interested', 'unsubscribe', 'complaint')
                  AND (suppression.expires_at IS NULL OR suppression.expires_at > NOW())
            )
            """,
            (
                str(uuid.uuid4()), context.get("lead_id"), workstream_id,
                context.get("scope_type"), context.get("business_id"),
                recipient_key(str(context.get("lead_id") or "")), context.get("channel"),
                user_id, context.get("lead_id"), workstream_id,
            ),
        )

    cursor.execute(
        """
        INSERT INTO outreach_campaign_events (
            id, campaign_id, touch_id, event_type, reason_code,
            payload_json, actor_id, created_at
        ) VALUES (%s, %s, %s, 'reply_outcome_confirmed', %s, %s, %s, NOW())
        """,
        (
            str(uuid.uuid4()), context.get("campaign_id"), context.get("campaign_touch_id"),
            effective_outcome,
            Json({
                "reaction_id": reaction_id,
                "confirmed_outcome": confirmed_outcome,
                "previous_learning_outcome": previous_outcome or None,
                "safety_outcome_retained": safety_outcome_retained,
                "learning_event_id": learning_event_id,
            }),
            user_id,
        ),
    )
    return {
        "updated": True,
        "learning_event_id": learning_event_id,
        "outcome_type": effective_outcome,
        "safety_outcome_retained": safety_outcome_retained,
    }


def refresh_strategy_stats(
    cursor: Any,
    *,
    scope_type: str,
    business_id: str | None,
    workstream_type: str,
    fingerprint: str,
) -> dict[str, Any]:
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
        (
            f"{scope_type}:{business_id or ''}",
            f"{workstream_type}:{fingerprint}",
        ),
    )
    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE outcome_type = 'sent') AS sent_count,
            COUNT(*) FILTER (WHERE outcome_type = 'delivered') AS delivered_count,
            COUNT(*) FILTER (WHERE outcome_type IN (
                'replied', 'positive_reply', 'question', 'hard_no', 'unsubscribe',
                'complaint', 'interested', 'call_planned', 'contacts_exchanged',
                'pilot_agreed', 'campaign_launched', 'joint_project',
                'recurring_partnership', 'not_relevant', 'lost'
            )) AS reply_count,
            COUNT(*) FILTER (WHERE outcome_type IN (
                'positive_reply', 'interested', 'call_planned', 'contacts_exchanged',
                'pilot_agreed', 'campaign_launched', 'joint_project', 'recurring_partnership'
            )) AS positive_reply_count,
            COUNT(*) FILTER (WHERE outcome_type = 'question') AS question_count,
            COUNT(*) FILTER (WHERE outcome_type = 'hard_no') AS hard_no_count,
            COUNT(*) FILTER (WHERE outcome_type = 'unsubscribe') AS unsubscribe_count,
            COUNT(*) FILTER (WHERE outcome_type = 'complaint') AS complaint_count,
            COUNT(*) FILTER (WHERE outcome_type IN ('meeting_booked', 'call_planned')) AS meeting_count,
            COUNT(*) FILTER (WHERE outcome_type IN (
                'converted', 'campaign_launched', 'joint_project', 'recurring_partnership'
            )) AS converted_count,
            MIN(occurred_at) AS first_event_at,
            MAX(occurred_at) AS last_event_at,
            COALESCE((ARRAY_AGG(dimensions_json ORDER BY occurred_at DESC))[1], '{}'::jsonb) AS dimensions_json
        FROM outreach_learning_events
        WHERE scope_type = %s
          AND COALESCE(business_id, '') = COALESCE(%s, '')
          AND workstream_type = %s
          AND strategy_fingerprint = %s
        """,
        (scope_type, business_id, workstream_type, fingerprint),
    )
    aggregate = _dict(cursor.fetchone())
    delivered_count = int(aggregate.get("delivered_count") or 0)
    sent_count = int(aggregate.get("sent_count") or 0)
    sample_count = max(delivered_count, sent_count)
    positive_count = int(aggregate.get("positive_reply_count") or 0)
    confidence = wilson_lower_bound(positive_count, sample_count)
    values = (
        aggregate.get("dimensions_json") or {},
        sent_count,
        delivered_count,
        int(aggregate.get("reply_count") or 0),
        positive_count,
        int(aggregate.get("question_count") or 0),
        int(aggregate.get("hard_no_count") or 0),
        int(aggregate.get("unsubscribe_count") or 0),
        int(aggregate.get("complaint_count") or 0),
        int(aggregate.get("meeting_count") or 0),
        int(aggregate.get("converted_count") or 0),
        learning_sample_status(sample_count),
        confidence,
        aggregate.get("first_event_at"),
        aggregate.get("last_event_at"),
    )
    cursor.execute(
        """
        SELECT id FROM outreach_strategy_stats
        WHERE scope_type = %s
          AND COALESCE(business_id, '') = COALESCE(%s, '')
          AND workstream_type = %s
          AND strategy_fingerprint = %s
        FOR UPDATE
        """,
        (scope_type, business_id, workstream_type, fingerprint),
    )
    existing = _dict(cursor.fetchone())
    if existing:
        cursor.execute(
            """
            UPDATE outreach_strategy_stats
            SET dimensions_json = %s, sent_count = %s, delivered_count = %s,
                reply_count = %s, positive_reply_count = %s, question_count = %s,
                hard_no_count = %s, unsubscribe_count = %s, complaint_count = %s,
                meeting_count = %s, converted_count = %s, sample_status = %s,
                confidence = %s, first_event_at = %s, last_event_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (Json(values[0]), *values[1:], existing.get("id")),
        )
        stats_id = str(existing.get("id"))
    else:
        stats_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO outreach_strategy_stats (
                id, scope_type, business_id, workstream_type, strategy_fingerprint,
                dimensions_json, sent_count, delivered_count, reply_count,
                positive_reply_count, question_count, hard_no_count, unsubscribe_count,
                complaint_count, meeting_count, converted_count, sample_status,
                confidence, first_event_at, last_event_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            """,
            (stats_id, scope_type, business_id, workstream_type, fingerprint, Json(values[0]), *values[1:]),
        )
    return {
        "id": stats_id,
        "sample_status": learning_sample_status(sample_count),
        "confidence": confidence,
        "sent_count": sent_count,
        "delivered_count": delivered_count,
        "positive_reply_count": positive_count,
    }


def record_sender_health_event(
    cursor: Any,
    *,
    sender_account_id: str,
    event_type: str,
    provider_code: str | None = None,
    campaign_id: str | None = None,
    touch_id: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_event = str(event_type or "provider_warning").strip().lower()
    severity = "critical" if normalized_event in {"blocked", "auth_invalid", "complaint"} else (
        "degraded" if normalized_event in {"bounce", "flood_wait"} else (
            "warning" if normalized_event in {"rate_limit", "delivery_failed", "provider_warning"} else "info"
        )
    )
    cursor.execute(
        """
        INSERT INTO outreach_sender_health_events (
            id, sender_account_id, event_type, severity, provider_code,
            campaign_id, touch_id, metrics_json, occurred_at, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            str(uuid.uuid4()), sender_account_id, normalized_event, severity,
            provider_code, campaign_id, touch_id, Json(metrics or {}),
        ),
    )
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM outreachsendqueue
             WHERE sender_account_id = %s AND sent_at > NOW() - INTERVAL '30 days'
               AND delivery_status IN ('sent', 'delivered')) AS sent_count,
            COUNT(*) FILTER (WHERE event_type = 'bounce') AS bounce_count,
            COUNT(*) FILTER (WHERE event_type = 'complaint') AS complaint_count,
            COUNT(*) FILTER (WHERE event_type = 'rate_limit') AS rate_limit_count,
            COALESCE(SUM((metrics_json->>'flood_wait_seconds')::integer)
                FILTER (WHERE event_type = 'flood_wait'), 0) AS flood_wait_seconds,
            BOOL_OR(event_type = 'blocked') AS blocked,
            BOOL_OR(event_type = 'auth_invalid') AS auth_invalid
        FROM outreach_sender_health_events health_event
        WHERE sender_account_id = %s
          AND occurred_at > GREATEST(
              NOW() - INTERVAL '30 days',
              COALESCE((
                  SELECT MAX(recovered.occurred_at)
                  FROM outreach_sender_health_events recovered
                  WHERE recovered.sender_account_id = %s
                    AND recovered.event_type = 'recovered'
              ), '-infinity'::timestamptz)
          )
        """,
        (sender_account_id, sender_account_id, sender_account_id),
    )
    health = sender_health(_dict(cursor.fetchone()))
    cursor.execute(
        """
        UPDATE outreach_sender_accounts
        SET health_status = %s, health_score = %s, health_reason = %s,
            health_metrics_json = %s,
            health_changed_at = CASE WHEN health_status <> %s THEN NOW() ELSE health_changed_at END,
            last_health_event_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (
            health["status"], health["score"], ",".join(health["reasons"]) or None,
            Json(health["metrics"]), health["status"], sender_account_id,
        ),
    )
    return health


def record_touch_learning_event(
    cursor: Any,
    *,
    touch_id: str,
    outcome_type: str,
    payload: dict[str, Any] | None = None,
) -> str | None:
    cursor.execute(
        """
        SELECT t.*, c.scope_type, c.business_id, ws.workstream_type
        FROM outreach_campaign_touches t
        JOIN outreach_campaigns c ON c.id = t.campaign_id
        JOIN lead_workstreams ws ON ws.id = c.workstream_id
        WHERE t.id = %s
        """,
        (touch_id,),
    )
    touch = _dict(cursor.fetchone())
    if not touch:
        return None
    return record_learning_event(
        cursor,
        campaign={
            "id": touch.get("campaign_id"),
            "scope_type": touch.get("scope_type"),
            "business_id": touch.get("business_id"),
            "workstream_type": touch.get("workstream_type"),
        },
        touch=touch,
        outcome_type=outcome_type,
        payload=payload,
    )
