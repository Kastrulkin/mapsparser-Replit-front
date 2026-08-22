"""Privacy-first website event ingestion and SQL analytics for LocalOS."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import secrets
import unicodedata
import uuid
from urllib.parse import urlparse

from psycopg2.extras import execute_values


SUPPORTED_EVENTS = {
    "session_start",
    "page_view",
    "scroll_depth",
    "click",
    "outbound_click",
    "form_start",
    "form_submit",
    "heartbeat",
    "page_leave",
    "section_view",
    "section_engagement",
    "cta_impression",
    "cta_click",
    "form_submit_attempt",
    "form_validation_error",
    "form_submit_success",
    "form_submit_error",
}
MAX_BATCH_EVENTS = 25
MAX_REQUEST_BYTES = 64 * 1024
MAX_METADATA_BYTES = 4096
MAX_EVENTS_PER_SESSION = 1000
TRACKER_SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, 2}
LEGACY_TRACKER_VERSION = "legacy"
IDENTIFIER_PATTERN = re.compile(r"^[vse]_[a-f0-9]{24,64}$")
TRACKER_ID_PATTERN = re.compile(r"^pub_[A-Za-z0-9_-]{16,80}$")
HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class WebTrackingLimitError(ValueError):
    """Raised when a session exceeds the bounded raw-event allowance."""


class WebTrackingConflictError(ValueError):
    """Raised when an anonymous session is reused with another visitor ID."""


class WebTrackingDeletionError(ValueError):
    """Raised when the reviewed destructive deletion contract is not satisfied."""


def _text(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFC", value)
    without_controls = "".join(
        character for character in normalized
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs", "Co"}
    )
    return without_controls.strip()[:limit]


def normalize_hostname(value: object) -> str:
    raw = _text(value, 253).rstrip(".").lower()
    if not raw:
        return ""
    try:
        hostname = raw.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    if hostname == "localhost":
        return hostname
    labels = hostname.split(".")
    if len(labels) < 2 or any(not HOST_LABEL_PATTERN.fullmatch(label) for label in labels):
        return ""
    return hostname


def canonical_site_hostname(value: object) -> str:
    hostname = normalize_hostname(value)
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


def _timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_href(value: object, page_hostname: str = "") -> str:
    href = _text(value, 500)
    if not href:
        return ""
    parsed = urlparse(href)
    if parsed.scheme not in {"", "http", "https", "tel", "mailto"}:
        return ""
    if parsed.scheme in {"tel", "mailto"}:
        return f"{parsed.scheme}:"
    if not parsed.scheme:
        return parsed.path[:500]
    hostname = normalize_hostname(parsed.hostname or "")
    if not hostname:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    include_port = port and not (parsed.scheme == "http" and port == 80) and not (parsed.scheme == "https" and port == 443)
    port_suffix = f":{port}" if include_port else ""
    origin = f"{parsed.scheme}://{hostname}{port_suffix}"
    if canonical_site_hostname(hostname) == canonical_site_hostname(page_hostname):
        return f"{origin}{parsed.path}"[:500]
    return origin[:500]


def classify_traffic_source(utm_source: object, referrer: object) -> dict[str, str]:
    utm_value = _text(utm_source, 120)
    safe_referrer = _safe_href(referrer)
    parsed = urlparse(safe_referrer)
    domain = normalize_hostname(parsed.hostname or "")
    if utm_value:
        lowered_utm = utm_value.casefold()
        if any(marker in lowered_utm for marker in ("maps", "map", "2gis", "карт")):
            return {"type": "maps", "label": utm_value, "domain": domain}
        return {"type": "utm", "label": utm_value, "domain": domain}
    if not referrer:
        return {"type": "direct", "label": "direct", "domain": ""}
    if not domain:
        return {"type": "unknown", "label": "unknown", "domain": ""}
    if domain == "2gis.ru" or domain.endswith(".2gis.ru") or domain.startswith("maps.google."):
        return {"type": "maps", "label": "maps", "domain": domain}
    if domain in {"vk.com", "t.me", "telegram.me", "ok.ru", "dzen.ru"} or domain.endswith(".vk.com"):
        return {"type": "social", "label": domain, "domain": domain}
    if domain == "yandex.ru" or domain.endswith(".yandex.ru"):
        return {"type": "search", "label": "Яндекс", "domain": domain}
    if domain == "google.com" or domain.startswith("google.") or ".google." in domain:
        return {"type": "search", "label": "Google", "domain": domain}
    if domain == "bing.com" or domain.endswith(".bing.com"):
        return {"type": "search", "label": "Bing", "domain": domain}
    return {"type": "referral", "label": domain, "domain": domain}


def classify_target_action(event_type: str, metadata: dict, page_hostname: str) -> dict[str, str | None]:
    if event_type in {"form_submit", "form_submit_success"}:
        action = metadata.get("form", {}).get("action", "")
        domain = normalize_hostname(urlparse(action).hostname or "") or page_hostname
        return {"type": "form", "provider": None, "domain": domain}
    if event_type != "outbound_click":
        return {"type": None, "provider": None, "domain": None}
    href = metadata.get("element", {}).get("href", "")
    if href == "tel:":
        return {"type": "phone", "provider": None, "domain": None}
    if href == "mailto:":
        return {"type": "email", "provider": None, "domain": None}
    domain = normalize_hostname(urlparse(href).hostname or "")
    if domain and canonical_site_hostname(domain) == canonical_site_hostname(page_hostname):
        return {"type": None, "provider": None, "domain": None}
    if domain == "wa.me" or domain == "whatsapp.com" or domain.endswith(".whatsapp.com"):
        return {"type": "whatsapp", "provider": "whatsapp", "domain": domain}
    if domain == "t.me" or domain == "telegram.me" or domain.endswith(".telegram.me"):
        return {"type": "telegram", "provider": "telegram", "domain": domain}
    yclients_domain = domain in {"yclients.com", "yclients.net"} or domain.endswith((".yclients.com", ".yclients.net"))
    dikidi_domain = domain in {"dikidi.ru", "dikidi.com", "dikidi.net"} or domain.endswith((".dikidi.ru", ".dikidi.com", ".dikidi.net"))
    if yclients_domain or dikidi_domain:
        provider = "yclients" if yclients_domain else "dikidi"
        return {"type": "booking", "provider": provider, "domain": domain}
    return {"type": "outbound", "provider": domain or None, "domain": domain or None}


def _legacy_event_id(tracker_id: str, event: dict) -> str:
    source = "|".join([
        tracker_id,
        event["session_key"],
        event["event_type"],
        event["occurred_at"].isoformat(),
        event["hostname"],
        event["path"],
    ])
    return f"e_{hashlib.sha256(source.encode('utf-8')).hexdigest()[:32]}"


def validate_event(raw: object, now: datetime | None = None) -> tuple[dict | None, str | None]:
    if not isinstance(raw, dict):
        return None, "invalid_event_object"
    event_type = _text(raw.get("event"), 40)
    if event_type not in SUPPORTED_EVENTS:
        return None, "unsupported_event"
    visitor_id = _text(raw.get("visitor_id"), 80)
    session_id = _text(raw.get("session_id"), 80)
    if not IDENTIFIER_PATTERN.fullmatch(visitor_id) or not IDENTIFIER_PATTERN.fullmatch(session_id):
        return None, "invalid_anonymous_identifiers"
    occurred_at = _timestamp(raw.get("timestamp"))
    current = now or datetime.now(timezone.utc)
    if occurred_at is None or occurred_at < current - timedelta(days=7) or occurred_at > current + timedelta(minutes=10):
        return None, "invalid_timestamp"
    engagement_ms = raw.get("engagement_ms")
    max_engagement_ms = 600000 if event_type == "section_engagement" else 30000
    if event_type in {"heartbeat", "page_leave", "section_engagement"} and not (
        type(engagement_ms) is int and 0 <= engagement_ms <= max_engagement_ms
    ):
        return None, "invalid_engagement"

    page = raw.get("page") if isinstance(raw.get("page"), dict) else {}
    hostname = normalize_hostname(page.get("hostname"))
    if not hostname:
        return None, "invalid_hostname"
    path = (_text(page.get("path"), 1000) or "/").split("?", 1)[0].split("#", 1)[0] or "/"
    if not path.startswith("/"):
        path = "/"
    utm = raw.get("utm") if isinstance(raw.get("utm"), dict) else {}
    element = raw.get("element") if isinstance(raw.get("element"), dict) else {}
    form = raw.get("form") if isinstance(raw.get("form"), dict) else {}
    section = raw.get("section") if isinstance(raw.get("section"), dict) else {}
    cta = raw.get("cta") if isinstance(raw.get("cta"), dict) else {}

    metadata = {
        "title": _text(page.get("title"), 300),
        "referrer": _safe_href(raw.get("referrer")),
        "utm": {
            "source": _text(utm.get("source"), 120),
            "medium": _text(utm.get("medium"), 120),
            "campaign": _text(utm.get("campaign"), 160),
            "term": _text(utm.get("term"), 160),
            "content": _text(utm.get("content"), 160),
        },
        "element": {
            "tag": _text(element.get("tag"), 20).lower(),
            "href": _safe_href(element.get("href"), hostname),
            "aria_label": _text(element.get("aria_label"), 160),
            "text": _text(element.get("text"), 160),
        },
        "form": {
            "id": _text(form.get("id"), 120),
            "name": _text(form.get("name"), 120),
            "action": _safe_href(form.get("action"), hostname),
            "section_key": _text(form.get("section_key"), 100),
        },
        "section": {
            "key": _text(section.get("key"), 100),
            "label": _text(section.get("label"), 120),
            "position": section.get("position") if type(section.get("position")) is int and 1 <= section.get("position") <= 500 else None,
        },
        "cta": {
            "id": _text(cta.get("id"), 120),
            "label": _text(cta.get("label"), 160),
            "position": _text(cta.get("position"), 80),
            "section_key": _text(cta.get("section_key"), 100),
        },
        "error_type": _text(raw.get("error_type"), 80),
        "depth": raw.get("depth") if raw.get("depth") in {25, 50, 75, 100} else None,
        "engagement_ms": engagement_ms if type(engagement_ms) is int and 0 <= engagement_ms <= max_engagement_ms else None,
        "device_type": _text(raw.get("device_type"), 20) or "unknown",
    }
    if metadata["device_type"] not in {"mobile", "tablet", "desktop", "unknown"}:
        metadata["device_type"] = "unknown"
    if len(json.dumps(metadata, ensure_ascii=False).encode("utf-8")) > MAX_METADATA_BYTES:
        return None, "event_metadata_too_large"
    action = classify_target_action(event_type, metadata, hostname)
    return {
        "event_id": _text(raw.get("event_id"), 80),
        "event_type": event_type,
        "visitor_key": visitor_id,
        "session_key": session_id,
        "occurred_at": occurred_at,
        "hostname": hostname,
        "path": path,
        "metadata": metadata,
        "action_type": action["type"],
        "action_provider": action["provider"],
        "action_domain": action["domain"],
    }, None


def validate_batch(payload: object, now: datetime | None = None) -> tuple[str, list[dict], str | None]:
    if not isinstance(payload, dict):
        return "", [], "invalid_payload_object"
    tracker_id = _text(payload.get("tracker_id"), 100)
    events = payload.get("events")
    if not TRACKER_ID_PATTERN.fullmatch(tracker_id):
        return "", [], "invalid_tracker_id"
    if not isinstance(events, list) or not events or len(events) > MAX_BATCH_EVENTS:
        return "", [], "invalid_batch_size"
    schema_version = payload.get("schema_version", 1)
    if type(schema_version) is not int or schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        return "", [], "unsupported_schema_version"
    tracker_version = _text(payload.get("tracker_version"), 40) or LEGACY_TRACKER_VERSION
    clean_events = []
    for raw in events:
        clean, error = validate_event(raw, now)
        if error:
            return "", [], error
        if schema_version >= 2 and not IDENTIFIER_PATTERN.fullmatch(clean["event_id"]):
            return "", [], "invalid_event_id"
        if not clean["event_id"]:
            clean["event_id"] = _legacy_event_id(tracker_id, clean)
        clean["schema_version"] = schema_version
        clean["tracker_version"] = tracker_version
        clean_events.append(clean)
    return tracker_id, clean_events, None


def validate_tracker_domains(events: list[dict], allowed_domains: object) -> str | None:
    allowed = {
        normalize_hostname(domain)
        for domain in (allowed_domains if isinstance(allowed_domains, list) else [])
    }
    allowed.discard("")
    if not allowed:
        return "tracker_domains_not_configured"
    if any(event["hostname"] not in allowed for event in events):
        return "hostname_not_allowed"
    return None


def ensure_tracker(cursor, business_id: str, *, allow_create: bool = True) -> dict | None:
    cursor.execute(
        """
        SELECT id, public_tracker_id, domain, allowed_domains, enabled, tracking_enabled,
               created_at, first_event_at, last_event_at, last_tracker_version, last_schema_version,
               last_error_code, last_error_at, raw_retention_days, aggregate_retention_days
        FROM business_web_trackers
        WHERE business_id = %s
        ORDER BY created_at
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    if not row and not allow_create:
        return None
    if not row:
        cursor.execute("SELECT COALESCE(NULLIF(site, ''), NULLIF(website, '')) AS website FROM businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone() or {}
        parsed_site = urlparse(str(business.get("website") or ""))
        initial_hostname = normalize_hostname(parsed_site.hostname or "")
        initial_domains = [initial_hostname] if initial_hostname else []
        tracker_uuid = str(uuid.uuid4())
        public_id = f"pub_{secrets.token_urlsafe(18)}"
        cursor.execute(
            """
            INSERT INTO business_web_trackers (id, business_id, public_tracker_id, domain, allowed_domains)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, public_tracker_id, domain, allowed_domains, enabled, tracking_enabled,
                      created_at, first_event_at, last_event_at, last_tracker_version,
                      last_schema_version, last_error_code, last_error_at,
                      raw_retention_days, aggregate_retention_days
            """,
            (tracker_uuid, business_id, public_id, initial_hostname or None, initial_domains),
        )
        row = cursor.fetchone()
    return dict(row)


def tracker_status(tracker: dict) -> dict:
    last_event_at = tracker.get("last_event_at")
    working = bool(last_event_at)
    return {
        "public_tracker_id": tracker.get("public_tracker_id"),
        "domain": tracker.get("domain"),
        "allowed_domains": list(tracker.get("allowed_domains") or []),
        "enabled": bool(tracker.get("enabled") and tracker.get("tracking_enabled")),
        "status": "working" if working else "not_detected",
        "last_event_at": last_event_at.isoformat() if last_event_at else None,
        "tracker_version": tracker.get("last_tracker_version"),
        "schema_version": tracker.get("last_schema_version"),
        "last_error_code": tracker.get("last_error_code"),
        "last_error_at": tracker.get("last_error_at").isoformat() if tracker.get("last_error_at") else None,
        "raw_retention_days": int(tracker.get("raw_retention_days") or 180),
        "aggregate_retention_days": int(tracker.get("aggregate_retention_days") or 730),
    }


def delete_business_web_analytics(
    cursor,
    business_id: str,
    requested_by: str,
    *,
    dry_run: bool = True,
) -> dict:
    cursor.execute("SET LOCAL statement_timeout = %s", (30000,))
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM business_web_trackers WHERE business_id = %s) AS trackers,
            (SELECT COUNT(*) FROM business_web_trackers WHERE business_id = %s AND enabled AND tracking_enabled) AS active_trackers,
            (SELECT COUNT(*) FROM web_visitors WHERE business_id = %s) AS visitors,
            (SELECT COUNT(*) FROM web_sessions WHERE business_id = %s) AS sessions,
            (SELECT COUNT(*) FROM web_events WHERE business_id = %s) AS events,
            (SELECT COUNT(*) FROM web_daily_metrics WHERE business_id = %s) AS metrics,
            (SELECT COUNT(*) FROM web_page_groups WHERE business_id = %s) AS page_groups,
            (SELECT COUNT(*) FROM web_goals WHERE business_id = %s) AS goals,
            (SELECT COUNT(*) FROM web_confirmed_conversions WHERE business_id = %s) AS confirmed_conversions,
            (SELECT COUNT(*) FROM web_campaign_costs WHERE business_id = %s) AS campaign_costs,
            (SELECT COUNT(*) FROM web_change_annotations WHERE business_id = %s) AS change_annotations
        """,
        (
            business_id, business_id, business_id, business_id, business_id, business_id,
            business_id, business_id, business_id, business_id, business_id,
        ),
    )
    counts = {key: int(value or 0) for key, value in dict(cursor.fetchone() or {}).items()}
    for optional_key in ("page_groups", "goals", "confirmed_conversions", "campaign_costs", "change_annotations"):
        counts.setdefault(optional_key, 0)
    audit_id = str(uuid.uuid4())
    if dry_run:
        cursor.execute(
            """INSERT INTO web_tracking_deletion_audits
               (id, business_id, requested_by, mode, status, trackers, visitors, sessions, events, metrics,
                page_groups, goals, confirmed_conversions, campaign_costs, change_annotations)
               VALUES (%s, %s, %s, 'dry_run', 'reviewed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (audit_id, business_id, requested_by, counts["trackers"], counts["visitors"],
             counts["sessions"], counts["events"], counts["metrics"], counts["page_groups"],
             counts["goals"], counts["confirmed_conversions"], counts["campaign_costs"],
             counts["change_annotations"]),
        )
        return {"audit_id": audit_id, "mode": "dry_run", "status": "reviewed", **counts}
    cursor.execute(
        """SELECT id, trackers, visitors, sessions, events, metrics, page_groups, goals,
                  confirmed_conversions, campaign_costs, change_annotations
           FROM web_tracking_deletion_audits
           WHERE business_id = %s AND requested_by = %s AND mode = 'dry_run' AND status = 'reviewed'
             AND created_at >= NOW() - INTERVAL '24 hours'
           ORDER BY created_at DESC LIMIT 1""",
        (business_id, requested_by),
    )
    review = cursor.fetchone()
    if not review:
        raise WebTrackingDeletionError("recent_dry_run_required")
    if counts["active_trackers"]:
        raise WebTrackingDeletionError("disable_tracking_before_deletion")
    deletion_keys = (
        "trackers", "visitors", "sessions", "events", "metrics", "page_groups", "goals",
        "confirmed_conversions", "campaign_costs", "change_annotations",
    )
    review_values = dict(review)
    if any(int(review_values.get(key) or 0) != counts[key] for key in deletion_keys):
        raise WebTrackingDeletionError("deletion_scope_changed")
    cursor.execute("DELETE FROM web_page_groups WHERE business_id = %s", (business_id,))
    cursor.execute("DELETE FROM web_goals WHERE business_id = %s", (business_id,))
    cursor.execute("DELETE FROM web_confirmed_conversions WHERE business_id = %s", (business_id,))
    cursor.execute("DELETE FROM web_campaign_costs WHERE business_id = %s", (business_id,))
    cursor.execute("DELETE FROM web_change_annotations WHERE business_id = %s", (business_id,))
    cursor.execute("DELETE FROM business_web_trackers WHERE business_id = %s", (business_id,))
    cursor.execute("DELETE FROM web_sessions WHERE business_id = %s", (business_id,))
    cursor.execute("DELETE FROM web_visitors WHERE business_id = %s", (business_id,))
    cursor.execute(
        """INSERT INTO web_tracking_deletion_audits
               (id, business_id, requested_by, mode, status, trackers, visitors, sessions, events, metrics,
                page_groups, goals, confirmed_conversions, campaign_costs, change_annotations)
               VALUES (%s, %s, %s, 'execute', 'completed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (audit_id, business_id, requested_by, counts["trackers"], counts["visitors"],
         counts["sessions"], counts["events"], counts["metrics"], counts["page_groups"],
         counts["goals"], counts["confirmed_conversions"], counts["campaign_costs"],
         counts["change_annotations"]),
    )
    return {"audit_id": audit_id, "mode": "execute", "status": "completed", **counts}


def ingest_events(cursor, tracker: dict, events: list[dict]) -> dict[str, int]:
    business_id = str(tracker["business_id"])
    tracker_uuid = tracker["id"]
    cursor.execute("SET LOCAL statement_timeout = %s", (5000,))
    session_visitors = {}
    for event in events:
        prior_visitor = session_visitors.setdefault(event["session_key"], event["visitor_key"])
        if prior_visitor != event["visitor_key"]:
            raise WebTrackingConflictError("session_visitor_mismatch")
    lock_keys = sorted(f"{business_id}:{session_key}" for session_key in session_visitors)
    cursor.execute(
        """SELECT pg_advisory_xact_lock(hashtextextended(lock_key, 0))
           FROM unnest(%s::text[]) AS keys(lock_key) ORDER BY lock_key""",
        (lock_keys,),
    )
    visitor_bounds = {}
    for event in events:
        bounds = visitor_bounds.setdefault(event["visitor_key"], [event["occurred_at"], event["occurred_at"]])
        bounds[0] = min(bounds[0], event["occurred_at"])
        bounds[1] = max(bounds[1], event["occurred_at"])
    visitor_values = [
        (str(uuid.uuid4()), business_id, key, bounds[0], bounds[1])
        for key, bounds in visitor_bounds.items()
    ]
    visitor_rows = execute_values(
        cursor,
        """INSERT INTO web_visitors (id, business_id, anonymous_id, first_seen_at, last_seen_at) VALUES %s
           ON CONFLICT (business_id, anonymous_id) DO UPDATE
           SET last_seen_at = GREATEST(web_visitors.last_seen_at, EXCLUDED.last_seen_at)
           RETURNING anonymous_id, id""",
        visitor_values,
        fetch=True,
    )
    visitor_ids = {row["anonymous_id"]: row["id"] for row in visitor_rows}
    sessions = {}
    for event in sorted(events, key=lambda item: item["occurred_at"]):
        sessions.setdefault(event["session_key"], event)
    session_values = []
    for session_key, event in sessions.items():
        meta = event["metadata"]
        utm = meta["utm"]
        source = classify_traffic_source(utm["source"], meta["referrer"])
        session_values.append((
            str(uuid.uuid4()), business_id, visitor_ids[event["visitor_key"]], session_key,
            event["occurred_at"], event["path"], event["hostname"], meta["referrer"],
            utm["source"], utm["medium"], utm["campaign"], utm["term"], utm["content"],
            meta["device_type"],
            source["type"], source["label"], source["domain"],
        ))
    session_rows = execute_values(
        cursor,
        """INSERT INTO web_sessions (
               id, business_id, visitor_id, session_key, started_at, landing_page,
               landing_hostname, referrer, utm_source, utm_medium, utm_campaign, utm_term,
               utm_content, device_type,
               source_type, source_label, source_domain
           ) VALUES %s
           ON CONFLICT (business_id, session_key) DO UPDATE
           SET ended_at = GREATEST(COALESCE(web_sessions.ended_at, EXCLUDED.started_at), EXCLUDED.started_at)
           RETURNING session_key, id, visitor_id""",
        session_values,
        fetch=True,
    )
    session_ids = {row["session_key"]: row["id"] for row in session_rows}
    expected_visitors = {
        session_key: visitor_ids[event["visitor_key"]]
        for session_key, event in sessions.items()
    }
    if any(row["visitor_id"] != expected_visitors[row["session_key"]] for row in session_rows):
        raise WebTrackingConflictError("session_visitor_mismatch")
    candidate_event_ids = list({event["event_id"] for event in events})
    cursor.execute(
        """SELECT event_id FROM web_events
           WHERE tracker_id = %s AND event_id = ANY(%s)""",
        (tracker_uuid, candidate_event_ids),
    )
    existing_event_ids = {row["event_id"] for row in cursor.fetchall()}
    cursor.execute(
        """SELECT session_id, COUNT(*) AS event_count FROM web_events
           WHERE session_id = ANY(%s::uuid[]) GROUP BY session_id""",
        (list(session_ids.values()),),
    )
    existing_counts = {row["session_id"]: int(row["event_count"]) for row in cursor.fetchall()}
    batch_counts = {}
    counted_event_ids = set()
    for event in events:
        if event["event_id"] in existing_event_ids or event["event_id"] in counted_event_ids:
            continue
        counted_event_ids.add(event["event_id"])
        session_uuid = session_ids[event["session_key"]]
        batch_counts[session_uuid] = batch_counts.get(session_uuid, 0) + 1
    if any(existing_counts.get(key, 0) + count > MAX_EVENTS_PER_SESSION for key, count in batch_counts.items()):
        raise WebTrackingLimitError("session_event_limit_exceeded")
    event_values = [
        (
            business_id, tracker_uuid, session_ids[event["session_key"]], event["event_id"],
            event["event_type"], event["tracker_version"], event["schema_version"], event["hostname"],
            event["path"], json.dumps(event["metadata"], ensure_ascii=False), event["action_type"],
            event["action_provider"], event["action_domain"], event["occurred_at"],
        )
        for event in events
    ]
    inserted_rows = execute_values(
        cursor,
        """INSERT INTO web_events (
               business_id, tracker_id, session_id, event_id, event_type, tracker_version,
               schema_version, page_hostname, page_path, metadata_json, action_type,
               action_provider, action_domain, occurred_at
           ) VALUES %s
           ON CONFLICT (tracker_id, event_id) DO NOTHING
           RETURNING event_id""",
        event_values,
        template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
        fetch=True,
    )
    accepted = len(inserted_rows)
    latest = max(event["occurred_at"] for event in events)
    first = min(event["occurred_at"] for event in events)
    cursor.execute(
        """UPDATE business_web_trackers
           SET first_event_at = LEAST(COALESCE(first_event_at, %s), %s),
               last_event_at = GREATEST(COALESCE(last_event_at, %s), %s),
               last_tracker_version = %s,
               last_schema_version = %s
           WHERE id = %s""",
        (first, first, latest, latest, events[0]["tracker_version"], events[0]["schema_version"], tracker_uuid),
    )
    return {"accepted": accepted, "duplicates": len(events) - accepted}


def _row_list(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def get_business_web_metrics(cursor, business_id: str, period_days: int = 30) -> dict:
    period_days = period_days if period_days in {7, 30, 90} else 30
    cursor.execute(
        """
        WITH bounds AS (
            SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1) AS current_start,
                   (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int * 2 - 1) AS previous_start
        )
        SELECT
            COUNT(DISTINCT visitor_id) FILTER (WHERE started_at >= current_start::timestamp AT TIME ZONE 'UTC') AS visitors,
            COUNT(*) FILTER (WHERE started_at >= current_start::timestamp AT TIME ZONE 'UTC') AS sessions,
            COUNT(DISTINCT visitor_id) FILTER (WHERE started_at >= previous_start::timestamp AT TIME ZONE 'UTC' AND started_at < current_start::timestamp AT TIME ZONE 'UTC') AS previous_visitors,
            COUNT(*) FILTER (WHERE started_at >= previous_start::timestamp AT TIME ZONE 'UTC' AND started_at < current_start::timestamp AT TIME ZONE 'UTC') AS previous_sessions
        FROM web_sessions, bounds
        WHERE business_id = %s AND started_at >= previous_start::timestamp AT TIME ZONE 'UTC'
        """,
        (period_days, period_days, business_id),
    )
    totals = dict(cursor.fetchone())
    cursor.execute(
        """
        WITH bounds AS (
            SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1) AS current_start,
                   (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int * 2 - 1) AS previous_start,
                   (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date + 1 AS tomorrow
        ), aggregate_counts AS (
            SELECT
                COALESCE(SUM(page_views) FILTER (WHERE metric_date >= current_start), 0) AS page_views,
                COALESCE(SUM(target_actions) FILTER (WHERE metric_date >= current_start), 0) AS conversions,
                COALESCE(SUM(page_views) FILTER (WHERE metric_date >= previous_start AND metric_date < current_start), 0) AS previous_page_views,
                COALESCE(SUM(target_actions) FILTER (WHERE metric_date >= previous_start AND metric_date < current_start), 0) AS previous_conversions
            FROM web_daily_metrics, bounds
            WHERE business_id = %s AND dimension_type = 'total'
              AND metric_date >= previous_start AND metric_date < tomorrow
        ), raw_counts AS (
            SELECT
                COUNT(*) FILTER (WHERE e.event_type = 'page_view' AND (e.occurred_at AT TIME ZONE 'UTC')::date >= current_start) AS page_views,
                COUNT(*) FILTER (
                    WHERE e.action_type IS NOT NULL
                      AND NOT (
                          e.action_type = 'outbound'
                          AND CASE WHEN e.action_domain LIKE 'www.%%' THEN substring(e.action_domain FROM 5) ELSE e.action_domain END
                              = CASE WHEN e.page_hostname LIKE 'www.%%' THEN substring(e.page_hostname FROM 5) ELSE e.page_hostname END
                      )
                      AND (e.occurred_at AT TIME ZONE 'UTC')::date >= current_start
                ) AS conversions,
                COUNT(*) FILTER (WHERE e.event_type = 'page_view' AND (e.occurred_at AT TIME ZONE 'UTC')::date < current_start) AS previous_page_views,
                COUNT(*) FILTER (
                    WHERE e.action_type IS NOT NULL
                      AND NOT (
                          e.action_type = 'outbound'
                          AND CASE WHEN e.action_domain LIKE 'www.%%' THEN substring(e.action_domain FROM 5) ELSE e.action_domain END
                              = CASE WHEN e.page_hostname LIKE 'www.%%' THEN substring(e.page_hostname FROM 5) ELSE e.page_hostname END
                      )
                      AND (e.occurred_at AT TIME ZONE 'UTC')::date < current_start
                ) AS previous_conversions
            FROM web_events e, bounds
            WHERE e.business_id = %s
              AND (e.occurred_at AT TIME ZONE 'UTC')::date >= previous_start
              AND (e.occurred_at AT TIME ZONE 'UTC')::date < tomorrow
              AND NOT EXISTS (
                  SELECT 1 FROM web_daily_metrics m
                  WHERE m.tracker_id = e.tracker_id
                    AND m.metric_date = (e.occurred_at AT TIME ZONE 'UTC')::date
                    AND m.dimension_type = 'total'
              )
        )
        SELECT a.page_views + r.page_views AS page_views,
               a.conversions + r.conversions AS conversions,
               a.previous_page_views + r.previous_page_views AS previous_page_views,
               a.previous_conversions + r.previous_conversions AS previous_conversions
        FROM aggregate_counts a CROSS JOIN raw_counts r
        """,
        (period_days, period_days, business_id, business_id),
    )
    totals.update(dict(cursor.fetchone()))
    cursor.execute(
        """
        WITH page_events AS (
            SELECT e.session_id, s.visitor_id,
                   CASE WHEN e.page_hostname LIKE 'www.%%' THEN substring(e.page_hostname FROM 5) ELSE e.page_hostname END AS page_hostname,
                   e.page_path, e.metadata_json, e.occurred_at,
                   e.id
            FROM web_events e
            JOIN web_sessions s ON s.id = e.session_id
            WHERE e.business_id = %s AND e.event_type = 'page_view'
              AND e.occurred_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
        ), conversions AS (
            SELECT CASE WHEN page_hostname LIKE 'www.%%' THEN substring(page_hostname FROM 5) ELSE page_hostname END AS page_hostname,
                   page_path, COUNT(*) AS count
            FROM web_events
            WHERE business_id = %s AND action_type IS NOT NULL
              AND NOT (
                  action_type = 'outbound'
                  AND CASE WHEN action_domain LIKE 'www.%%' THEN substring(action_domain FROM 5) ELSE action_domain END
                      = CASE WHEN page_hostname LIKE 'www.%%' THEN substring(page_hostname FROM 5) ELSE page_hostname END
              )
              AND occurred_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
            GROUP BY 1, page_path
        ), engagement AS (
            SELECT CASE WHEN page_hostname LIKE 'www.%%' THEN substring(page_hostname FROM 5) ELSE page_hostname END AS page_hostname,
                   page_path,
                   SUM(COALESCE((metadata_json->>'engagement_ms')::int, 0)) AS engagement_ms
            FROM web_events
            WHERE business_id = %s AND event_type IN ('heartbeat', 'page_leave')
              AND occurred_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
            GROUP BY 1, page_path
        )
        SELECT p.page_hostname AS hostname, p.page_path AS path,
               MAX(NULLIF(p.metadata_json->>'title', '')) AS title,
               COUNT(*) AS views,
               COUNT(DISTINCT p.visitor_id) AS visitors,
               COALESCE(MAX(c.count), 0) AS conversions,
               ROUND(COALESCE(MAX(g.engagement_ms), 0)::numeric / GREATEST(COUNT(*), 1) / 1000)::int AS average_engagement_seconds
        FROM page_events p
        LEFT JOIN conversions c ON c.page_hostname = p.page_hostname AND c.page_path = p.page_path
        LEFT JOIN engagement g ON g.page_hostname = p.page_hostname AND g.page_path = p.page_path
        GROUP BY p.page_hostname, p.page_path
        ORDER BY views DESC
        LIMIT 10
        """,
        (business_id, period_days, business_id, period_days, business_id, period_days),
    )
    top_pages = _row_list(cursor)
    cursor.execute(
        """
        SELECT source_label AS source, source_type, source_domain,
               COUNT(*) AS sessions
        FROM web_sessions
        WHERE business_id = %s
          AND started_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
        GROUP BY source_label, source_type, source_domain
        ORDER BY sessions DESC LIMIT 10
        """,
        (business_id, period_days),
    )
    sources = _row_list(cursor)
    cursor.execute(
        """
        WITH bounds AS (
            SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1) AS start_date,
                   (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date + 1 AS tomorrow
        ), combined AS (
            SELECT split_part(dimension_key, '|', 1) AS action_type,
                   NULLIF(split_part(dimension_key, '|', 2), '') AS provider,
                   NULLIF(split_part(dimension_key, '|', 3), '') AS domain,
                   SUM(target_actions) AS count
            FROM web_daily_metrics, bounds
            WHERE business_id = %s AND dimension_type = 'action'
              AND metric_date >= start_date AND metric_date < tomorrow
            GROUP BY dimension_key
            UNION ALL
            SELECT e.action_type, e.action_provider, e.action_domain, COUNT(*) AS count
            FROM web_events e, bounds
            WHERE e.business_id = %s AND e.action_type IS NOT NULL
              AND NOT (
                  e.action_type = 'outbound'
                  AND CASE WHEN e.action_domain LIKE 'www.%%' THEN substring(e.action_domain FROM 5) ELSE e.action_domain END
                      = CASE WHEN e.page_hostname LIKE 'www.%%' THEN substring(e.page_hostname FROM 5) ELSE e.page_hostname END
              )
              AND (e.occurred_at AT TIME ZONE 'UTC')::date >= start_date
              AND (e.occurred_at AT TIME ZONE 'UTC')::date < tomorrow
              AND NOT EXISTS (
                  SELECT 1 FROM web_daily_metrics m
                  WHERE m.tracker_id = e.tracker_id
                    AND m.metric_date = (e.occurred_at AT TIME ZONE 'UTC')::date
                    AND m.dimension_type = 'total'
              )
            GROUP BY e.action_type, e.action_provider, e.action_domain
        )
        SELECT
            CASE action_type
                WHEN 'form' THEN 'Форма отправлена'
                WHEN 'phone' THEN 'Клик по телефону'
                WHEN 'email' THEN 'Клик по Email'
                WHEN 'whatsapp' THEN 'Переход в WhatsApp'
                WHEN 'telegram' THEN 'Переход в Telegram'
                WHEN 'booking' THEN 'Переход к записи'
                ELSE 'Внешний переход'
            END AS action,
            action_type, provider, domain, SUM(count) AS count
        FROM combined
        GROUP BY action_type, provider, domain ORDER BY count DESC
        """,
        (period_days, business_id, business_id),
    )
    conversions = _row_list(cursor)
    cursor.execute(
        """
        WITH ordered AS (
            SELECT session_id,
                   (CASE WHEN page_hostname LIKE 'www.%%' THEN substring(page_hostname FROM 5) ELSE page_hostname END) || page_path AS page_label,
                   occurred_at, id,
                   ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY occurred_at, id) AS position
            FROM web_events
            WHERE business_id = %s AND event_type = 'page_view'
              AND occurred_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
        ), paths AS (
            SELECT session_id, STRING_AGG(page_label, ' → ' ORDER BY position) AS path
            FROM ordered WHERE position <= 5 GROUP BY session_id
        )
        SELECT path, COUNT(*) AS sessions FROM paths
        GROUP BY path ORDER BY sessions DESC LIMIT 8
        """,
        (business_id, period_days),
    )
    top_paths = _row_list(cursor)
    cursor.execute(
        """
        WITH section_views AS (
            SELECT e.session_id, s.visitor_id, e.page_path,
                   CASE WHEN e.page_hostname LIKE 'www.%%' THEN substring(e.page_hostname FROM 5) ELSE e.page_hostname END AS page_hostname,
                   e.metadata_json->'section'->>'key' AS section_key,
                   MAX(e.metadata_json->'section'->>'label') AS section_label,
                   MAX(COALESCE((e.metadata_json->'section'->>'position')::int, 0)) AS position,
                   MIN(e.occurred_at) AS first_viewed_at
            FROM web_events e
            JOIN web_sessions s ON s.id = e.session_id
            WHERE e.business_id = %s AND e.event_type = 'section_view'
              AND e.occurred_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
              AND COALESCE(e.metadata_json->'section'->>'key', '') <> ''
            GROUP BY e.session_id, s.visitor_id, e.page_hostname, e.page_path, e.metadata_json->'section'->>'key'
        ), section_engagement AS (
            SELECT e.session_id,
                   CASE WHEN e.page_hostname LIKE 'www.%%' THEN substring(e.page_hostname FROM 5) ELSE e.page_hostname END AS page_hostname,
                   e.page_path, e.metadata_json->'section'->>'key' AS section_key,
                   SUM(COALESCE((e.metadata_json->>'engagement_ms')::int, 0)) AS engagement_ms
            FROM web_events e
            WHERE e.business_id = %s AND e.event_type = 'section_engagement'
              AND e.occurred_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
            GROUP BY e.session_id, e.page_hostname, e.page_path, e.metadata_json->'section'->>'key'
        ), last_sections AS (
            SELECT session_id, page_hostname, page_path, section_key,
                   ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY first_viewed_at DESC, position DESC) AS rank
            FROM section_views
        ), period_sessions AS (
            SELECT COUNT(*) AS count FROM web_sessions
            WHERE business_id = %s
              AND started_at >= (((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - (%s::int - 1))::timestamp AT TIME ZONE 'UTC')
        )
        SELECT v.page_hostname AS hostname, v.page_path AS path, v.section_key AS key,
               MAX(v.section_label) AS label, MAX(v.position) AS position,
               COUNT(*) AS views, COUNT(DISTINCT v.visitor_id) AS visitors,
               COUNT(DISTINCT v.session_id) AS sessions,
               ROUND(COUNT(DISTINCT v.session_id)::numeric * 100 / GREATEST(MAX(ps.count), 1))::int AS reach_percent,
               ROUND(COALESCE(SUM(g.engagement_ms), 0)::numeric / GREATEST(COUNT(DISTINCT v.session_id), 1) / 1000)::int AS average_engagement_seconds,
               COUNT(DISTINCT v.session_id) FILTER (WHERE last.rank = 1) AS exits
        FROM section_views v
        CROSS JOIN period_sessions ps
        LEFT JOIN section_engagement g ON g.session_id = v.session_id
             AND g.page_hostname = v.page_hostname AND g.page_path = v.page_path AND g.section_key = v.section_key
        LEFT JOIN last_sections last ON last.session_id = v.session_id
             AND last.page_hostname = v.page_hostname AND last.page_path = v.page_path
             AND last.section_key = v.section_key AND last.rank = 1
        GROUP BY v.page_hostname, v.page_path, v.section_key
        ORDER BY MAX(v.position), views DESC
        LIMIT 100
        """,
        (business_id, period_days, business_id, period_days, business_id, period_days),
    )
    sections = _row_list(cursor)
    return {
        "period_days": period_days,
        "totals": totals,
        "top_pages": top_pages,
        "traffic_sources": sources,
        "conversions": conversions,
        "top_paths": top_paths,
        "sections": sections,
        "funnel": {
            "sessions": int(totals.get("sessions") or 0),
            "service_page_views": None,
            "price_page_views": None,
            "target_actions": int(totals.get("conversions") or 0),
            "requires_page_groups": True,
        },
    }


def get_web_tracking_health(cursor) -> dict:
    cursor.execute(
        """
        SELECT COUNT(*) AS trackers,
               COUNT(*) FILTER (WHERE enabled AND tracking_enabled) AS active_trackers,
               COUNT(*) FILTER (WHERE last_event_at >= NOW() - INTERVAL '24 hours') AS active_last_24h,
               COUNT(*) FILTER (WHERE last_event_at IS NULL) AS never_seen,
               MAX(last_event_at) AS last_event_at
        FROM business_web_trackers
        """
    )
    trackers = dict(cursor.fetchone() or {})
    cursor.execute(
        """
        SELECT COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour') AS events_1h,
               COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') AS events_24h,
               COUNT(DISTINCT tracker_id) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') AS trackers_24h,
               MAX(created_at) AS latest_ingested_at
        FROM web_events
        """
    )
    events = dict(cursor.fetchone() or {})
    cursor.execute(
        """
        SELECT tracker_version, schema_version, COUNT(*) AS events
        FROM web_events
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY tracker_version, schema_version
        ORDER BY events DESC
        """
    )
    versions = _row_list(cursor)
    cursor.execute(
        """
        SELECT pg_total_relation_size('web_events') AS events_total_bytes,
               pg_relation_size('web_events') AS events_table_bytes,
               pg_indexes_size('web_events') AS events_indexes_bytes,
               pg_total_relation_size('web_daily_metrics') AS metrics_total_bytes
        """
    )
    storage = dict(cursor.fetchone() or {})
    cursor.execute(
        """
        WITH activity AS (
            SELECT tracker_id,
                   COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour') AS events_1h,
                   COUNT(*) AS events_24h
            FROM web_events
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY tracker_id
        )
        SELECT t.public_tracker_id, t.business_id, b.name AS business_name,
               t.allowed_domains, t.enabled, t.tracking_enabled,
               t.first_event_at, t.last_event_at, t.last_tracker_version,
               t.last_schema_version, t.last_error_code, t.last_error_at,
               COALESCE(a.events_1h, 0) AS events_1h,
               COALESCE(a.events_24h, 0) AS events_24h
        FROM business_web_trackers t
        JOIN businesses b ON b.id = t.business_id
        LEFT JOIN activity a ON a.tracker_id = t.id
        ORDER BY t.last_event_at DESC NULLS LAST, t.created_at DESC
        LIMIT 200
        """
    )
    tracker_diagnostics = _row_list(cursor)
    cursor.execute(
        """SELECT started_at, finished_at, dry_run, status, aggregate_date,
                  metrics_rows, raw_events, aggregate_events, eligible_events,
                  eligible_metrics, deleted_events, deleted_metrics,
                  deleted_sessions, deleted_visitors, error_code
           FROM web_tracking_maintenance_runs
           ORDER BY started_at DESC LIMIT 20"""
    )
    return {
        "trackers": trackers,
        "events": events,
        "versions": versions,
        "storage": storage,
        "tracker_diagnostics": tracker_diagnostics,
        "maintenance": _row_list(cursor),
    }
