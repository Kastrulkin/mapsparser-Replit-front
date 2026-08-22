from datetime import datetime, timezone
from pathlib import Path

from flask import Flask
import pytest

from api import web_tracking_api
from services.web_tracking_service import (
    WebTrackingDeletionError,
    classify_traffic_source,
    delete_business_web_analytics,
    get_business_web_metrics,
    validate_batch,
    validate_tracker_domains,
)


NOW = datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc)


def _event(event_type="page_view", extra=None):
    event = {
        "visitor_id": "v_0123456789abcdef01234567",
        "session_id": "s_0123456789abcdef01234567",
        "event": event_type,
        "timestamp": NOW.isoformat(),
        "page": {"hostname": "example.com", "path": "/services", "title": "Services"},
        "referrer": "https://google.com/",
        "utm": {"source": "google"},
    }
    event.update(extra or {})
    return event


def test_validates_batch_and_public_tracker_resolution_shape():
    tracker_id, events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [_event()]},
        NOW,
    )
    assert error is None
    assert tracker_id == "pub_public-not-secret"
    assert events[0]["event_type"] == "page_view"
    assert events[0]["path"] == "/services"
    assert events[0]["event_id"].startswith("e_")


def test_schema_v2_requires_client_event_id_and_records_versions():
    event = _event(extra={"event_id": "e_0123456789abcdef01234567"})
    tracker_id, events, error = validate_batch(
        {
            "tracker_id": "pub_public-not-secret",
            "tracker_version": "1.1.0",
            "schema_version": 2,
            "events": [event],
        },
        NOW,
    )
    assert error is None
    assert tracker_id == "pub_public-not-secret"
    assert events[0]["event_id"] == "e_0123456789abcdef01234567"
    assert events[0]["tracker_version"] == "1.1.0"
    assert events[0]["schema_version"] == 2


def test_schema_v2_rejects_missing_event_id():
    _tracker_id, _events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "schema_version": 2, "events": [_event()]},
        NOW,
    )
    assert error == "invalid_event_id"


def test_schema_version_rejects_boolean_alias_for_integer():
    _tracker_id, _events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "schema_version": True, "events": [_event()]},
        NOW,
    )
    assert error == "unsupported_schema_version"


def test_hostname_allowlist_is_exact_and_multi_domain():
    _tracker_id, events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [_event()]},
        NOW,
    )
    assert error is None
    assert validate_tracker_domains(events, ["example.com", "www.example.com"]) is None
    assert validate_tracker_domains(events, ["other.example"]) == "hostname_not_allowed"
    assert validate_tracker_domains(events, []) == "tracker_domains_not_configured"


def test_rejects_malformed_event_payload():
    _tracker_id, _events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [{"event": "page_view"}]},
        NOW,
    )
    assert error == "invalid_anonymous_identifiers"


def test_rejects_oversized_batch_and_timestamp_outside_acceptance_window():
    oversized = [_event() for _index in range(26)]
    _tracker_id, _events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": oversized},
        NOW,
    )
    assert error == "invalid_batch_size"

    stale = _event(extra={"timestamp": "2026-08-01T09:00:00+00:00"})
    _tracker_id, _events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [stale]},
        NOW,
    )
    assert error == "invalid_timestamp"


def test_form_events_never_keep_field_values_or_personal_contact_targets():
    raw = _event(
        "form_submit",
        {
            "form": {
                "id": "lead-form",
                "name": "lead",
                "action": "https://example.com/private-submit?email=person@example.com",
                "values": {"phone": "+79990000000", "comment": "private"},
            },
            "value": "person@example.com",
        },
    )
    _tracker_id, events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [raw]},
        NOW,
    )
    assert error is None
    assert events[0]["metadata"]["form"] == {
        "id": "lead-form",
        "name": "lead",
        "action": "https://example.com/private-submit",
        "section_key": "",
    }
    assert "values" not in events[0]["metadata"]["form"]
    assert "person@example.com" not in str(events[0]["metadata"])


def test_referrer_keeps_attribution_without_query_or_path_details():
    raw = _event(extra={
        "referrer": "https://person:secret@google.com/search?q=private+request",
        "device_type": "forged-device",
        "page": {"hostname": "example.com", "path": "/services?email=private@example.com#secret"},
    })
    _tracker_id, events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [raw]},
        NOW,
    )
    assert error is None
    assert events[0]["metadata"]["referrer"] == "https://google.com"
    assert "secret" not in str(events[0]["metadata"])
    assert events[0]["path"] == "/services"
    assert events[0]["metadata"]["device_type"] == "unknown"


@pytest.mark.parametrize(
    ("utm_source", "referrer", "source_type", "label"),
    [
        ("campaign", "https://google.com/search?q=x", "utm", "campaign"),
        ("", "https://google.com/search?q=x", "search", "Google"),
        ("", "https://yandex.ru/search/?text=x", "search", "Яндекс"),
        ("", "https://vk.com/local-business", "social", "vk.com"),
        ("", "https://t.me/local_business", "social", "t.me"),
        ("", "https://2gis.ru/moscow", "maps", "maps"),
        ("yandex_maps", "", "maps", "yandex_maps"),
        ("", "", "direct", "direct"),
        ("", "https://partner.example/article", "referral", "partner.example"),
        ("", "not-a-url", "unknown", "unknown"),
    ],
)
def test_first_session_source_attribution(utm_source, referrer, source_type, label):
    result = classify_traffic_source(utm_source, referrer)

    assert result["type"] == source_type
    assert result["label"] == label


@pytest.mark.parametrize(
    ("event_type", "href", "action_type", "provider"),
    [
        ("form_submit", "", "form", None),
        ("outbound_click", "tel:+79990000000", "phone", None),
        ("outbound_click", "mailto:person@example.com", "email", None),
        ("outbound_click", "https://wa.me/79990000000", "whatsapp", "whatsapp"),
        ("outbound_click", "https://t.me/business", "telegram", "telegram"),
        ("outbound_click", "https://yclients.com/company/1", "booking", "yclients"),
        ("outbound_click", "https://www.example.com/prices", None, None),
        ("outbound_click", "https://partner.example/path", "outbound", "partner.example"),
    ],
)
def test_target_action_has_canonical_classification(event_type, href, action_type, provider):
    extra = {"element": {"href": href}} if href else {"form": {"id": "lead-form"}}
    _tracker_id, events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [_event(event_type, extra)]},
        NOW,
    )

    assert error is None
    assert events[0]["action_type"] == action_type
    assert events[0]["action_provider"] == provider


def test_foreground_engagement_is_bounded_and_requires_explicit_duration():
    _tracker_id, events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [_event("heartbeat", {"engagement_ms": 30000})]},
        NOW,
    )
    assert error is None
    assert events[0]["metadata"]["engagement_ms"] == 30000

    _tracker_id, _events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [_event("heartbeat", {"engagement_ms": 30001})]},
        NOW,
    )
    assert error == "invalid_engagement"


def test_section_events_keep_only_bounded_non_personal_metadata():
    raw = _event(
        "section_engagement",
        {
            "engagement_ms": 45000,
            "section": {
                "key": "services",
                "label": "Услуги",
                "position": 2,
                "form_value": "person@example.com",
            },
        },
    )
    _tracker_id, events, error = validate_batch(
        {"tracker_id": "pub_public-not-secret", "events": [raw]},
        NOW,
    )

    assert error is None
    assert events[0]["metadata"]["section"] == {"key": "services", "label": "Услуги", "position": 2}
    assert events[0]["metadata"]["engagement_ms"] == 45000
    assert "person@example.com" not in str(events[0]["metadata"])


class _Cursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.current = None
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))
        self.current = self.rows.pop(0) if self.rows else None

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current or []


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _Database:
    cursor = _Cursor()

    def __init__(self):
        self.conn = _Connection(self.cursor)

    def close(self):
        return None


def _app():
    app = Flask(__name__)
    app.register_blueprint(web_tracking_api.web_tracking_bp)
    return app


@pytest.fixture(autouse=True)
def _enable_web_tracking(monkeypatch):
    monkeypatch.setenv("WEB_TRACKING_ENABLED", "true")
    monkeypatch.setenv("WEB_TRACKING_CREATE_ENABLED", "true")
    monkeypatch.setenv("WEB_TRACKING_INGEST_ENABLED", "true")
    monkeypatch.setenv("WEB_TRACKING_ANALYTICS_ENABLED", "true")
    monkeypatch.delenv("WEB_TRACKING_BUSINESS_IDS", raising=False)
    web_tracking_api._rate_windows.clear()


def test_public_ingestion_resolves_tracker_and_accepts_batch(monkeypatch):
    _Database.cursor = _Cursor([{"id": "tracker-1", "business_id": "business-1", "public_tracker_id": "pub_public-not-secret", "allowed_domains": ["example.com"]}])
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "validate_batch", lambda _payload: ("pub_public-not-secret", [{"event_type": "page_view", "hostname": "example.com"}], None))
    captured = {}
    monkeypatch.setattr(web_tracking_api, "ingest_events", lambda _cursor, tracker, events: captured.update({"tracker": tracker, "events": events}) or {"accepted": 1, "duplicates": 0})
    monkeypatch.setattr(web_tracking_api, "record_ingestion_metrics", lambda **values: captured.update({"metrics": values}))

    response = _app().test_client().post(
        "/api/tracking/events",
        json={"tracker_id": "pub_public-not-secret", "business_id": "business-attacker", "events": [_event()]},
        headers={"Origin": "https://client.example"},
    )

    assert response.status_code == 202
    assert response.get_json()["accepted"] == 1
    assert response.get_json()["duplicates"] == 0
    assert captured["tracker"]["business_id"] == "business-1"
    assert captured["metrics"]["status"] == 202
    assert captured["metrics"]["accepted"] == 1
    assert response.headers["Access-Control-Allow-Origin"] == "https://client.example"
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_public_ingestion_rejects_oversized_body_before_database_access(monkeypatch):
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", lambda: pytest.fail("database must not be opened"))

    response = _app().test_client().post(
        "/api/tracking/events",
        data=b"x" * (64 * 1024 + 1),
        content_type="text/plain",
    )

    assert response.status_code == 413
    assert response.get_json()["error"] == "payload_too_large"


@pytest.mark.parametrize("disabled_switch", ["WEB_TRACKING_ENABLED", "WEB_TRACKING_INGEST_ENABLED"])
def test_ingestion_rollback_switches_stop_before_database_access(monkeypatch, disabled_switch):
    monkeypatch.setenv(disabled_switch, "false")
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", lambda: pytest.fail("database must not be opened"))

    response = _app().test_client().post(
        "/api/tracking/events",
        json={"tracker_id": "pub_public-not-secret", "events": [_event()]},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "tracking_ingestion_disabled"


def test_external_rate_limit_uses_safe_ingestion_telemetry_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(web_tracking_api, "record_ingestion_metrics", lambda **values: captured.update(values))
    app = _app()

    with app.test_request_context(
        "/api/tracking/events",
        method="POST",
        headers={"Origin": "https://client.example"},
    ):
        response, status = web_tracking_api.ingestion_rate_limited_response(web_tracking_api.time.perf_counter())

    assert status == 429
    assert response.get_json()["error"] == "rate_limited"
    assert response.headers["Access-Control-Allow-Origin"] == "https://client.example"
    assert captured["status"] == 429
    assert captured["outcome"] == "rate_limited"


def test_unknown_or_disabled_tracker_has_same_public_response(monkeypatch):
    _Database.cursor = _Cursor([None])
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)

    response = _app().test_client().post(
        "/api/tracking/events",
        json={"tracker_id": "pub_public-not-secret", "events": [_event()]},
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "tracker_not_found"


def test_public_ingestion_accepts_beacon_text_payload(monkeypatch):
    _Database.cursor = _Cursor([{"id": "tracker-1", "business_id": "business-1", "public_tracker_id": "pub_public-not-secret", "allowed_domains": ["example.com"]}])
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "ingest_events", lambda _cursor, _tracker, events: {"accepted": len(events), "duplicates": 0})
    payload = (
        '{"tracker_id":"pub_public-not-secret","events":['
        '{"visitor_id":"v_0123456789abcdef01234567","session_id":"s_0123456789abcdef01234567",'
        '"event":"page_view","timestamp":"2026-08-16T09:00:00+00:00",'
        '"page":{"hostname":"example.com","path":"/"}}]}'
    )
    response = _app().test_client().post(
        "/api/tracking/events",
        data=payload,
        content_type="text/plain;charset=UTF-8",
    )

    assert response.status_code == 202
    assert response.get_json()["accepted"] == 1


def test_public_ingestion_rejects_deep_json_without_internal_error(monkeypatch):
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    nested = "[" * 1100 + "]" * 1100

    response = _app().test_client().post(
        "/api/tracking/events",
        data='{"tracker_id":"pub_public-not-secret","events":' + nested + "}",
        content_type="text/plain;charset=UTF-8",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_payload_object"


def test_private_analytics_enforces_tenant_isolation(monkeypatch):
    _Database.cursor = _Cursor()
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "require_auth_from_request", lambda: {"user_id": "user-2"})
    monkeypatch.setattr(web_tracking_api, "verify_business_access", lambda *_args: (False, "owner-1"))

    response = _app().test_client().get("/api/business/business-1/web-analytics")

    assert response.status_code == 403
    assert response.get_json()["error"] == "Нет доступа к бизнесу"


def test_analytics_api_returns_aggregation_for_allowed_business(monkeypatch):
    _Database.cursor = _Cursor()
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "require_auth_from_request", lambda: {"user_id": "owner-1"})
    monkeypatch.setattr(web_tracking_api, "verify_business_access", lambda *_args: (True, "owner-1"))
    monkeypatch.setattr(web_tracking_api, "get_business_web_metrics", lambda _cursor, business_id, period: {"business": business_id, "period_days": period})
    monkeypatch.setattr(web_tracking_api, "get_web_analytics_extensions", lambda _cursor, _business_id, _period: {"goals": []})

    response = _app().test_client().get("/api/business/business-1/web-analytics?period=7")

    assert response.status_code == 200
    assert response.get_json()["metrics"] == {"business": "business-1", "period_days": 7, "goals": []}


def test_ingestion_can_be_disabled_while_existing_analytics_remain_readable(monkeypatch):
    monkeypatch.setenv("WEB_TRACKING_INGEST_ENABLED", "false")
    _Database.cursor = _Cursor()
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "require_auth_from_request", lambda: {"user_id": "owner-1"})
    monkeypatch.setattr(web_tracking_api, "verify_business_access", lambda *_args: (True, "owner-1"))
    monkeypatch.setattr(web_tracking_api, "get_business_web_metrics", lambda *_args: {"sessions": 9})
    monkeypatch.setattr(web_tracking_api, "get_web_analytics_extensions", lambda *_args: {})

    response = _app().test_client().get("/api/business/business-1/web-analytics")

    assert response.status_code == 200
    assert response.get_json()["metrics"] == {"sessions": 9}


def test_analytics_rollback_switch_hides_reads_before_database_access(monkeypatch):
    monkeypatch.setenv("WEB_TRACKING_ANALYTICS_ENABLED", "false")
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", lambda: pytest.fail("database must not be opened"))

    response = _app().test_client().get("/api/business/business-1/web-analytics")

    assert response.status_code == 404
    assert response.get_json()["error"] == "web_analytics_unavailable"


def test_tracker_creation_switch_preserves_existing_read_path(monkeypatch):
    monkeypatch.setenv("WEB_TRACKING_CREATE_ENABLED", "false")
    _Database.cursor = _Cursor()
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "require_auth_from_request", lambda: {"user_id": "owner-1"})
    monkeypatch.setattr(web_tracking_api, "verify_business_access", lambda *_args: (True, "owner-1"))
    observed = {}

    def existing_tracker(_cursor, business_id, *, allow_create):
        observed.update({"business_id": business_id, "allow_create": allow_create})
        return {
            "id": "tracker-1",
            "business_id": business_id,
            "public_tracker_id": "pub_public-not-secret",
            "enabled": True,
            "tracking_enabled": True,
            "allowed_domains": ["example.com"],
        }

    monkeypatch.setattr(web_tracking_api, "ensure_tracker", existing_tracker)
    response = _app().test_client().get("/api/business/business-1/web-tracking")

    assert response.status_code == 200
    assert observed == {"business_id": "business-1", "allow_create": False}


def test_web_analytics_deletion_requires_explicit_irreversible_confirmation(monkeypatch):
    monkeypatch.setattr(web_tracking_api, "require_auth_from_request", lambda: {"user_id": "admin-1", "is_superadmin": True})

    response = _app().test_client().post(
        "/api/admin/business/business-1/web-tracking/delete",
        json={"dry_run": False, "confirm_business_id": "another-business", "acknowledge_irreversible": True},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "deletion_confirmation_required"


def test_superadmin_health_exposes_only_safe_operational_diagnostics(monkeypatch):
    _Database.cursor = _Cursor([
        {"trackers": 1, "active_trackers": 1, "active_last_24h": 1, "never_seen": 0, "last_event_at": NOW},
        {"events_1h": 2, "events_24h": 3, "trackers_24h": 1, "latest_ingested_at": NOW},
        [{"tracker_version": "1.1.0", "schema_version": 2, "events": 3}],
        {"events_total_bytes": 100, "events_table_bytes": 60, "events_indexes_bytes": 40, "metrics_total_bytes": 20},
        [{
            "public_tracker_id": "pub_public-not-secret",
            "business_id": "business-1",
            "business_name": "Business",
            "allowed_domains": ["example.com"],
            "last_error_code": "hostname_not_allowed",
            "events_1h": 2,
            "events_24h": 3,
        }],
        [{"status": "completed", "dry_run": True, "error_code": None}],
    ])
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "require_auth_from_request", lambda: {"user_id": "admin-1", "is_superadmin": True})
    monkeypatch.setattr(web_tracking_api, "get_ingestion_metrics", lambda: {"available": True, "p95_ms": 100, "responses_5xx": 0})

    response = _app().test_client().get("/api/admin/web-tracking/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["tracker_diagnostics"][0]["last_error_code"] == "hostname_not_allowed"
    assert payload["maintenance"][0]["status"] == "completed"
    assert payload["ingestion"]["p95_ms"] == 100
    serialized = str(payload)
    assert "metadata_json" not in serialized
    assert "visitor_id" not in serialized
    assert "session_id" not in serialized


def test_deletion_dry_run_is_audited_without_deleting_rows():
    cursor = _Cursor([None, {"trackers": 1, "active_trackers": 1, "visitors": 2, "sessions": 3, "events": 4, "metrics": 5}])

    result = delete_business_web_analytics(cursor, "business-1", "admin-1", dry_run=True)

    assert result["status"] == "reviewed"
    assert result["events"] == 4
    joined = "\n".join(query for query, _params in cursor.queries)
    assert "INSERT INTO web_tracking_deletion_audits" in joined
    assert "DELETE FROM business_web_trackers" not in joined


def test_deletion_execute_requires_recent_review_and_cascades_after_it():
    counts = {"trackers": 1, "active_trackers": 0, "visitors": 2, "sessions": 3, "events": 4, "metrics": 5}
    missing_review = _Cursor([None, counts, None])
    with pytest.raises(WebTrackingDeletionError, match="recent_dry_run_required"):
        delete_business_web_analytics(missing_review, "business-1", "admin-1", dry_run=False)

    cursor = _Cursor([None, counts, {"id": "review-1", **counts}])
    result = delete_business_web_analytics(cursor, "business-1", "admin-1", dry_run=False)

    assert result["status"] == "completed"
    joined = "\n".join(query for query, _params in cursor.queries)
    assert "DELETE FROM business_web_trackers" in joined
    assert "DELETE FROM web_sessions" in joined
    assert "DELETE FROM web_visitors" in joined


def test_sql_aggregation_returns_top_pages_sources_actions_and_paths():
    cursor = _Cursor([
        {"visitors": 4, "sessions": 5, "previous_visitors": 2, "previous_sessions": 3},
        {"page_views": 12, "conversions": 3, "previous_page_views": 8, "previous_conversions": 1},
        [{"path": "/services", "title": "Services", "views": 7, "visitors": 4, "conversions": 2, "average_engagement_seconds": 42}],
        [{"source": "Google", "sessions": 5}],
        [{"action": "Форма", "count": 2}],
        [{"path": "/ → /services", "sessions": 3}],
    ])

    result = get_business_web_metrics(cursor, "business-1", 7)

    assert result["totals"]["sessions"] == 5
    assert result["top_pages"][0]["path"] == "/services"
    assert result["traffic_sources"][0]["source"] == "Google"
    assert result["conversions"][0]["action"] == "Форма"
    assert result["top_paths"][0]["sessions"] == 3
    assert result["funnel"]["requires_page_groups"] is True


def test_tracker_supports_spa_beacon_and_never_reads_input_values():
    source = (Path(__file__).resolve().parents[1] / "frontend" / "public" / "tracker.js").read_text()
    assert 'wrapHistory("pushState")' in source
    assert 'window.addEventListener("popstate"' in source
    assert "navigator.sendBeacon" in source
    assert "if (!navigator.sendBeacon" in source
    assert 'event_id: randomId("e_")' in source
    assert "schema_version: schemaVersion" in source
    assert 'document.addEventListener("submit"' in source
    assert 'window.setInterval(function () { checkpointForeground("heartbeat"); }, 30000)' in source
    assert 'checkpointForeground("page_leave")' in source
    assert 'enqueue("cta_impression"' in source
    assert 'enqueue("cta_click"' in source
    assert 'enqueue("form_submit_attempt"' in source
    assert 'trackFormResult: function' in source
    assert 'document.addEventListener("invalid"' in source
    assert 'document.addEventListener("tildaform:aftersuccess"' in source
    assert 'window.addEventListener("tildaform:aftersuccess"' not in source
    assert 'getAttribution: function' in source
    assert ".value" not in source


def test_confirmed_conversion_endpoint_requires_key_and_is_idempotent(monkeypatch):
    _Database.cursor = _Cursor()
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    captured = {}
    monkeypatch.setattr(web_tracking_api, "resolve_conversion_tracker", lambda _cursor, token: captured.update({"token": token}) or {"id": "tracker-1", "business_id": "business-1"})
    monkeypatch.setattr(web_tracking_api, "ingest_confirmed_conversion", lambda _cursor, tracker, payload: captured.update({"tracker": tracker, "payload": payload}) or {"id": "conversion-1", "accepted": True, "duplicate": False})

    response = _app().test_client().post(
        "/api/web-tracking/conversions",
        headers={"Authorization": "Bearer locconv_secret"},
        json={"source": "yclients", "external_id": "booking-1", "event_type": "booking_confirmed"},
    )

    assert response.status_code == 202
    assert response.get_json()["accepted"] is True
    assert captured["token"] == "locconv_secret"
    assert captured["payload"]["external_id"] == "booking-1"


def test_page_group_preview_enforces_business_access(monkeypatch):
    _Database.cursor = _Cursor()
    monkeypatch.setattr(web_tracking_api, "DatabaseManager", _Database)
    monkeypatch.setattr(web_tracking_api, "require_auth_from_request", lambda: {"user_id": "user-2"})
    monkeypatch.setattr(web_tracking_api, "verify_business_access", lambda *_args: (False, "owner-1"))

    response = _app().test_client().post(
        "/api/business/business-1/web-page-groups/preview",
        json={"name": "Услуги", "group_type": "service", "match_type": "prefix", "include_patterns": ["/services"]},
    )

    assert response.status_code == 403
