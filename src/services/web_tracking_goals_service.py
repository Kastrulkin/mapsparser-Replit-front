"""Configuration and outcome analytics layered over privacy-first website events."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import secrets
import unicodedata
import uuid


PAGE_GROUP_TYPES = {"service", "pricing", "contact", "success", "custom"}
PAGE_MATCH_TYPES = {"exact", "prefix", "contains", "list"}
GOAL_TYPES = {
    "page_view", "section_view", "cta_click", "form_submit", "booking_click",
    "lead_created", "message_started", "message_lead", "call_connected",
    "call_answered", "call_qualified", "booking_created", "booking_confirmed",
    "booking_cancelled", "visit_completed", "payment_completed",
}
CONFIRMED_TYPES = {
    "lead_created", "message_started", "message_lead", "call_connected",
    "call_answered", "call_qualified", "booking_created", "booking_confirmed",
    "booking_cancelled", "visit_completed", "payment_completed",
}
CHANGE_TYPES = {
    "page", "price", "headline", "cta", "form", "campaign", "promotion",
    "incident", "tracker", "other",
}
FORM_EVENT_TYPES = {
    "form_start", "form_validation_error", "form_submit_attempt",
    "form_submit_success", "form_submit_error", "form_submit",
}


class WebTrackingConfigurationError(ValueError):
    """Raised when an owner-provided analytics configuration is invalid."""


class WebConversionAuthenticationError(ValueError):
    """Raised when a conversion source key cannot be resolved."""


def _text(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFC", value)
    clean = "".join(
        character for character in normalized
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs", "Co"}
    )
    return clean.strip()[:limit]


def _text_list(value, *, limit: int = 30, item_limit: int = 500) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise WebTrackingConfigurationError("invalid_pattern_list")
    result = []
    for item in value:
        clean = _text(item, item_limit)
        if not clean:
            continue
        if not clean.startswith("/"):
            clean = f"/{clean}"
        clean = clean.split("?", 1)[0].split("#", 1)[0]
        if clean not in result:
            result.append(clean)
    return result


def _json_object(value) -> dict:
    return value if isinstance(value, dict) else {}


def page_matches(path: str, match_type: str, includes: list[str], excludes: list[str]) -> bool:
    candidate = (_text(path, 1000) or "/").split("?", 1)[0].split("#", 1)[0]
    if any(excluded in candidate for excluded in excludes):
        return False
    if not includes:
        return False
    if match_type in {"exact", "list"}:
        return candidate in includes
    if match_type == "prefix":
        return any(candidate.startswith(pattern) for pattern in includes)
    if match_type == "contains":
        return any(pattern in candidate for pattern in includes)
    return False


def validate_page_group_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise WebTrackingConfigurationError("invalid_page_group")
    name = _text(payload.get("name"), 120)
    group_type = _text(payload.get("group_type"), 30) or "custom"
    match_type = _text(payload.get("match_type"), 30) or "prefix"
    if not name:
        raise WebTrackingConfigurationError("page_group_name_required")
    if group_type not in PAGE_GROUP_TYPES:
        raise WebTrackingConfigurationError("invalid_page_group_type")
    if match_type not in PAGE_MATCH_TYPES:
        raise WebTrackingConfigurationError("invalid_page_match_type")
    includes = _text_list(payload.get("include_patterns", []))
    excludes = _text_list(payload.get("exclude_patterns", []))
    is_draft = payload.get("is_draft") is True
    if not includes and not is_draft:
        raise WebTrackingConfigurationError("page_group_patterns_required")
    enabled = payload.get("enabled") is not False
    return {
        "name": name,
        "group_type": group_type,
        "match_type": match_type,
        "include_patterns": includes,
        "exclude_patterns": excludes,
        "is_draft": is_draft,
        "enabled": enabled,
    }


def _recent_page_rows(cursor, business_id: str, period_days: int = 90) -> list[dict]:
    cursor.execute(
        """SELECT e.page_path AS path,
                  MAX(NULLIF(e.metadata_json->>'title', '')) AS title,
                  COUNT(*) AS views,
                  COUNT(DISTINCT e.session_id) AS sessions
           FROM web_events e
           WHERE e.business_id = %s AND e.event_type = 'page_view'
             AND e.occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY e.page_path ORDER BY views DESC, e.page_path LIMIT 1000""",
        (business_id, period_days),
    )
    return [dict(row) for row in cursor.fetchall()]


def preview_page_group(cursor, business_id: str, payload: object) -> dict:
    group = validate_page_group_payload(payload)
    rows = _recent_page_rows(cursor, business_id)
    matches = [
        row for row in rows
        if page_matches(
            row.get("path") or "/",
            group["match_type"],
            group["include_patterns"],
            group["exclude_patterns"],
        )
    ]
    return {
        "matched_paths": len(matches),
        "matched_sessions": sum(int(row.get("sessions") or 0) for row in matches),
        "sample": matches[:20],
        "available_paths": len(rows),
    }


def list_page_groups(cursor, business_id: str) -> list[dict]:
    cursor.execute(
        """SELECT id, name, group_type, match_type, include_patterns, exclude_patterns,
                  is_draft, enabled, created_at, updated_at
           FROM web_page_groups WHERE business_id = %s
           ORDER BY enabled DESC, updated_at DESC, name""",
        (business_id,),
    )
    groups = [dict(row) for row in cursor.fetchall()]
    recent_rows = _recent_page_rows(cursor, business_id, 30)
    for group in groups:
        matches = [
            row for row in recent_rows
            if page_matches(
                row.get("path") or "/",
                group.get("match_type") or "prefix",
                group.get("include_patterns") or [],
                group.get("exclude_patterns") or [],
            )
        ]
        matched_sessions = sum(int(row.get("sessions") or 0) for row in matches)
        if not group.get("enabled"):
            status = "disabled"
        elif group.get("is_draft"):
            status = "draft"
        elif matched_sessions:
            status = "receiving"
        elif recent_rows:
            status = "no_data"
        else:
            status = "configured"
        group["status"] = status
        group["matched_paths"] = len(matches)
        group["matched_sessions"] = matched_sessions
    return groups


def save_page_group(cursor, business_id: str, user_id: str, payload: object, group_id: str = "") -> dict:
    group = validate_page_group_payload(payload)
    resolved_id = group_id or str(uuid.uuid4())
    if group_id:
        cursor.execute(
            """UPDATE web_page_groups
               SET name = %s, group_type = %s, match_type = %s,
                   include_patterns = %s::jsonb, exclude_patterns = %s::jsonb,
                   is_draft = %s, enabled = %s, updated_at = NOW()
               WHERE id = %s AND business_id = %s RETURNING id""",
            (
                group["name"], group["group_type"], group["match_type"],
                json.dumps(group["include_patterns"], ensure_ascii=False),
                json.dumps(group["exclude_patterns"], ensure_ascii=False),
                group["is_draft"], group["enabled"], group_id, business_id,
            ),
        )
        if not cursor.fetchone():
            raise WebTrackingConfigurationError("page_group_not_found")
    else:
        cursor.execute(
            """INSERT INTO web_page_groups (
                   id, business_id, name, group_type, match_type, include_patterns,
                   exclude_patterns, is_draft, enabled, created_by
               ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)""",
            (
                resolved_id, business_id, group["name"], group["group_type"], group["match_type"],
                json.dumps(group["include_patterns"], ensure_ascii=False),
                json.dumps(group["exclude_patterns"], ensure_ascii=False),
                group["is_draft"], group["enabled"], user_id or None,
            ),
        )
    return {"id": resolved_id, **group}


def delete_page_group(cursor, business_id: str, group_id: str) -> bool:
    cursor.execute(
        "DELETE FROM web_page_groups WHERE id = %s AND business_id = %s RETURNING id",
        (group_id, business_id),
    )
    return cursor.fetchone() is not None


def validate_goal_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise WebTrackingConfigurationError("invalid_goal")
    name = _text(payload.get("name"), 120)
    goal_type = _text(payload.get("goal_type"), 40)
    matcher = _json_object(payload.get("matcher"))
    if not name:
        raise WebTrackingConfigurationError("goal_name_required")
    if goal_type not in GOAL_TYPES:
        raise WebTrackingConfigurationError("invalid_goal_type")
    clean_matcher = {
        "page_group_id": _text(matcher.get("page_group_id"), 80),
        "section_key": _text(matcher.get("section_key"), 100),
        "cta_id": _text(matcher.get("cta_id"), 120),
        "form_id": _text(matcher.get("form_id"), 120),
    }
    is_draft = payload.get("is_draft") is True
    if goal_type == "page_view" and not clean_matcher["page_group_id"] and not is_draft:
        raise WebTrackingConfigurationError("goal_page_group_required")
    if goal_type == "section_view" and not clean_matcher["section_key"] and not is_draft:
        raise WebTrackingConfigurationError("goal_section_required")
    if goal_type == "cta_click" and not clean_matcher["cta_id"] and not is_draft:
        raise WebTrackingConfigurationError("goal_cta_required")
    if goal_type == "form_submit" and not clean_matcher["form_id"] and not is_draft:
        raise WebTrackingConfigurationError("goal_form_required")
    return {
        "name": name,
        "goal_type": goal_type,
        "matcher": clean_matcher,
        "is_draft": is_draft,
        "enabled": payload.get("enabled") is not False,
    }


def save_goal(cursor, business_id: str, user_id: str, payload: object, goal_id: str = "") -> dict:
    goal = validate_goal_payload(payload)
    resolved_id = goal_id or str(uuid.uuid4())
    matcher_json = json.dumps(goal["matcher"], ensure_ascii=False)
    if goal_id:
        cursor.execute(
            """UPDATE web_goals SET name = %s, goal_type = %s, matcher_json = %s::jsonb,
                   is_draft = %s, enabled = %s, updated_at = NOW()
               WHERE id = %s AND business_id = %s RETURNING id""",
            (
                goal["name"], goal["goal_type"], matcher_json, goal["is_draft"],
                goal["enabled"], goal_id, business_id,
            ),
        )
        if not cursor.fetchone():
            raise WebTrackingConfigurationError("goal_not_found")
    else:
        cursor.execute(
            """INSERT INTO web_goals (
                   id, business_id, name, goal_type, matcher_json, is_draft, enabled, created_by
               ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (
                resolved_id, business_id, goal["name"], goal["goal_type"], matcher_json,
                goal["is_draft"], goal["enabled"], user_id or None,
            ),
        )
    return {"id": resolved_id, **goal}


def delete_goal(cursor, business_id: str, goal_id: str) -> bool:
    cursor.execute(
        "DELETE FROM web_goals WHERE id = %s AND business_id = %s RETURNING id",
        (goal_id, business_id),
    )
    return cursor.fetchone() is not None


def _goal_count(cursor, business_id: str, goal: dict, period_days: int = 30) -> int:
    goal_type = goal.get("goal_type") or ""
    matcher = goal.get("matcher_json") or {}
    if goal_type in CONFIRMED_TYPES:
        cursor.execute(
            """SELECT COUNT(*) AS count FROM web_confirmed_conversions
               WHERE business_id = %s AND event_type = %s
                 AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')""",
            (business_id, goal_type, period_days),
        )
        return int(cursor.fetchone()["count"] or 0)
    event_type = {
        "page_view": "page_view",
        "section_view": "section_view",
        "cta_click": "cta_click",
        "form_submit": "form_submit_success",
        "booking_click": "outbound_click",
    }.get(goal_type)
    if not event_type:
        return 0
    clauses = ["e.business_id = %s", "e.event_type = %s", "e.occurred_at >= NOW() - (%s::int * INTERVAL '1 day')"]
    params = [business_id, event_type, period_days]
    if goal_type == "section_view" and matcher.get("section_key"):
        clauses.append("e.metadata_json->'section'->>'key' = %s")
        params.append(matcher["section_key"])
    if goal_type == "cta_click" and matcher.get("cta_id"):
        clauses.append("e.metadata_json->'cta'->>'id' = %s")
        params.append(matcher["cta_id"])
    if goal_type == "form_submit" and matcher.get("form_id"):
        clauses.append("e.metadata_json->'form'->>'id' = %s")
        params.append(matcher["form_id"])
    if goal_type == "booking_click":
        clauses.append("e.action_type = 'booking'")
    if goal_type == "page_view":
        group_id = matcher.get("page_group_id")
        cursor.execute(
            """SELECT match_type, include_patterns, exclude_patterns FROM web_page_groups
               WHERE id = %s AND business_id = %s""",
            (group_id, business_id),
        )
        group = cursor.fetchone()
        if not group:
            return 0
        cursor.execute(
            """SELECT e.page_path, COUNT(*) AS count FROM web_events e
               WHERE e.business_id = %s AND e.event_type = 'page_view'
                 AND e.occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
               GROUP BY e.page_path""",
            (business_id, period_days),
        )
        return sum(
            int(row["count"] or 0) for row in cursor.fetchall()
            if page_matches(
                row["page_path"], group["match_type"],
                group["include_patterns"] or [], group["exclude_patterns"] or [],
            )
        )
    cursor.execute(f"SELECT COUNT(*) AS count FROM web_events e WHERE {' AND '.join(clauses)}", tuple(params))
    return int(cursor.fetchone()["count"] or 0)


def list_goals(cursor, business_id: str, period_days: int = 30) -> list[dict]:
    cursor.execute(
        """SELECT id, name, goal_type, matcher_json, is_draft, enabled, created_at, updated_at
           FROM web_goals WHERE business_id = %s ORDER BY enabled DESC, updated_at DESC, name""",
        (business_id,),
    )
    goals = [dict(row) for row in cursor.fetchall()]
    for goal in goals:
        count = _goal_count(cursor, business_id, goal, period_days)
        if not goal.get("enabled"):
            status = "disabled"
        elif goal.get("is_draft"):
            status = "draft"
        elif count:
            status = "receiving"
        else:
            status = "no_data"
        goal["status"] = status
        goal["count"] = count
        goal["matcher"] = goal.pop("matcher_json", {})
    return goals


def rotate_conversion_key(cursor, business_id: str) -> dict:
    token = f"locconv_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cursor.execute(
        """UPDATE business_web_trackers
           SET conversion_key_hash = %s, conversion_key_created_at = NOW()
           WHERE business_id = %s
           RETURNING id, conversion_key_created_at""",
        (token_hash, business_id),
    )
    row = cursor.fetchone()
    if not row:
        raise WebTrackingConfigurationError("tracker_not_found")
    return {"key": token, "created_at": row["conversion_key_created_at"]}


def conversion_key_status(cursor, business_id: str) -> dict:
    cursor.execute(
        """SELECT conversion_key_hash IS NOT NULL AS configured, conversion_key_created_at
           FROM business_web_trackers WHERE business_id = %s ORDER BY created_at LIMIT 1""",
        (business_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {"configured": False, "created_at": None}
    return dict(row)


def resolve_conversion_tracker(cursor, token: str) -> dict:
    clean_token = _text(token, 200)
    if not clean_token.startswith("locconv_"):
        raise WebConversionAuthenticationError("invalid_conversion_key")
    token_hash = hashlib.sha256(clean_token.encode("utf-8")).hexdigest()
    cursor.execute(
        """SELECT id, business_id FROM business_web_trackers
           WHERE conversion_key_hash = %s AND enabled = TRUE LIMIT 1""",
        (token_hash,),
    )
    row = cursor.fetchone()
    if not row:
        raise WebConversionAuthenticationError("invalid_conversion_key")
    return dict(row)


def _decimal_amount(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise WebTrackingConfigurationError("invalid_conversion_amount")
    if amount < 0 or amount > Decimal("999999999999.99"):
        raise WebTrackingConfigurationError("invalid_conversion_amount")
    return amount.quantize(Decimal("0.01"))


def ingest_confirmed_conversion(cursor, tracker: dict, payload: object) -> dict:
    if not isinstance(payload, dict):
        raise WebTrackingConfigurationError("invalid_conversion")
    source = _text(payload.get("source"), 80)
    external_id = _text(payload.get("external_id"), 160)
    event_type = _text(payload.get("event_type"), 40)
    if not source or not external_id:
        raise WebTrackingConfigurationError("conversion_identity_required")
    if event_type not in CONFIRMED_TYPES:
        raise WebTrackingConfigurationError("invalid_conversion_type")
    raw_occurred_at = _text(payload.get("occurred_at"), 80)
    try:
        occurred_at = datetime.fromisoformat(raw_occurred_at.replace("Z", "+00:00")) if raw_occurred_at else datetime.now(timezone.utc)
    except ValueError:
        raise WebTrackingConfigurationError("invalid_conversion_time")
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    occurred_at = occurred_at.astimezone(timezone.utc)
    if occurred_at < datetime.now(timezone.utc) - timedelta(days=365) or occurred_at > datetime.now(timezone.utc) + timedelta(minutes=10):
        raise WebTrackingConfigurationError("invalid_conversion_time")
    session_key = _text(payload.get("attribution_session_id"), 80)
    if session_key and not session_key.startswith("s_"):
        raise WebTrackingConfigurationError("invalid_attribution_session")
    currency = _text(payload.get("currency"), 3).upper()
    amount = _decimal_amount(payload.get("amount"))
    if amount is not None and len(currency) != 3:
        raise WebTrackingConfigurationError("conversion_currency_required")
    cta_id = _text(payload.get("cta_id"), 120)
    raw_duration = payload.get("duration_seconds")
    duration_seconds = raw_duration if type(raw_duration) is int and 0 <= raw_duration <= 86400 else None
    safe_metadata = {
        "status": _text(payload.get("status"), 80),
        "provider": _text(payload.get("provider"), 80),
        "duration_seconds": duration_seconds,
    }
    conversion_id = str(uuid.uuid4())
    cursor.execute(
        """INSERT INTO web_confirmed_conversions (
               id, business_id, tracker_id, source, external_id, event_type, occurred_at,
               attribution_session_key, cta_id, amount, currency, metadata_json
           ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
           ON CONFLICT (business_id, source, external_id, event_type) DO NOTHING
           RETURNING id""",
        (
            conversion_id, tracker["business_id"], tracker["id"], source, external_id,
            event_type, occurred_at, session_key or None, cta_id or None, amount,
            currency or None, json.dumps(safe_metadata, ensure_ascii=False),
        ),
    )
    inserted = cursor.fetchone()
    return {"id": inserted["id"] if inserted else None, "accepted": bool(inserted), "duplicate": not bool(inserted)}


def list_annotations(cursor, business_id: str, period_days: int = 90) -> list[dict]:
    cursor.execute(
        """SELECT id, occurred_at, change_type, title, description, page_path,
                  expected_impact, source, created_at
           FROM web_change_annotations
           WHERE business_id = %s AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
           ORDER BY occurred_at DESC LIMIT 200""",
        (business_id, period_days),
    )
    return [dict(row) for row in cursor.fetchall()]


def save_annotation(cursor, business_id: str, user_id: str, payload: object) -> dict:
    if not isinstance(payload, dict):
        raise WebTrackingConfigurationError("invalid_annotation")
    change_type = _text(payload.get("change_type"), 30)
    title = _text(payload.get("title"), 160)
    if change_type not in CHANGE_TYPES:
        raise WebTrackingConfigurationError("invalid_change_type")
    if not title:
        raise WebTrackingConfigurationError("change_title_required")
    raw_time = _text(payload.get("occurred_at"), 80)
    try:
        occurred_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00")) if raw_time else datetime.now(timezone.utc)
    except ValueError:
        raise WebTrackingConfigurationError("invalid_change_time")
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    annotation_id = str(uuid.uuid4())
    result = {
        "id": annotation_id,
        "occurred_at": occurred_at.astimezone(timezone.utc),
        "change_type": change_type,
        "title": title,
        "description": _text(payload.get("description"), 1000),
        "page_path": _text(payload.get("page_path"), 500),
        "expected_impact": _text(payload.get("expected_impact"), 500),
        "source": "manual",
    }
    cursor.execute(
        """INSERT INTO web_change_annotations (
               id, business_id, occurred_at, change_type, title, description,
               page_path, expected_impact, source, created_by
           ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'manual',%s)""",
        (
            result["id"], business_id, result["occurred_at"], result["change_type"],
            result["title"], result["description"], result["page_path"],
            result["expected_impact"], user_id or None,
        ),
    )
    return result


def save_system_annotation(cursor, business_id: str, title: str, change_type: str = "tracker") -> None:
    cursor.execute(
        """INSERT INTO web_change_annotations (
               id, business_id, occurred_at, change_type, title, source
           ) VALUES (%s,%s,NOW(),%s,%s,'system')""",
        (str(uuid.uuid4()), business_id, change_type, _text(title, 180)),
    )


def delete_annotation(cursor, business_id: str, annotation_id: str) -> bool:
    cursor.execute(
        "DELETE FROM web_change_annotations WHERE id = %s AND business_id = %s AND source = 'manual' RETURNING id",
        (annotation_id, business_id),
    )
    return cursor.fetchone() is not None


def save_campaign_cost(cursor, business_id: str, user_id: str, payload: object) -> dict:
    if not isinstance(payload, dict):
        raise WebTrackingConfigurationError("invalid_campaign_cost")
    source = _text(payload.get("source"), 120)
    currency = _text(payload.get("currency"), 3).upper()
    if not source or len(currency) != 3:
        raise WebTrackingConfigurationError("campaign_source_currency_required")
    try:
        period_start = date.fromisoformat(_text(payload.get("period_start"), 10))
        period_end = date.fromisoformat(_text(payload.get("period_end"), 10))
    except ValueError:
        raise WebTrackingConfigurationError("invalid_campaign_period")
    if period_end < period_start or (period_end - period_start).days > 366:
        raise WebTrackingConfigurationError("invalid_campaign_period")
    cost = _decimal_amount(payload.get("cost"))
    if cost is None:
        raise WebTrackingConfigurationError("campaign_cost_required")
    cost_id = str(uuid.uuid4())
    result = {
        "id": cost_id,
        "source": source,
        "medium": _text(payload.get("medium"), 120),
        "campaign": _text(payload.get("campaign"), 160),
        "content": _text(payload.get("content"), 160),
        "term": _text(payload.get("term"), 160),
        "period_start": period_start,
        "period_end": period_end,
        "cost": cost,
        "currency": currency,
        "external_id": _text(payload.get("external_id"), 160),
    }
    cursor.execute(
        """INSERT INTO web_campaign_costs (
               id, business_id, source, medium, campaign, content, term,
               period_start, period_end, cost, currency, external_id, created_by
           ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            result["id"], business_id, result["source"], result["medium"],
            result["campaign"], result["content"], result["term"], result["period_start"],
            result["period_end"], result["cost"], result["currency"],
            result["external_id"] or None, user_id or None,
        ),
    )
    return result


def list_campaign_costs(cursor, business_id: str, period_days: int = 90) -> list[dict]:
    cursor.execute(
        """SELECT id, source, medium, campaign, content, term, period_start, period_end,
                  cost, currency, external_id, created_at
           FROM web_campaign_costs
           WHERE business_id = %s
             AND period_end >= CURRENT_DATE - (%s::int - 1)
           ORDER BY period_start DESC, source, campaign LIMIT 500""",
        (business_id, period_days),
    )
    return [dict(row) for row in cursor.fetchall()]


def delete_campaign_cost(cursor, business_id: str, cost_id: str) -> bool:
    cursor.execute(
        "DELETE FROM web_campaign_costs WHERE id = %s AND business_id = %s RETURNING id",
        (cost_id, business_id),
    )
    return cursor.fetchone() is not None


def _group_funnel(cursor, business_id: str, period_days: int) -> dict:
    groups = list_page_groups(cursor, business_id)
    active_groups = [group for group in groups if group.get("enabled") and not group.get("is_draft")]
    cursor.execute(
        """SELECT DISTINCT session_id, page_path FROM web_events
           WHERE business_id = %s AND event_type = 'page_view'
             AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')""",
        (business_id, period_days),
    )
    page_rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """SELECT COUNT(DISTINCT session_id) AS count FROM web_events
           WHERE business_id = %s AND action_type IS NOT NULL
             AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')""",
        (business_id, period_days),
    )
    target_sessions = int(cursor.fetchone()["count"] or 0)
    cursor.execute(
        """SELECT COUNT(DISTINCT session_key) AS count FROM web_sessions
           WHERE business_id = %s AND started_at >= NOW() - (%s::int * INTERVAL '1 day')""",
        (business_id, period_days),
    )
    all_sessions = int(cursor.fetchone()["count"] or 0)
    stages = [{"key": "sessions", "label": "Сессии", "sessions": all_sessions}]
    for group_type, label in (("service", "Услуги"), ("pricing", "Цены")):
        relevant = [group for group in active_groups if group.get("group_type") == group_type]
        matched = {
            row["session_id"] for row in page_rows
            if any(
                page_matches(
                    row["page_path"], group["match_type"], group["include_patterns"] or [],
                    group["exclude_patterns"] or [],
                )
                for group in relevant
            )
        }
        if relevant:
            stages.append({"key": group_type, "label": label, "sessions": len(matched)})
    stages.append({"key": "target", "label": "Целевые действия", "sessions": target_sessions})
    return {"configured": bool(active_groups), "stages": stages}


def get_web_analytics_extensions(cursor, business_id: str, period_days: int = 30) -> dict:
    period_days = period_days if period_days in {7, 30, 90} else 30
    cursor.execute(
        """SELECT COALESCE(NULLIF(metadata_json->'cta'->>'id', ''), '(без ID)') AS cta_id,
                  MAX(NULLIF(metadata_json->'cta'->>'label', '')) AS label,
                  MAX(NULLIF(metadata_json->'cta'->>'position', '')) AS position,
                  MAX(NULLIF(metadata_json->'cta'->>'section_key', '')) AS section_key,
                  MAX(page_path) AS page_path,
                  COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'cta_impression') AS impressions,
                  COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'cta_click') AS clicks
           FROM web_events
           WHERE business_id = %s AND event_type IN ('cta_impression', 'cta_click')
             AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY COALESCE(NULLIF(metadata_json->'cta'->>'id', ''), '(без ID)')
           ORDER BY clicks DESC, impressions DESC LIMIT 100""",
        (business_id, period_days),
    )
    ctas = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """SELECT COALESCE(NULLIF(cta_id, ''), '(без ID)') AS cta_id,
                  COUNT(*) AS confirmed, COALESCE(SUM(amount), 0) AS revenue,
                  MAX(currency) AS currency
           FROM web_confirmed_conversions
           WHERE business_id = %s AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY COALESCE(NULLIF(cta_id, ''), '(без ID)')""",
        (business_id, period_days),
    )
    outcomes_by_cta = {row["cta_id"]: dict(row) for row in cursor.fetchall()}
    for item in ctas:
        impressions = int(item.get("impressions") or 0)
        clicks = int(item.get("clicks") or 0)
        item["ctr_percent"] = round(clicks * 100 / impressions, 1) if impressions else 0
        item.update(outcomes_by_cta.get(item["cta_id"], {"confirmed": 0, "revenue": 0, "currency": None}))
    cursor.execute(
        """SELECT COALESCE(NULLIF(metadata_json->'form'->>'id', ''), '(без ID)') AS form_id,
                  MAX(NULLIF(metadata_json->'form'->>'section_key', '')) AS section_key,
                  COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'form_start') AS starts,
                  COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'form_validation_error') AS validation_errors,
                  COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'form_submit_attempt') AS attempts,
                  COUNT(DISTINCT session_id) FILTER (WHERE event_type IN ('form_submit_success', 'form_submit')) AS successes,
                  COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'form_submit_error') AS submit_errors
           FROM web_events
           WHERE business_id = %s AND event_type = ANY(%s)
             AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY COALESCE(NULLIF(metadata_json->'form'->>'id', ''), '(без ID)')
           ORDER BY successes DESC, attempts DESC LIMIT 100""",
        (business_id, list(FORM_EVENT_TYPES), period_days),
    )
    forms = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """SELECT event_type, COUNT(*) AS count, COUNT(DISTINCT attribution_session_key) AS attributed,
                  COALESCE(SUM(amount), 0) AS revenue, MAX(currency) AS currency
           FROM web_confirmed_conversions
           WHERE business_id = %s AND occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY event_type ORDER BY count DESC""",
        (business_id, period_days),
    )
    outcomes = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """SELECT device_type, COUNT(*) AS sessions, COUNT(DISTINCT visitor_id) AS visitors
           FROM web_sessions WHERE business_id = %s
             AND started_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY device_type ORDER BY sessions DESC""",
        (business_id, period_days),
    )
    devices = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """SELECT COUNT(*) FILTER (WHERE prior_sessions = 0) AS new_visitors,
                  COUNT(*) FILTER (WHERE prior_sessions > 0) AS returning_visitors
           FROM (
               SELECT visitor_id,
                      COUNT(*) FILTER (WHERE started_at < NOW() - (%s::int * INTERVAL '1 day')) AS prior_sessions
               FROM web_sessions WHERE business_id = %s
               GROUP BY visitor_id
               HAVING MAX(started_at) >= NOW() - (%s::int * INTERVAL '1 day')
           ) cohorts""",
        (period_days, business_id, period_days),
    )
    cohorts = dict(cursor.fetchone())
    costs = list_campaign_costs(cursor, business_id, period_days)
    cursor.execute(
        """SELECT COALESCE(NULLIF(utm_source, ''), source_label, 'direct') AS source,
                  COALESCE(utm_campaign, '') AS campaign,
                  COALESCE(utm_content, '') AS content,
                  COUNT(*) AS sessions
           FROM web_sessions WHERE business_id = %s
             AND started_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY COALESCE(NULLIF(utm_source, ''), source_label, 'direct'), COALESCE(utm_campaign, ''), COALESCE(utm_content, '')
           ORDER BY sessions DESC LIMIT 200""",
        (business_id, period_days),
    )
    campaign_sessions = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """SELECT COALESCE(NULLIF(s.utm_source, ''), s.source_label, 'direct') AS source,
                  COALESCE(s.utm_campaign, '') AS campaign,
                  COALESCE(s.utm_content, '') AS content,
                  COUNT(*) FILTER (WHERE c.event_type IN ('lead_created', 'message_lead')) AS leads,
                  COUNT(*) FILTER (WHERE c.event_type IN ('booking_created', 'booking_confirmed')) AS bookings,
                  COALESCE(SUM(c.amount) FILTER (WHERE c.event_type = 'payment_completed'), 0) AS revenue,
                  MAX(c.currency) FILTER (WHERE c.event_type = 'payment_completed') AS currency
           FROM web_confirmed_conversions c
           JOIN web_sessions s ON s.business_id = c.business_id
                AND s.session_key = c.attribution_session_key
           WHERE c.business_id = %s AND c.occurred_at >= NOW() - (%s::int * INTERVAL '1 day')
           GROUP BY COALESCE(NULLIF(s.utm_source, ''), s.source_label, 'direct'), COALESCE(s.utm_campaign, ''), COALESCE(s.utm_content, '')""",
        (business_id, period_days),
    )
    campaign_outcomes = {(row["source"], row["campaign"], row["content"]): dict(row) for row in cursor.fetchall()}
    costs_by_campaign = {}
    for cost in costs:
        key = (cost.get("source") or "", cost.get("campaign") or "", cost.get("content") or "")
        costs_by_campaign[key] = costs_by_campaign.get(key, Decimal("0")) + Decimal(str(cost.get("cost") or 0))
    campaign_keys = {(row["source"], row["campaign"], row["content"]) for row in campaign_sessions} | set(campaign_outcomes) | set(costs_by_campaign)
    campaign_performance = []
    sessions_by_campaign = {(row["source"], row["campaign"], row["content"]): row for row in campaign_sessions}
    for key in sorted(campaign_keys):
        session_row = sessions_by_campaign.get(key, {})
        outcome_row = campaign_outcomes.get(key, {})
        campaign_cost = costs_by_campaign.get(key, Decimal("0"))
        leads = int(outcome_row.get("leads") or 0)
        revenue = Decimal(str(outcome_row.get("revenue") or 0))
        campaign_performance.append({
            "source": key[0], "campaign": key[1], "content": key[2], "sessions": int(session_row.get("sessions") or 0),
            "leads": leads, "bookings": int(outcome_row.get("bookings") or 0),
            "revenue": revenue, "currency": outcome_row.get("currency"), "cost": campaign_cost,
            "cpa": round(campaign_cost / leads, 2) if leads else None,
            "roi_percent": round((revenue - campaign_cost) * 100 / campaign_cost, 1) if campaign_cost else None,
        })
    cursor.execute(
        """SELECT DATE(day) AS day,
                  COUNT(DISTINCT s.session_key) AS sessions,
                  COUNT(DISTINCT c.id) AS outcomes
           FROM generate_series(
               CURRENT_DATE - ((%s::int - 1) * INTERVAL '1 day'), CURRENT_DATE, INTERVAL '1 day'
           ) day
           LEFT JOIN web_sessions s ON s.business_id = %s AND DATE(s.started_at) = DATE(day)
           LEFT JOIN web_confirmed_conversions c ON c.business_id = %s AND DATE(c.occurred_at) = DATE(day)
           GROUP BY DATE(day) ORDER BY DATE(day)""",
        (period_days, business_id, business_id),
    )
    daily_trend = [dict(row) for row in cursor.fetchall()]
    recommendations = []
    for form in forms:
        attempts = int(form.get("attempts") or 0)
        successes = int(form.get("successes") or 0)
        if attempts >= 5 and successes * 2 < attempts:
            recommendations.append({
                "kind": "form_dropoff",
                "title": f"Проверьте форму {form['form_id']}",
                "detail": f"Успешно отправлены {successes} из {attempts} попыток.",
            })
    for cta in ctas:
        if int(cta.get("impressions") or 0) >= 20 and float(cta.get("ctr_percent") or 0) < 2:
            recommendations.append({
                "kind": "low_cta_ctr",
                "title": f"Кнопку {cta.get('label') or cta['cta_id']} редко нажимают",
                "detail": f"CTR {cta['ctr_percent']}% при {cta['impressions']} просмотрах.",
            })
    return {
        "page_groups": list_page_groups(cursor, business_id),
        "goals": list_goals(cursor, business_id, period_days),
        "funnel_v2": _group_funnel(cursor, business_id, period_days),
        "cta_performance": ctas,
        "form_funnels": forms,
        "confirmed_outcomes": outcomes,
        "devices": devices,
        "visitor_cohorts": cohorts,
        "campaigns": {"sessions": campaign_sessions, "costs": costs, "performance": campaign_performance},
        "daily_trend": daily_trend,
        "annotations": list_annotations(cursor, business_id, period_days),
        "recommendations": recommendations[:10],
        "conversion_key": conversion_key_status(cursor, business_id),
    }
