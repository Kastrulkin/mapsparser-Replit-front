from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask

from services import riderra_systematic_outreach_service as systematic
from services import riderra_template_authorization_service as riderra


class Cursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))


def attestation():
    return {
        "id": "snapshot-1",
        "artifact_sha256": "a" * 64,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "provider": riderra.PRICEBOOK_PROVIDER,
        "rows": {
            "2": ["Finland", "Helsinki Airport (HEL)", "Helsinki", "Standard minivan 6 pax", "6", "35", "EUR"],
            "3": ["Finland", "Helsinki Airport (HEL)", "Helsinki", "Standard sedan 3 pax", "3", "39", "EUR"],
            "4": ["UK", "London Heathrow Airport (LHR)", "London", "Standard sedan 3 pax", "3", "133", "GBP"],
        },
    }


def candidate(**updates):
    row = {
        "workstream_id": "ws-1",
        "lead_id": "lead-1",
        "workstream_type": "client_partnership",
        "client_business_id": riderra.BUSINESS_ID,
        "company": "Example Travel",
        "city": "Helsinki",
        "category": "Travel agency",
        "contact_point_id": "contact-1",
        "contact_type": "email",
        "verification_status": "confirmed_source",
        "recipient": "buyer@example.test",
        "evidence_json": [{"fact": "Travel agency", "source_url": "https://example.test"}],
        "signals_json": [],
        "report_hash": "",
        "suggested_opener": "",
        "opener_source_url": "",
        "researched_at": datetime.now(timezone.utc) - timedelta(days=1),
        "has_campaign": False,
        "suppressed": False,
        "lifecycle_status": "active",
        "workstream_status": "active",
        "pipeline_status": "qualified",
        "lead_status": "active",
    }
    row.update(updates)
    return row


def test_standing_policy_fixes_sender_template_slots_pricebook_and_daily_limit():
    policy = riderra.standing_policy()
    assert policy["sender_identity"] == "riderracs@gmail.com"
    assert policy["daily_limit"] == 150
    assert policy["template_definition_sha256"] == riderra.APPROVED_TEMPLATE_DEFINITION_SHA256
    assert policy["pricebook_id"] == riderra.PRICEBOOK_ID
    assert policy["allowed_slot_names"] == [
        "company", "city", "opening", "route", "price", "vehicle", "pax",
    ]
    assert policy["excluded_cities"] == ["Berlin"]


def test_derived_batch_requires_its_standing_authorization_to_remain_active():
    current_attestation = attestation()
    record = systematic.build_candidate_record(candidate(), current_attestation)
    manifest = riderra.build_manifest([record], pricebook_attestation=current_attestation)
    sender = {
        "id": riderra.SENDER_ACCOUNT_ID,
        "status": "connected",
        "outreach_enabled": True,
        "health_status": "healthy",
        "capabilities_json": {"direct_send": True, "reply_sync": True},
    }
    exact_event = {
        "id": "batch-1",
        "event_type": "permission_changed",
        "actor_id": "admin-1",
        "actor_authorized": True,
        "created_at": datetime.now(timezone.utc),
        "payload_json": {
            "permission_kind": riderra.PERMISSION_KIND,
            "state": "active",
            "grant_id": "batch-1",
            "authorization_reference": riderra.AUTHORIZATION_REFERENCE,
            "pricebook_attestation_id": "snapshot-1",
            "standing_authorization_id": "standing-1",
            "manifest": manifest,
        },
    }
    price_event = {
        "id": "snapshot-1",
        "event_type": "provider_snapshot_verified",
        "actor_authorized": True,
        "created_at": datetime.now(timezone.utc),
        "payload_json": {
            "snapshot_kind": riderra.PRICEBOOK_ATTESTATION_KIND,
            "attestation_id": "snapshot-1",
            "evidence_reference": "test",
            "attestation": {key: value for key, value in current_attestation.items() if key != "id"},
        },
    }

    class SequenceCursor(Cursor):
        def __init__(self):
            super().__init__()
            self.rows = [sender, exact_event, None, price_event, sender, None]

        def fetchone(self):
            return self.rows.pop(0)

    assert riderra.load_authorization(SequenceCursor(), authorization_id="batch-1") == {}


def test_pricebook_route_is_exact_city_airport_and_deterministic_vehicle_priority():
    row_number, values = systematic.select_pricebook_route("Helsinki", attestation())
    assert row_number == 3
    assert values[1] == "Helsinki Airport (HEL)"
    assert systematic.select_pricebook_route("Espoo", attestation()) is None


def test_candidate_record_uses_current_005_row_and_pounds_for_uk():
    record = systematic.build_candidate_record(candidate(city="London"), attestation())
    assert record["pricebook"]["route"] == "London Heathrow Airport (LHR) to a hotel in London"
    assert record["pricebook"]["price"] == "£133"
    assert "for just £133" in record["body"]
    assert record["opening_variant"] == "no_opening_v1"


def test_classification_sends_available_remainder_and_counts_actionable_shortage_reasons():
    rows = [
        candidate(),
        candidate(workstream_id="ws-2", lead_id="lead-2", company="Berlin Buyer", city="Berlin", recipient="b@example.test"),
        candidate(workstream_id="ws-3", lead_id="lead-3", company="Espoo Buyer", city="Espoo", recipient="e@example.test"),
        candidate(workstream_id="ws-4", lead_id="lead-4", company="No Mail", recipient="", verification_status="valid_format"),
    ]
    eligible, exclusions, routes = systematic.classify_candidates(rows, attestation(), now=datetime.now(timezone.utc))
    assert len(eligible) == 1
    assert exclusions == {"confirmed_email_missing": 1, "excluded_city": 1, "route_price_missing": 1}
    assert routes == {"Espoo": 1}


def test_prepare_blocks_without_standing_authorization_and_requests_one_notice(monkeypatch):
    cursor = Cursor()
    monkeypatch.setattr(systematic, "load_standing_authorization", lambda _cursor: {})
    monkeypatch.setattr(systematic, "remaining_daily_capacity", lambda _cursor: 150)
    monkeypatch.setattr(systematic, "record_run", lambda _cursor, result: result)
    result = systematic.prepare_systematic_batch(cursor)
    assert result["status"] == "blocked"
    assert result["error_code"] == "standing_authorization_missing"
    assert result["notification_required"] is True


def test_prepare_derives_exact_grant_and_queues_every_available_candidate(monkeypatch):
    cursor = Cursor()
    standing = {"id": "standing-1", "approved_by": "admin-1"}
    record = systematic.build_candidate_record(candidate(), attestation())
    monkeypatch.setattr(systematic, "load_standing_authorization", lambda _cursor: standing)
    monkeypatch.setattr(systematic, "remaining_daily_capacity", lambda _cursor: 5)
    monkeypatch.setattr(systematic, "refresh_pricebook_attestation", lambda *_args, **_kwargs: {
        "id": "snapshot-1", "attestation": {key: value for key, value in attestation().items() if key != "id"},
    })
    monkeypatch.setattr(systematic, "load_candidate_rows", lambda _cursor: [candidate()])
    monkeypatch.setattr(systematic, "classify_candidates", lambda *_args, **_kwargs: ([record], {"route_price_missing": 4}, {"Espoo": 4}))
    grant_call = {}
    monkeypatch.setattr(systematic, "set_authorization", lambda *_args, **kwargs: grant_call.update(kwargs) or {
        "id": "batch-1", "manifest": {"records": [record]},
    })
    monkeypatch.setattr(systematic, "build_riderra_template_preview", lambda *_args, **_kwargs: {"record": record})
    monkeypatch.setattr(systematic, "persist_preview", lambda *_args, **_kwargs: {"id": "campaign-1"})
    monkeypatch.setattr(systematic, "approve_campaign_by_riderra_template", lambda *_args, **_kwargs: {"status": "approved"})
    monkeypatch.setattr(systematic, "record_run", lambda _cursor, result: result)
    result = systematic.prepare_systematic_batch(cursor, target_count=5)
    assert result["status"] == "shortage"
    assert result["queued_count"] == 1
    assert result["notification_required"] is True
    assert grant_call["standing_authorization_id"] == "standing-1"
    assert grant_call["records"] == [record]


def test_shortage_notification_contains_counts_reasons_routes_and_next_action():
    text = systematic.format_run_notification({
        "status": "shortage", "target_count": 10, "eligible_count": 6, "queued_count": 6,
        "exclusion_counts": {"confirmed_email_missing": 3}, "missing_routes": {"Espoo": 1},
    })
    assert "не хватает: 4" in text
    assert "confirmed_email_missing: 3" in text
    assert "Espoo: 1" in text
    assert "Следующее действие" in text
    assert "остаток уже поставлен в очередь" in text


def test_migration_adds_deduplicated_run_log_and_pending_notice_index():
    source = Path("alembic_migrations/versions/20260914_add_riderra_systematic_outreach_runs.py").read_text()
    assert 'down_revision = "20260909_001"' in source
    assert "UNIQUE INDEX uq_riderra_outreach_runs_fingerprint" in source
    assert "notification_required AND notified_at IS NULL" in source


def test_standing_authorization_api_records_explicit_scope_without_dispatch(monkeypatch):
    from api import outreach_campaign_api

    class Connection:
        def __init__(self):
            self.commits = 0

        def cursor(self, **_kwargs):
            return object()

        def commit(self):
            self.commits += 1

        def rollback(self):
            return None

        def close(self):
            return None

    connection = Connection()
    monkeypatch.setattr(outreach_campaign_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(outreach_campaign_api, "_require_auth", lambda: ({"is_superadmin": True, "user_id": "admin-1"}, None))
    monkeypatch.setattr(outreach_campaign_api, "_authorized_sender_account", lambda *_args, **_kwargs: {"id": riderra.SENDER_ACCOUNT_ID})
    saved = {}
    monkeypatch.setattr(
        outreach_campaign_api,
        "set_riderra_standing_authorization",
        lambda *_args, **kwargs: saved.update(kwargs) or {"id": "standing-1", "state": "active"},
    )
    app = Flask(__name__)
    app.register_blueprint(outreach_campaign_api.outreach_campaign_bp)
    response = app.test_client().patch(
        f"/api/outreach/sender-accounts/{riderra.SENDER_ACCOUNT_ID}/riderra-standing-authorization",
        json={"enabled": True, "authorization_reference": riderra.AUTHORIZATION_REFERENCE},
    )
    assert response.status_code == 200
    assert response.get_json()["external_dispatch_performed"] is False
    assert saved == {
        "actor_id": "admin-1",
        "enabled": True,
        "authorization_reference": riderra.AUTHORIZATION_REFERENCE,
    }
    assert connection.commits == 1
