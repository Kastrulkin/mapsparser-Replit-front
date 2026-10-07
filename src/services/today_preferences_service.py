"""User-controlled Today priority. Reads never create preferences or proposals.

Only confirmed interactive commands contribute to proposals. The maintenance
calculation is deterministic and cannot change a user's selected priority.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone


FLOWS = ("overview", "content", "influencers", "partnerships", "maps", "upsells", "automation")
FLOW_ALIASES = {"influencer": "influencers", "partnership": "partnerships", "average_ticket": "upsells", "cards": "maps", "agents": "automation", "services": "maps"}
FLOW_CAPABILITIES = {"content": "social_content", "influencers": "influencers", "partnerships": "partnerships", "maps": "maps", "upsells": "average_ticket", "automation": "automation"}
CONFIRMED_EVENTS = frozenset({"content_draft_saved", "content_scheduled", "automation_configured", "automation_preflight_approved", "automation_run_linked", "reply_recorded", "deal_started", "result_added", "map_task_completed", "action_marked_sent", "followup_created"})
OBSERVATION_WINDOW = timedelta(days=14)


class PreferenceError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code = code
        self.status = status


def enabled(name="LOCALOS_TODAY_PERSONALIZATION_ENABLED", default=True):
    return str(os.getenv(name, str(default))).lower() in {"1", "true", "yes", "on"}


def normalize_flow(value):
    value = str(value or "")
    return FLOW_ALIASES.get(value, value)


def _row(cursor, value):
    if value is None:
        return {}
    if hasattr(value, "keys"):
        return dict(value)
    return dict(zip([column[0] for column in cursor.description], value))


def _json(value):
    if isinstance(value, dict):
        return value
    return json.loads(value) if isinstance(value, str) and value else {}


def _iso(value):
    return value.isoformat() if isinstance(value, (datetime, date)) else value


def _now(value=None):
    result = value or datetime.now(timezone.utc)
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def schema_available(cursor):
    cursor.execute("SELECT to_regclass('today_preferences') table_ref")
    return bool(_row(cursor, cursor.fetchone()).get("table_ref"))


def _key(user_id, scope):
    kind, scope_id = scope.get("kind"), str(scope.get("id") or "")
    if not user_id or kind not in {"business", "network"} or not scope_id:
        raise PreferenceError("invalid_scope")
    return str(user_id), kind, scope_id


def load_record(cursor, *, user_id, scope, lock=False):
    cursor.execute("SELECT * FROM today_preferences WHERE user_id = %s AND scope_type = %s AND scope_id = %s" + (" FOR UPDATE" if lock else ""), _key(user_id, scope))
    return _row(cursor, cursor.fetchone())


def preference_payload(record, *, scope, now=None):
    observed = _now(now)
    undo_until = record.get("undo_until")
    if isinstance(undo_until, str):
        undo_until = datetime.fromisoformat(undo_until)
    return {
        "scope_type": scope["kind"], "scope_id": str(scope["id"]),
        "primary_flow": record.get("primary_flow") or "overview",
        "suggestions_enabled": record.get("suggestions_enabled", True),
        "revision": record.get("revision", 0),
        "updated_at": _iso(record.get("updated_at")),
        "previous_flow": record.get("previous_flow"),
        "can_undo": bool(record.get("previous_flow") and undo_until and _now(undo_until) > observed),
    }


def read_preferences(cursor, *, user_id, scope, allowed_flows=FLOWS, now=None):
    record = load_record(cursor, user_id=user_id, scope=scope)
    proposal = _json(record.get("proposal_json")) or None
    if proposal and (not enabled("LOCALOS_TODAY_PROPOSALS_ENABLED", False) or
                     proposal.get("flow") not in allowed_flows or
                     proposal.get("preference_revision") != record.get("revision") or
                     not record.get("suggestions_enabled", True)):
        proposal = None
    return {"preference": preference_payload(record, scope=scope, now=now), "priority_proposal": proposal}


def change_preferences(cursor, *, user_id, scope, command, allowed_flows=FLOWS, now=None):
    observed = _now(now)
    expected = command.get("expected_revision")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise PreferenceError("expected_revision_required")
    action = command.get("action")
    if action not in {"set", "accept", "decline", "snooze", "opt_out", "enable", "undo"}:
        raise PreferenceError("invalid_action")
    key = _key(user_id, scope)
    # Serialize first creation too. Conflicting clients receive 409, never last-write-wins.
    cursor.execute("INSERT INTO today_preferences(user_id,scope_type,scope_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING revision", key)
    inserted = cursor.fetchone() is not None
    record = load_record(cursor, user_id=user_id, scope=scope, lock=True)
    if (0 if inserted else record["revision"]) != expected:
        raise PreferenceError("preference_conflict", 409)
    previous = record["primary_flow"]
    proposal = _json(record.get("proposal_json"))
    if action in {"accept", "decline", "snooze"}:
        if not enabled("LOCALOS_TODAY_PROPOSALS_ENABLED", False):
            raise PreferenceError("proposals_disabled", 409)
        if not proposal or proposal.get("id") != command.get("proposal_id") or proposal.get("preference_revision") != expected:
            raise PreferenceError("proposal_stale", 409)
    if action in {"set", "accept", "undo"}:
        flow = command.get("primary_flow") if action == "set" else proposal.get("flow")
        if action == "undo":
            if not preference_payload(record, scope=scope, now=observed)["can_undo"]:
                raise PreferenceError("undo_expired", 409)
            flow = record.get("previous_flow")
        if flow not in FLOWS or flow not in allowed_flows:
            raise PreferenceError("flow_unavailable", 403)
        record["primary_flow"] = flow
        record["previous_flow"] = previous if action != "undo" else None
        record["undo_until"] = observed + timedelta(days=14) if action != "undo" else None
        record["next_offer_at"] = observed + timedelta(days=14)
    elif action == "decline":
        dismissed = _json(record.get("dismissed_flows_json"))
        dismissed[proposal["flow"]] = (observed + timedelta(days=30)).isoformat()
        record["dismissed_flows_json"] = dismissed
        record["next_offer_at"] = observed + timedelta(days=14)
    elif action == "snooze":
        record["next_offer_at"] = observed + timedelta(days=14)
    elif action == "opt_out":
        record["suggestions_enabled"] = False
    elif action == "enable":
        record["suggestions_enabled"] = True
    cursor.execute("""UPDATE today_preferences SET primary_flow=%s, suggestions_enabled=%s,
        revision=%s, previous_flow=%s, undo_until=%s, proposal_json=NULL,
        candidate_flow=NULL,candidate_since=NULL, evaluated_on=NULL,
        next_offer_at=%s,dismissed_flows_json=%s::jsonb,updated_at=%s
        WHERE user_id=%s AND scope_type=%s AND scope_id=%s RETURNING *""",
        (record["primary_flow"], record["suggestions_enabled"], expected + 1,
         record.get("previous_flow"), record.get("undo_until"), record.get("next_offer_at"),
         json.dumps(_json(record.get("dismissed_flows_json"))), observed, *key))
    updated = _row(cursor, cursor.fetchone())
    from services.product_telemetry_service import record_product_event
    event = {"set":"today_priority_set", "accept":"today_priority_accepted",
        "decline":"today_priority_declined", "snooze":"today_priority_snoozed",
        "opt_out":"today_priority_disabled", "enable":"today_priority_enabled",
        "undo":"today_priority_undone"}[action]
    record_product_event(cursor,event_name=event,surface="web",
        business_id=scope["id"] if scope["kind"]=="business" else None,
        user_id=user_id,scope_type=scope["kind"],scope_id=scope["id"],
        flow_type=record["primary_flow"],signal_source="preference_decision",
        deduplication_key=f"preference:{scope['kind']}:{scope['id']}:{expected+1}",
        properties={"previous_flow":previous,"primary_flow":record["primary_flow"],
            "proposal_id":command.get("proposal_id"),"revision":expected+1})
    return {"preference": preference_payload(updated, scope=scope, now=observed), "priority_proposal": None}


def choose_candidate(activity, primary_flow):
    """Pilot thresholds, not learned facts: 14 days, 3 days, 5 actions, 60% share."""
    scores = {}
    for item in activity:
        flow = normalize_flow(item.get("flow"))
        if flow in FLOW_CAPABILITIES:
            scores[flow] = {"flow": flow, "active_days": int(item.get("active_days") or 0), "confirmed_actions": int(item.get("confirmed_actions") or 0)}
    if not scores:
        return None
    candidate = sorted(scores.values(), key=lambda item: (-item["confirmed_actions"], item["flow"]))[0]
    total = sum(item["confirmed_actions"] for item in scores.values())
    candidate["action_share"] = round(candidate["confirmed_actions"] / max(total, 1), 4)
    if candidate["flow"] == primary_flow or candidate["active_days"] < 3 or candidate["confirmed_actions"] < 5 or candidate["action_share"] < .6:
        return None
    return candidate


def observation_window_complete(cursor, *, record, now):
    """A proposal needs a real collection window, never inferred elapsed use."""
    observed = _now(now)
    cursor.execute("""SELECT MIN(occurred_at) observed_from
        FROM product_analytics_events
        WHERE user_id=%s AND signal_source='confirmed_user_action'
          AND event_name = ANY(%s)
          AND ((%s='business' AND business_id=%s) OR
               (%s='network' AND business_id IN (SELECT id FROM businesses WHERE network_id=%s)))""",
        (record["user_id"], list(CONFIRMED_EVENTS), record["scope_type"], record["scope_id"], record["scope_type"], record["scope_id"]))
    observed_from = _row(cursor, cursor.fetchone()).get("observed_from")
    if isinstance(observed_from, str):
        observed_from = datetime.fromisoformat(observed_from)
    return bool(observed_from and _now(observed_from) <= observed - OBSERVATION_WINDOW)


def evaluate_record(cursor, *, record, now=None):
    observed = _now(now)
    day = observed.date()
    key = (record["user_id"], record["scope_type"], record["scope_id"])
    if record.get("evaluated_on") == day or not record.get("suggestions_enabled"):
        return False
    # Events use UTC days consistently across devices; no client clock controls eligibility.
    cursor.execute("""SELECT COALESCE(flow_type,'') flow,
            COUNT(DISTINCT (occurred_at AT TIME ZONE 'UTC')::date) active_days,
            COUNT(*) confirmed_actions
        FROM product_analytics_events
        WHERE user_id=%s AND signal_source='confirmed_user_action'
          AND occurred_at >= %s AND occurred_at <= %s
          AND event_name = ANY(%s)
          AND ((%s='business' AND business_id=%s) OR
               (%s='network' AND business_id IN (SELECT id FROM businesses WHERE network_id=%s)))
        GROUP BY flow_type""", (record["user_id"], observed-timedelta(days=14), observed,
            list(CONFIRMED_EVENTS), record["scope_type"], record["scope_id"], record["scope_type"], record["scope_id"]))
    candidate = choose_candidate([_row(cursor, row) for row in cursor.fetchall()], record["primary_flow"])
    flow = candidate["flow"] if candidate else None
    since = record.get("candidate_since") if flow and flow == record.get("candidate_flow") else day if flow else None
    proposal = _json(record.get("proposal_json")) or None
    if proposal and (proposal.get("flow") != flow or proposal.get("preference_revision") != record["revision"]):
        proposal = None
    dismissed = _json(record.get("dismissed_flows_json"))
    blocked_until = datetime.fromisoformat(dismissed[flow]) if flow in dismissed else None
    may_offer = not record.get("next_offer_at") or _now(record["next_offer_at"]) <= observed
    may_offer = may_offer and (not blocked_until or _now(blocked_until) <= observed)
    may_offer = may_offer and enabled("LOCALOS_TODAY_PROPOSALS_ENABLED", False)
    offered = bool(candidate and since and since < day and may_offer and not proposal
                   and observation_window_complete(cursor, record=record, now=observed))
    if offered:
        proposal = {"id": str(uuid.uuid4()), **candidate, "reason_code": "activity_shift", "preference_revision": record["revision"], "created_at": observed.isoformat()}
    cursor.execute("""UPDATE today_preferences SET candidate_flow=%s,candidate_since=%s,
        evaluated_on=%s,proposal_json=%s::jsonb,next_offer_at=%s
        WHERE user_id=%s AND scope_type=%s AND scope_id=%s""",
        (flow, since, day, json.dumps(proposal) if proposal else None,
         observed + timedelta(days=14) if offered else record.get("next_offer_at"), *key))
    return offered


def materialize_priority_proposals(db_factory, *, now=None, limit=100):
    if not enabled("LOCALOS_TODAY_ACTIVITY_ENABLED", False):
        return 0
    observed = _now(now)
    db = db_factory()
    try:
        cursor = db.conn.cursor()
        if not schema_available(cursor):
            return 0
        cursor.execute("""SELECT * FROM today_preferences WHERE suggestions_enabled
            AND (evaluated_on IS NULL OR evaluated_on < %s)
            ORDER BY evaluated_on NULLS FIRST,updated_at
            LIMIT %s FOR UPDATE SKIP LOCKED""", (observed.date(), limit))
        records = [_row(cursor, row) for row in cursor.fetchall()]
        result = sum(evaluate_record(cursor, record=record, now=observed) for record in records)
        db.conn.commit()
        return result
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
