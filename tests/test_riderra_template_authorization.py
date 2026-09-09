from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import psycopg2
from flask import Flask, jsonify
from psycopg2.extras import RealDictCursor

from services import riderra_template_authorization_service as riderra
from services import outreach_safety_service as safety
from services import outreach_campaign_service as campaign_service
from services.outreach_dispatch_service import bind_preflight_dispatch_item, dispatch_due_outreach_queue


class ApiConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return object()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        return None


@pytest.fixture
def riderra_api_client(monkeypatch):
    from api import outreach_campaign_api

    connection = ApiConnection()
    monkeypatch.setattr(outreach_campaign_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(
        outreach_campaign_api,
        "_authorized_sender_account",
        lambda *_args, **_kwargs: {"id": riderra.SENDER_ACCOUNT_ID},
    )
    app = Flask(__name__)
    app.register_blueprint(outreach_campaign_api.outreach_campaign_bp)
    return app.test_client(), connection, outreach_campaign_api


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


def attestation():
    return {
        "id": "receipt-1", "artifact_sha256": "a" * 64,
        "verified_at": datetime.now(timezone.utc).isoformat(), "provider": riderra.PRICEBOOK_PROVIDER,
        "rows": {"1710": ["Spain", "Malaga Airport (AGP)", "Malaga", "Standard minivan 6 pax", 6, 46, "EUR"]},
    }


def record():
    item = {
        "audience": "transfer_buyer", "lead_id": "lead-1", "workstream_id": "ws-1",
        "contact_point_id": "contact-1", "recipient": "buyer@example.test",
        "company": "Malaca Instituto", "city": "Malaga",
        "opening": "I saw that Malaca Instituto offers programmes for international students in Malaga.",
        "opening_source_url": "https://example.test/programmes",
        "opening_variant": "verified_opening_v1",
        "source_fact_fingerprint": "facts:" + "b" * 64,
        "pricebook": {
            "spreadsheet_id": riderra.PRICEBOOK_ID, "sheet": riderra.PRICEBOOK_SHEET, "row": 1710,
            "route": "Malaga Airport (AGP) to a hotel in Malaga", "vehicle": "standard minivan",
            "pax": 6, "price": "€46", "currency": "EUR", "source_row_sha256": "",
            "source_artifact_sha256": "a" * 64, "source_version": "a" * 64,
        },
    }
    item["pricebook"]["source_row_sha256"] = riderra._hash(attestation()["rows"]["1710"])
    item["content_sha256"] = riderra.render_record(item)["content_sha256"]
    return item


def manifest():
    return riderra.build_manifest([record()], pricebook_attestation=attestation())


def test_manifest_is_closed_exact_template_and_frozen_quote():
    result = manifest()
    member = result["records"][0]
    assert member["subject"] == "Malaca Instituto | Riderra | Malaga airport transfers"
    assert "€46 (standard minivan, up to 6 passengers)" in member["body"]
    assert member["pricebook"]["source_row_values"][1] == "Malaga Airport (AGP)"
    assert result["daily_limit"] == 150


def test_approved_v8_copy_anchor_and_strict_no_opening_variant():
    item = record()
    item["opening"] = "I saw that Malaca Instituto offers Spanish-language programmes for international students in Malaga."
    item["content_sha256"] = "c75446c490bdeea21d1c75994adb42803851a26f4465849282aaca30504be9fe"
    assert riderra.build_manifest([item], pricebook_attestation=attestation())["records"][0]["content_sha256"] == item["content_sha256"]
    neutral = record()
    neutral.update({"opening_variant": "no_opening_v1", "opening": "", "opening_source_url": ""})
    rendered = riderra.render_record(neutral)
    neutral["content_sha256"] = rendered["content_sha256"]
    member = riderra.build_manifest([neutral], pricebook_attestation=attestation())["records"][0]
    assert "team,\n\nI'm Alex from Riderra" in member["body"]
    assert "I saw that" not in member["body"]
    altered = deepcopy(neutral)
    altered["opening"] = "A new arbitrary paragraph that must never be admitted."
    with pytest.raises(ValueError):
        riderra.build_manifest([altered], pricebook_attestation=attestation())


@pytest.mark.parametrize("change", ["quote", "vehicle", "body", "berlin", "weak_source"])
def test_manifest_rejects_changed_copy_quote_or_scope(change):
    item = record()
    if change == "quote": item["pricebook"]["price"] = "€45"
    if change == "vehicle": item["pricebook"]["vehicle"] = "minivan"
    if change == "body": item["content_sha256"] = "c" * 64
    if change == "berlin": item["city"] = "Berlin"
    if change == "weak_source": item["opening_source_url"] = ""
    with pytest.raises(ValueError):
        riderra.build_manifest([item], pricebook_attestation=attestation())


def test_manifest_rejects_duplicate_company_or_recipient():
    duplicate = deepcopy(record())
    duplicate["lead_id"] = "lead-2"
    duplicate["workstream_id"] = "ws-2"
    duplicate["contact_point_id"] = "contact-2"
    duplicate["recipient"] = "other-buyer@example.test"
    duplicate["content_sha256"] = riderra.render_record(duplicate)["content_sha256"]
    with pytest.raises(ValueError, match="membership"):
        riderra.build_manifest([record(), duplicate], pricebook_attestation=attestation())


@pytest.mark.parametrize("change", ["business", "contact", "fingerprint", "opening"])
def test_database_binding_rechecks_business_contact_and_opening(change):
    item = riderra.build_manifest([record()], pricebook_attestation=attestation())["records"][0]
    row = {
        "workstream_type": "client_partnership", "client_business_id": riderra.BUSINESS_ID,
        "company": item["company"], "city": item["city"], "contact_type": "email",
        "verification_status": "verified", "recipient": item["recipient"],
        "signals_json": [{"fact": "grounded", "source_url": "https://source.test"}],
        "evidence_json": [], "report_hash": "", "suggested_opener": item["opening"],
        "opener_source_url": item["opening_source_url"],
    }
    item["source_fact_fingerprint"] = riderra.research_source_fact_fingerprint(row)
    if change == "business": row["client_business_id"] = "other"
    if change == "contact": row["verification_status"] = "valid_format"
    if change == "fingerprint": item["source_fact_fingerprint"] = "facts:" + "0" * 64
    if change == "opening": row["suggested_opener"] = "An arbitrary claim."
    with pytest.raises(ValueError, match="database_binding"):
        riderra.verify_database_binding(Cursor([row]), item)


def test_database_binding_requires_current_research_window():
    item = riderra.build_manifest([record()], pricebook_attestation=attestation())["records"][0]
    cursor = Cursor()
    with pytest.raises(ValueError, match="database_binding"):
        riderra.verify_database_binding(cursor, item)
    assert "researched_at >= NOW()-INTERVAL '90 days'" in cursor.calls[0][0]


def test_exact_invitation_rejects_wrong_sender_and_body():
    auth = {"sender_account_id": riderra.SENDER_ACCOUNT_ID, "manifest": manifest()}
    member = auth["manifest"]["records"][0]
    assert riderra.exact_invitation(record=member, authorization=auth, subject=member["subject"], body=member["body"],
                                    sender_account_id=riderra.SENDER_ACCOUNT_ID, channel="email", sequence_index=0)
    assert not riderra.exact_invitation(record=member, authorization=auth, subject=member["subject"], body=member["body"] + "x",
                                        sender_account_id=riderra.SENDER_ACCOUNT_ID, channel="email", sequence_index=0)
    assert not riderra.exact_invitation(record=member, authorization=auth, subject=member["subject"], body=member["body"],
                                        sender_account_id="author-sender", channel="email", sequence_index=0)


def test_revocation_succeeds_with_expired_or_damaged_previous_manifest():
    previous = {"id": "grant", "payload_json": {"grant_id": "grant", "manifest": {"damaged": True},
                "pricebook_attestation_id": "expired"}}
    sender = {"id": riderra.SENDER_ACCOUNT_ID}
    cursor = Cursor([{"id": "admin"}, sender, previous])
    result = riderra.set_authorization(cursor, actor_id="admin", enabled=False, records=[],
                                      authorization_reference=riderra.AUTHORIZATION_REFERENCE)
    assert result["state"] == "revoked"
    assert "'permission_changed'" in cursor.calls[-1][0]
    assert cursor.calls[-1][1][3].adapted["state"] == "revoked"


@pytest.mark.parametrize("count,duplicate,allowed,reason", [
    (150, False, True, "riderra_daily_slot_reserved"),
    (151, False, False, "riderra_daily_limit_reached"),
    (1, True, False, "riderra_company_already_reserved"),
])
def test_daily_cap_counts_unique_queued_reserved_sent_and_unknown(count, duplicate, allowed, reason):
    item = {"business_id": riderra.BUSINESS_ID, "workstream_type": "client_partnership", "lead_id": "lead-1",
            "lead_name": "Malaca Instituto",
            "policy_json": {"approval_mode": "riderra_template"}}
    cursor = Cursor([{"company_count": count, "duplicate_company": duplicate}])
    result = riderra.reserve_daily_company_slot(cursor, queue_id="queue-1", item=item)
    assert result["allowed"] is allowed and result["reason_code"] == reason
    sql = cursor.calls[1][0]
    assert "('queued','sending','sent','delivered')" in sql and "send_uncertain" in sql
    assert "manual_activity" in sql and "event.event_type='manual_sent'" in sql
    assert "Europe/Moscow" in cursor.calls[1][1]


def test_non_riderra_b2b_does_not_enter_scoped_cap():
    item = {"business_id": "other", "workstream_type": "client_partnership",
            "policy_json": {"approval_mode": "manual"}}
    result = riderra.reserve_daily_company_slot(Cursor(), queue_id="q", item=item)
    assert result == {"allowed": False, "reason_code": "riderra_template_scope_invalid", "item": item}


def test_manual_history_uses_immutable_event_recipient_for_reimported_lead():
    cursor = Cursor([{"found": 1}])
    assert riderra.previously_contacted_buyer(
        cursor,
        queue_id="queue-new",
        item={"lead_id": "lead-new", "lead_name": "Malaca Instituto", "normalized_value": "Buyer@Example.test"},
    )
    sql, params = cursor.calls[0]
    assert "event.payload_json->>'recipient_value'" in sql
    assert params[-2:] == ("buyer@example.test", "buyer@example.test")
    assert "manual_lead.name" in sql and "previous_lead.name" in sql


def test_dispatch_binds_only_freshly_validated_riderra_payload():
    original = {"id": "q", "approved_text": "mutable", "email": "old@example.test"}
    validated = {"id": "q", "approved_text": "exact", "email": "buyer@example.test"}
    proof = {"item": {"policy_json": {"approval_mode": "riderra_template"}},
             "validated_dispatch_payload": validated}
    assert bind_preflight_dispatch_item(original, proof)["approved_text"] == "exact"
    unchanged = bind_preflight_dispatch_item(original, {"item": {"policy_json": {"approval_mode": "manual"}}})
    assert unchanged is original


def test_dispatch_sql_keeps_noncreator_riderra_after_legacy_cap_and_is_fair(monkeypatch):
    from api import admin_prospecting

    class DispatchCursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params=()):
            self.calls.append((query, list(params)))

        def fetchone(self):
            return {"count": 10}

        def fetchall(self):
            return []

    class DispatchConnection:
        def __init__(self):
            self.cursor_instance = DispatchCursor()

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            return None

        def close(self):
            return None

    connection = DispatchConnection()
    monkeypatch.setattr(admin_prospecting, "get_db_connection", lambda: connection)
    result = dispatch_due_outreach_queue(
        batch_size=2,
        campaign_only=True,
        allowed_business_ids=["cb674174-8b3d-41a3-8277-525c849935f2", riderra.BUSINESS_ID],
        max_daily_outreach_batch=10,
    )
    sql, params = connection.cursor_instance.calls[1]
    assert result["picked"] == 0
    assert "LEFT JOIN creator_profiles author_creator" in sql
    assert "author_creator.id IS NOT NULL" in sql
    assert "author_workstream.workstream_type = 'client_partnership'" in sql
    assert "author_campaign.business_id = 'edbd961a-273f-4f15-836e-33aacc0aa0e3'" in sql
    assert "ROW_NUMBER() OVER (PARTITION BY cohort_key" in sql
    assert "candidate.cohort_rank ASC" in sql
    assert params[1:3] == ["cb674174-8b3d-41a3-8277-525c849935f2", riderra.BUSINESS_ID]


def test_revoked_grant_loads_as_inactive_without_revalidating_members():
    sender = {"id": riderra.SENDER_ACCOUNT_ID, "status": "connected", "outreach_enabled": True,
              "health_status": "healthy", "capabilities_json": {"direct_send": True, "reply_sync": True}}
    revoked = {"id": "revoke", "event_type": "permission_changed", "actor_id": "admin", "actor_authorized": True,
               "created_at": datetime.now(timezone.utc),
               "payload_json": {"permission_kind": riderra.PERMISSION_KIND, "state": "revoked"}}
    cursor = Cursor([sender, revoked])
    assert riderra.load_authorization(cursor) == {}


@pytest.mark.parametrize("revoked_after,expected", [(False, True), (True, False)])
def test_grant_lookup_preserves_queued_old_grant_across_rotation_but_honors_revoke(revoked_after, expected):
    source_attestation = attestation()
    current_manifest = riderra.build_manifest([record()], pricebook_attestation=source_attestation)
    grant_event = {"id": "old-grant", "event_type": "permission_changed",
                   "actor_id": "admin", "actor_authorized": True,
                   "created_at": datetime.now(timezone.utc),
                   "payload_json": {"permission_kind": riderra.PERMISSION_KIND,
                       "state": "active", "grant_id": "old-grant",
                       "authorization_reference": riderra.AUTHORIZATION_REFERENCE,
                       "pricebook_attestation_id": "receipt-1", "manifest": current_manifest}}
    sender = {"id": riderra.SENDER_ACCOUNT_ID, "status": "connected", "outreach_enabled": True,
              "health_status": "healthy", "capabilities_json": {"direct_send": True, "reply_sync": True}}
    receipt_event = {"id": "receipt-1", "event_type": "provider_snapshot_verified",
                     "actor_authorized": True, "created_at": datetime.now(timezone.utc),
                     "payload_json": {"snapshot_kind": riderra.PRICEBOOK_ATTESTATION_KIND,
                                      "attestation_id": "receipt-1", "evidence_reference": "provider-readback",
                                      "attestation": {key: value for key, value in source_attestation.items() if key != "id"}}}
    rows = [sender, grant_event, {"revoked": 1} if revoked_after else None]
    if not revoked_after:
        rows.append(receipt_event)
    loaded = riderra.load_authorization(Cursor(rows), authorization_id="old-grant")
    assert bool(loaded) is expected


def test_stale_price_attestation_fails_closed():
    source = attestation()
    source["verified_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    with pytest.raises(ValueError, match="verified_at"):
        riderra.build_manifest([record()], pricebook_attestation=source)


def test_pricebook_attestation_requires_exact_provider():
    artifact = {
        "spreadsheet_id": riderra.PRICEBOOK_ID,
        "sheet": riderra.PRICEBOOK_SHEET,
        "evidence_kind": "provider_observed",
        "provider": "self-asserted",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "ranges": [
            {"range": f"'{riderra.PRICEBOOK_SHEET}'!A1:G1", "values": [["Country", "From", "To", "Type", "Pax", "Price", "Currency"]]},
            {"range": f"'{riderra.PRICEBOOK_SHEET}'!A1710:G1710", "values": [attestation()["rows"]["1710"]]},
        ],
    }
    with pytest.raises(ValueError, match="attestation_invalid"):
        riderra.normalize_pricebook_attestation(artifact, "a" * 64)
    with pytest.raises(ValueError, match="attestation_invalid"):
        riderra.normalize_pricebook_attestation([], "a" * 64)


def test_pricebook_attestation_records_only_the_migrated_snapshot_event():
    artifact = {
        "spreadsheet_id": riderra.PRICEBOOK_ID,
        "sheet": riderra.PRICEBOOK_SHEET,
        "evidence_kind": "provider_observed",
        "provider": riderra.PRICEBOOK_PROVIDER,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "ranges": [
            {"range": f"'{riderra.PRICEBOOK_SHEET}'!A1:G1", "values": [["Country", "From", "To", "Type", "Pax", "Price", "Currency"]]},
            {"range": f"'{riderra.PRICEBOOK_SHEET}'!A1710:G1710", "values": [attestation()["rows"]["1710"]]},
        ],
    }
    cursor = Cursor([{"id": "admin"}, {"id": riderra.SENDER_ACCOUNT_ID}])
    result = riderra.record_pricebook_attestation(
        cursor, actor_id="admin", artifact_bytes=json.dumps(artifact).encode(),
        evidence_reference="authenticated_settings:snapshot005.json",
    )
    insert_sql = cursor.calls[-1][0]
    assert "'provider_snapshot_verified'" in insert_sql
    assert "'preflight_succeeded'" not in insert_sql
    assert result["attestation"]["provider"] == riderra.PRICEBOOK_PROVIDER


def test_pricebook_loader_rejects_transport_preflight_or_wrong_snapshot_kind():
    source = attestation()
    payload = {
        "snapshot_kind": riderra.PRICEBOOK_ATTESTATION_KIND,
        "attestation_id": "receipt-1", "evidence_reference": "provider-readback",
        "attestation": {key: value for key, value in source.items() if key != "id"},
    }
    common = {"id": "receipt-1", "actor_authorized": True, "created_at": datetime.now(timezone.utc)}
    assert riderra.load_pricebook_attestation(
        Cursor([{**common, "event_type": "preflight_succeeded", "payload_json": payload}]), "receipt-1",
    ) == {}
    assert riderra.load_pricebook_attestation(
        Cursor([{**common, "event_type": "provider_snapshot_verified",
                 "payload_json": {**payload, "snapshot_kind": "other"}}]), "receipt-1",
    ) == {}


def test_grant_loader_rejects_non_permission_event_even_with_active_payload():
    sender = {"id": riderra.SENDER_ACCOUNT_ID, "status": "connected", "outreach_enabled": True,
              "health_status": "healthy", "capabilities_json": {"direct_send": True, "reply_sync": True}}
    event = {"id": "grant", "event_type": "preflight_succeeded", "actor_id": "admin",
             "actor_authorized": True, "created_at": datetime.now(timezone.utc),
             "payload_json": {"permission_kind": riderra.PERMISSION_KIND, "state": "active"}}
    assert riderra.load_authorization(Cursor([sender, event])) == {}


def test_migration_adds_only_honest_snapshot_event_to_existing_allowlist():
    migration = importlib.import_module(
        "alembic_migrations.versions.20260909_allow_riderra_pricebook_snapshot_event"
    )
    expanded = migration.EVENT_TYPE_CHECK_WITH_PRICEBOOK_SNAPSHOT
    previous = migration.EVENT_TYPE_CHECK_BEFORE_PRICEBOOK_SNAPSHOT
    base_types = {
        "connected", "permission_changed", "preflight_succeeded", "preflight_failed",
        "reply_sync_succeeded", "reply_sync_failed", "disconnected",
    }
    assert migration.down_revision == "20260908_001"
    assert expanded.count("'provider_snapshot_verified'") == 1
    assert "'provider_snapshot_verified'" not in previous
    for event_type in base_types:
        assert f"'{event_type}'" in expanded and f"'{event_type}'" in previous


@pytest.mark.integration
def test_migrated_event_allowlist_accepts_snapshot_and_rejects_unknown(postgres_container):
    migration = importlib.import_module(
        "alembic_migrations.versions.20260909_allow_riderra_pricebook_snapshot_event"
    )
    database_url = postgres_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)
    connection = psycopg2.connect(database_url)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """CREATE TEMP TABLE outreach_sender_account_events (
                   event_type TEXT NOT NULL,
                   CONSTRAINT ck_outreach_sender_account_event_type CHECK (
                     event_type IN ('connected','permission_changed','preflight_succeeded','preflight_failed',
                                    'reply_sync_succeeded','reply_sync_failed','disconnected')
                   )
               )"""
        )
        cursor.execute("ALTER TABLE outreach_sender_account_events DROP CONSTRAINT ck_outreach_sender_account_event_type")
        cursor.execute(migration.EVENT_TYPE_CHECK_WITH_PRICEBOOK_SNAPSHOT)
        cursor.execute("ALTER TABLE outreach_sender_account_events VALIDATE CONSTRAINT ck_outreach_sender_account_event_type")
        cursor.execute(
            "INSERT INTO outreach_sender_account_events(event_type) VALUES (%s),(%s)",
            ("permission_changed", "provider_snapshot_verified"),
        )
        cursor.execute("SAVEPOINT unsupported_event")
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute(
                "INSERT INTO outreach_sender_account_events(event_type) VALUES (%s)",
                ("riderra_unknown_event",),
            )
        cursor.execute("ROLLBACK TO SAVEPOINT unsupported_event")
        cursor.execute("ALTER TABLE outreach_sender_account_events DROP CONSTRAINT ck_outreach_sender_account_event_type")
        cursor.execute(migration.EVENT_TYPE_CHECK_BEFORE_PRICEBOOK_SNAPSHOT)
        cursor.execute("SAVEPOINT downgraded_event")
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute(
                "INSERT INTO outreach_sender_account_events(event_type) VALUES (%s)",
                ("provider_snapshot_verified",),
            )
        cursor.execute("ROLLBACK TO SAVEPOINT downgraded_event")
        cursor.execute("SELECT COUNT(*) FROM outreach_sender_account_events WHERE event_type='provider_snapshot_verified'")
        assert cursor.fetchone()[0] == 1
        connection.rollback()
    finally:
        connection.close()


def test_subject_is_part_of_frozen_template_definition(monkeypatch):
    monkeypatch.setattr(riderra, "SUBJECT_TEMPLATE", "{company} | changed | {city}")
    with pytest.raises(ValueError, match="template_definition_changed"):
        riderra.build_manifest([record()], pricebook_attestation=attestation())


def test_runner_help_imports_without_database_access():
    runner = Path(__file__).parents[1] / "scripts" / "ops" / "riderra_buyer_template.py"
    result = subprocess.run(
        [sys.executable, str(runner), "--help"],
        cwd=runner.parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--records-sha256" in result.stdout


def test_protected_riderra_api_rejects_unauthenticated_and_normal_users(riderra_api_client, monkeypatch):
    client, _connection, api = riderra_api_client
    monkeypatch.setattr(api, "_require_auth", lambda: (None, (jsonify({"error": "unauthorized"}), 401)))
    url = f"/api/outreach/sender-accounts/{riderra.SENDER_ACCOUNT_ID}/riderra-template-authorization"
    assert client.get(url).status_code == 401
    monkeypatch.setattr(api, "_require_auth", lambda: ({"user_id": "ordinary", "is_superadmin": False}, None))
    assert client.get(url).status_code == 403


def test_riderra_api_rejects_wrong_sender_and_non_object_json(riderra_api_client, monkeypatch):
    client, connection, api = riderra_api_client
    monkeypatch.setattr(api, "_require_auth", lambda: ({"user_id": "admin", "is_superadmin": True}, None))
    wrong = client.patch(
        "/api/outreach/sender-accounts/not-riderra/riderra-template-authorization", json={"enabled": True},
    )
    malformed = client.patch(
        f"/api/outreach/sender-accounts/{riderra.SENDER_ACCOUNT_ID}/riderra-template-authorization",
        json=["not", "an", "object"],
    )
    malformed_attestation = client.post(
        f"/api/outreach/sender-accounts/{riderra.SENDER_ACCOUNT_ID}/riderra-pricebook-attestations",
        json=["not", "an", "object"],
    )
    assert wrong.status_code == 404
    assert malformed.status_code == 400 and malformed.get_json()["error"] == "json_object_required"
    assert malformed_attestation.status_code == 400
    assert connection.commits == 0


def test_manifest_challenge_is_non_mutating_and_uses_authenticated_actor(riderra_api_client, monkeypatch):
    client, connection, api = riderra_api_client
    monkeypatch.setattr(api, "_require_auth", lambda: ({"user_id": "authenticated-admin", "is_superadmin": True}, None))
    monkeypatch.setattr(api, "load_riderra_pricebook_attestation", lambda *_args: {"id": "receipt"})
    monkeypatch.setattr(api, "build_riderra_manifest", lambda *_args, **_kwargs: {
        "records_sha256": "a" * 64, "records": [],
    })
    calls = []
    monkeypatch.setattr(api, "set_riderra_authorization",
                        lambda *_args, **kwargs: calls.append(kwargs) or {"state": "active"})
    url = f"/api/outreach/sender-accounts/{riderra.SENDER_ACCOUNT_ID}/riderra-template-authorization"
    decision = {
        "enabled": True, "authorization_reference": riderra.AUTHORIZATION_REFERENCE,
        "pricebook_attestation_id": "receipt", "records": [], "approved_manifest_sha256": "",
    }
    challenge = client.patch(url, json=decision)
    assert challenge.status_code == 409 and calls == [] and connection.commits == 0
    decision["approved_manifest_sha256"] = "a" * 64
    granted = client.patch(url, json=decision)
    assert granted.status_code == 200
    assert calls[0]["actor_id"] == "authenticated-admin"
    assert granted.get_json()["external_dispatch_performed"] is False


def test_attestation_uses_fixed_sender_and_authenticated_actor(riderra_api_client, monkeypatch):
    client, connection, api = riderra_api_client
    monkeypatch.setattr(api, "_require_auth", lambda: ({"user_id": "authenticated-admin", "is_superadmin": True}, None))
    calls = []
    monkeypatch.setattr(api, "record_riderra_pricebook_attestation",
                        lambda *_args, **kwargs: calls.append(kwargs) or {"id": "attestation"})
    response = client.post(
        f"/api/outreach/sender-accounts/{riderra.SENDER_ACCOUNT_ID}/riderra-pricebook-attestations",
        json={"artifact_text": "{}", "evidence_reference": "authenticated_settings:snapshot005.json"},
    )
    assert response.status_code == 200 and connection.commits == 1
    assert calls == [{
        "actor_id": "authenticated-admin", "artifact_bytes": b"{}",
        "evidence_reference": "authenticated_settings:snapshot005.json",
    }]


@pytest.mark.integration
def test_daily_company_cap_sql_executes_atomically_on_isolated_postgres(postgres_container):
    database_url = postgres_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)
    connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TEMP TABLE outreachsendqueue (
              id text PRIMARY KEY, lead_id text, campaign_touch_id text, workstream_id text,
              delivery_status text, sent_at timestamptz, dispatch_started_at timestamptz,
              updated_at timestamptz, error_text text, scheduled_at timestamptz, created_at timestamptz
            );
            CREATE TEMP TABLE outreach_campaign_touches (id text PRIMARY KEY, campaign_id text);
            CREATE TEMP TABLE outreach_campaigns (id text PRIMARY KEY, business_id text, lead_id text, workstream_id text);
            CREATE TEMP TABLE lead_workstreams (id text PRIMARY KEY, client_business_id text, workstream_type text);
            CREATE TEMP TABLE prospectingleads (id text PRIMARY KEY, name text);
            CREATE TEMP TABLE outreach_campaign_events (
              campaign_id text, event_type text, payload_json jsonb, created_at timestamptz
            );
            INSERT INTO prospectingleads
              SELECT 'lead-'||n, 'Company '||n FROM generate_series(1,151) n;
            INSERT INTO lead_workstreams
              SELECT 'ws-'||n, %s, 'client_partnership' FROM generate_series(1,151) n;
            INSERT INTO outreach_campaigns
              SELECT 'campaign-'||n, %s, 'lead-'||n, 'ws-'||n FROM generate_series(1,151) n;
            INSERT INTO outreach_campaign_events
              SELECT 'campaign-'||n, 'manual_sent',
                     jsonb_build_object('evidence_kind','user_confirmed','occurred_at',NOW()::text), NOW()
              FROM generate_series(1,149) n;
            INSERT INTO outreach_campaign_touches VALUES
              ('touch-150','campaign-150'),('touch-151','campaign-151');
            INSERT INTO outreachsendqueue VALUES
              ('queue-150','lead-150','touch-150','ws-150','queued',NULL,NULL,NOW(),NULL,NOW(),NOW()),
              ('queue-151','lead-151','touch-151','ws-151','queued',NULL,NULL,NOW(),NULL,NOW()+INTERVAL '1 second',NOW()+INTERVAL '1 second');
            """,
            (riderra.BUSINESS_ID, riderra.BUSINESS_ID),
        )
        base = {"business_id": riderra.BUSINESS_ID, "workstream_type": "client_partnership",
                "policy_json": {"approval_mode": "riderra_template"}}
        first = riderra.reserve_daily_company_slot(
            cursor, queue_id="queue-150", item={**base, "lead_id": "lead-150", "lead_name": "Company 150"},
        )
        next_item = riderra.reserve_daily_company_slot(
            cursor, queue_id="queue-151", item={**base, "lead_id": "lead-151", "lead_name": "Company 151"},
        )
        assert first["allowed"] is True and first["riderra_daily_company_count"] == 150
        assert next_item["allowed"] is False and next_item["reason_code"] == "riderra_daily_limit_reached"
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.integration
def test_dispatch_claims_author_and_noncreator_riderra_on_isolated_postgres(postgres_container, monkeypatch):
    from api import admin_prospecting
    from services import outreach_dispatch_service

    database_url = postgres_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)
    raw_connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)

    class SharedConnection:
        def cursor(self):
            return raw_connection.cursor()

        def commit(self):
            return raw_connection.commit()

        def rollback(self):
            return raw_connection.rollback()

        def close(self):
            return None

    try:
        cursor = raw_connection.cursor()
        cursor.execute(
            """
            CREATE TEMP TABLE outreachsendbatches (id text PRIMARY KEY,status text);
            CREATE TEMP TABLE outreach_suppressions (lead_id text,workstream_id text,expires_at timestamptz);
            CREATE TEMP TABLE outreach_campaigns (
              id text PRIMARY KEY,status text,scope_type text,business_id text,sender_mode text,
              policy_json jsonb,workstream_id text,lead_id text,recipient_key text
            );
            CREATE TEMP TABLE outreach_campaign_touches (
              id text PRIMARY KEY,campaign_id text,status text,subject text,contact_point_id text
            );
            CREATE TEMP TABLE lead_workstreams (id text PRIMARY KEY,lead_id text,workstream_type text);
            CREATE TEMP TABLE prospectingleads (
              id text PRIMARY KEY,source_external_id text,name text,phone text,email text,
              telegram_url text,whatsapp_url text,selected_channel text
            );
            CREATE TEMP TABLE creator_profiles (id text PRIMARY KEY);
            CREATE TEMP TABLE outreachmessagedrafts (
              id text PRIMARY KEY,approved_text text,generated_text text
            );
            CREATE TEMP TABLE lead_contact_points (id text PRIMARY KEY,contact_type text,normalized_value text);
            CREATE TEMP TABLE outreachsendqueue (
              id text PRIMARY KEY,batch_id text,lead_id text,draft_id text,workstream_id text,
              campaign_touch_id text,sender_account_id text,scheduled_at timestamptz,sent_at timestamptz,
              delivery_status text,next_retry_at timestamptz,created_at timestamptz,dispatch_started_at timestamptz,
              updated_at timestamptz,attempts int,provider_message_id text,error_text text,
              idempotency_key text,channel text,recipient_value text
            );
            INSERT INTO outreachsendbatches VALUES ('batch','approved');
            INSERT INTO creator_profiles VALUES ('creator-1');
            INSERT INTO prospectingleads VALUES
              ('lead-author','creator:creator-1','Author',NULL,'author@example.test',NULL,NULL,'email'),
              ('lead-riderra',NULL,'Buyer',NULL,'buyer@example.test',NULL,NULL,'email'),
              ('lead-sent',NULL,'Legacy',NULL,'legacy@example.test',NULL,NULL,'email');
            INSERT INTO lead_workstreams VALUES
              ('ws-author','lead-author','creator_collaboration'),
              ('ws-riderra','lead-riderra','client_partnership'),
              ('ws-sent','lead-sent','client_partnership');
            INSERT INTO outreach_campaigns VALUES
              ('campaign-author','approved','business','cb674174-8b3d-41a3-8277-525c849935f2','localos_for_partner','{}','ws-author','lead-author',NULL),
              ('campaign-riderra','approved','business',%s,'partner_business','{"approval_mode":"riderra_template"}','ws-riderra','lead-riderra',NULL);
            INSERT INTO lead_contact_points VALUES
              ('contact-author','email','author@example.test'),('contact-riderra','email','buyer@example.test');
            INSERT INTO outreachmessagedrafts VALUES
              ('draft-author','author body','author body'),('draft-riderra','riderra body','riderra body');
            INSERT INTO outreach_campaign_touches VALUES
              ('touch-author','campaign-author','queued','Author subject','contact-author'),
              ('touch-riderra','campaign-riderra','queued','Riderra subject','contact-riderra');
            INSERT INTO outreachsendqueue VALUES
              ('queue-author','batch','lead-author','draft-author','ws-author','touch-author','sender-a',NOW(),NULL,'queued',NULL,NOW()-INTERVAL '2 minutes',NULL,NOW(),0,NULL,NULL,NULL,'email','author@example.test'),
              ('queue-riderra','batch','lead-riderra','draft-riderra','ws-riderra','touch-riderra','sender-r',NOW(),NULL,'queued',NULL,NOW()-INTERVAL '1 minute',NULL,NOW(),0,NULL,NULL,NULL,'email','buyer@example.test'),
              ('queue-sent','batch','lead-sent',NULL,'ws-sent',NULL,NULL,NOW(),NOW(),'sent',NULL,NOW(),NOW(),NOW(),1,NULL,NULL,NULL,'email','legacy@example.test');
            """,
            (riderra.BUSINESS_ID,),
        )
        shared = SharedConnection()
        monkeypatch.setattr(admin_prospecting, "get_db_connection", lambda: shared)
        monkeypatch.setattr(outreach_dispatch_service, "run_dispatch_preflight",
                            lambda *_args, **_kwargs: {"allowed": False, "reason_code": "test_stop", "item": {}})
        monkeypatch.setattr(outreach_dispatch_service, "persist_preflight_result", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(outreach_dispatch_service, "block_queue_item_after_preflight", lambda *_args, **_kwargs: None)
        result = dispatch_due_outreach_queue(
            batch_size=2, campaign_only=True,
            allowed_business_ids=["cb674174-8b3d-41a3-8277-525c849935f2", riderra.BUSINESS_ID],
            max_daily_outreach_batch=1,
        )
        assert result["picked"] == 2 and result["blocked"] == 2
        cursor.execute("SELECT id FROM outreachsendqueue WHERE delivery_status='sending' ORDER BY id")
        assert [row["id"] for row in cursor.fetchall()] == ["queue-author", "queue-riderra"]
        raw_connection.rollback()
    finally:
        raw_connection.close()


class PreflightCursor:
    def __init__(self, item, touch, *, source_fingerprint):
        self.item = item
        self.touch = touch
        self.source_fingerprint = source_fingerprint
        self.current_query = ""

    def execute(self, query, params=()):
        self.current_query = query

    def fetchall(self):
        if "SELECT * FROM outreach_campaign_touches" in self.current_query:
            return [self.touch]
        return []

    def fetchone(self):
        query = self.current_query
        if "SELECT q.id, q.lead_id" in query:
            return self.item
        if "SELECT evidence_json, signals_json, report_hash" in query:
            return {"fingerprint": self.source_fingerprint}
        if "SELECT COUNT(*) AS sent_count" in query:
            return {"sent_count": 0}
        return None


def riderra_preflight_fixture():
    member = manifest()["records"][0]
    grant = {
        "id": "grant-1",
        "sender_account_id": riderra.SENDER_ACCOUNT_ID,
        "manifest": {**manifest(), "records": [member]},
    }
    policy = {
        "approval_mode": "riderra_template",
        "riderra_template_authorization_id": "grant-1",
        "sender_mode": "partner_business",
        "daily_limit": riderra.DAILY_LIMIT,
    }
    item = {
        "id": "queue-1", "lead_id": member["lead_id"], "lead_name": member["company"],
        "workstream_id": member["workstream_id"], "campaign_workstream_id": member["workstream_id"],
        "campaign_touch_id": "touch-1", "touch_id": "touch-1", "queue_draft_id": "draft-1",
        "queued_draft_id": "draft-1", "queued_draft_status": "approved", "queued_draft_body": member["body"],
        "queued_draft_channel": "email", "queued_draft_contact_id": member["contact_point_id"],
        "queued_draft_lead_id": member["lead_id"], "queued_draft_workstream_id": member["workstream_id"],
        "sender_account_id": riderra.SENDER_ACCOUNT_ID, "delivery_status": "sending",
        "touch_status": "queued", "channel": "email", "contact_point_id": member["contact_point_id"],
        "sequence_index": 0, "campaign_id": "campaign-1", "campaign_status": "approved",
        "scope_type": "business", "business_id": riderra.BUSINESS_ID, "version": 1,
        "sender_profile_id": "profile-1", "approved_at": datetime.now(timezone.utc),
        "approved_snapshot_hash": "snapshot-1", "policy_json": policy,
        "sender_mode": "partner_business", "workstream_type": "client_partnership",
        "sender_scope_type": "business", "sender_channel": "email", "sender_identity": riderra.SENDER_IDENTITY,
        "sender_business_id": riderra.BUSINESS_ID, "sender_status": "connected", "health_status": "healthy",
        "sender_outreach_enabled": True, "sender_capabilities_json": {"direct_send": True, "reply_sync": True},
        "contact_type": "email", "normalized_value": member["recipient"], "contact_verification_status": "verified",
    }
    touch = {
        "id": "touch-1", "draft_id": "draft-1", "contact_point_id": member["contact_point_id"],
        "sender_account_id": riderra.SENDER_ACCOUNT_ID, "channel": "email", "sequence_index": 0,
        "subject": member["subject"], "generated_text": member["body"], "approved_text": member["body"],
        "message_brief_json": {"riderra_template_record": member,
                               "source_fact_fingerprint": member["source_fact_fingerprint"]},
        "quality_gate_json": {"passed": True},
    }
    return member, grant, item, touch


def configure_preflight_mocks(monkeypatch, grant, source_fingerprint):
    monkeypatch.setattr(safety, "load_partnership_repeat_contact_guard", lambda *_args, **_kwargs: {"blocked": False})
    monkeypatch.setattr(safety, "generation_contract_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(safety, "approval_snapshot_hash", lambda *_args, **_kwargs: "snapshot-1")
    monkeypatch.setattr(safety, "research_source_fact_fingerprint", lambda row: row.get("fingerprint", ""))
    monkeypatch.setattr(riderra, "load_authorization", lambda *_args, **_kwargs: grant)
    monkeypatch.setattr(riderra, "verify_database_binding", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(riderra, "previously_contacted_buyer", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(riderra, "reserve_daily_company_slot", lambda *_args, **_kwargs: {"allowed": True})
    from services import outreach_reply_sync_receipt
    monkeypatch.setattr(outreach_reply_sync_receipt, "load_trusted_email_reply_sync_receipt",
                        lambda *_args, **_kwargs: {"receipt_version": "trusted-v2"})


class CampaignCursor:
    def __init__(self, *, campaign=None, touch=None):
        self.campaign = campaign
        self.touch = touch
        self.current_query = ""
        self.calls = []

    def execute(self, query, params=()):
        self.current_query = query
        self.calls.append((query, params))

    def fetchone(self):
        if "SELECT campaign.*, workstream.workstream_type" in self.current_query:
            return self.campaign
        if "SELECT COALESCE(MAX(version)" in self.current_query:
            return {"next_version": 1}
        return None

    def fetchall(self):
        if "SELECT * FROM outreach_campaign_touches" in self.current_query:
            return [self.touch] if self.touch else []
        return []


def test_native_preview_persist_and_template_approval_hooks_use_same_grant(monkeypatch):
    member, grant, _item, _touch = riderra_preflight_fixture()
    grant["approved_by"] = "admin-1"
    monkeypatch.setattr(riderra, "load_authorization", lambda *_args, **_kwargs: grant)
    monkeypatch.setattr(riderra, "verify_database_binding", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(campaign_service, "_apply_sender_mode", lambda context, _mode: context)
    monkeypatch.setattr(campaign_service, "_load_context", lambda *_args, **_kwargs: {
        "lead_id": member["lead_id"], "client_business_id": riderra.BUSINESS_ID,
        "sender_profile": {"id": "profile-1"}, "source_url": "https://source.test",
    })
    monkeypatch.setattr(campaign_service, "channel_availability", lambda *_args, **_kwargs: {
        "email": {"contact_point_id": member["contact_point_id"], "recipient": member["recipient"],
                  "sender_accounts": [{"id": riderra.SENDER_ACCOUNT_ID, "status": "ready"}]},
    })
    monkeypatch.setattr(campaign_service, "_suppression_status", lambda *_args, **_kwargs: {"suppressed": False})
    monkeypatch.setattr(campaign_service, "build_evidence_ledger", lambda *_args, **_kwargs: [])
    preview_cursor = CampaignCursor()
    preview = campaign_service.build_riderra_template_preview(preview_cursor, member)
    assert preview["touches"][0]["text"] == member["body"]
    assert preview["touches"][0]["sender_account_id"] == riderra.SENDER_ACCOUNT_ID

    monkeypatch.setenv("OUTREACH_ROOM_SYNC_ENABLED", "false")
    persisted_cursor = CampaignCursor()
    saved = campaign_service.persist_preview(persisted_cursor, preview, user_id=grant["approved_by"])
    assert saved["status"] == "draft"
    policy_params = next(params for sql, params in persisted_cursor.calls if "INSERT INTO outreach_campaigns" in sql)
    assert policy_params[11].adapted["approval_mode"] == "riderra_template"
    assert policy_params[11].adapted["daily_limit"] == 150

    campaign = {
        "id": saved["id"], "status": "draft", "workstream_type": "client_partnership",
        "business_id": riderra.BUSINESS_ID, "workstream_id": member["workstream_id"],
        "lead_id": member["lead_id"], "policy_json": {"approval_mode": "riderra_template"},
    }
    touch = {
        "contact_point_id": member["contact_point_id"], "sender_account_id": riderra.SENDER_ACCOUNT_ID,
        "channel": "email", "sequence_index": 0, "subject": member["subject"],
        "generated_text": member["body"], "message_brief_json": {"riderra_template_record": member},
    }
    approved_call = {}
    monkeypatch.setattr(campaign_service, "approve_campaign",
                        lambda cursor, campaign_id, **kwargs: approved_call.update(kwargs) or {
                            "id": campaign_id, "status": "approved", "batch_id": "batch-1",
                            "approval_mode": "riderra_template",
                        })
    approved = campaign_service.approve_campaign_by_riderra_template(
        CampaignCursor(campaign=campaign, touch=touch), saved["id"],
    )
    assert approved["approval_mode"] == "riderra_template"
    assert approved_call["user_id"] is None
    assert approved_call["riderra_template_authorization"] is grant


def test_native_dispatch_preflight_returns_only_exact_validated_riderra_payload(monkeypatch):
    member, grant, item, touch = riderra_preflight_fixture()
    configure_preflight_mocks(monkeypatch, grant, member["source_fact_fingerprint"])
    result = safety.run_dispatch_preflight(
        PreflightCursor(item, touch, source_fingerprint=member["source_fact_fingerprint"]),
        "queue-1", author_reply_sync_started_at=datetime.now(timezone.utc),
    )
    assert result["allowed"] is True
    assert result["validated_dispatch_payload"]["approved_text"] == member["body"]
    assert result["validated_dispatch_payload"]["email"] == member["recipient"]


@pytest.mark.parametrize("mutation,reason", [
    ("revoked", "riderra_template_authorization_revoked_or_changed"),
    ("body", "riderra_template_copy_quote_or_contact_changed"),
    ("contact", "riderra_template_copy_quote_or_contact_changed"),
    ("draft", "riderra_template_queued_draft_changed"),
    ("source", "source_facts_changed"),
])
def test_native_dispatch_preflight_fails_closed_on_riderra_mutation(monkeypatch, mutation, reason):
    member, grant, item, touch = riderra_preflight_fixture()
    if mutation == "revoked":
        grant = {}
    elif mutation == "body":
        touch["approved_text"] += " changed"
        touch["generated_text"] = touch["approved_text"]
    elif mutation == "contact":
        touch["contact_point_id"] = "other-contact"
    elif mutation == "draft":
        item["queued_draft_body"] += " changed"
    source = "facts:" + "0" * 64 if mutation == "source" else member["source_fact_fingerprint"]
    configure_preflight_mocks(monkeypatch, grant, source)
    result = safety.run_dispatch_preflight(
        PreflightCursor(item, touch, source_fingerprint=source),
        "queue-1", author_reply_sync_started_at=datetime.now(timezone.utc),
    )
    assert result["allowed"] is False
    assert result["reason_code"] == reason


def test_legacy_policy_never_loads_riderra_grant(monkeypatch):
    _member, _grant, item, touch = riderra_preflight_fixture()
    item["policy_json"] = {"approval_mode": "manual", "sender_mode": "partner_business"}
    called = []
    monkeypatch.setattr(riderra, "load_authorization", lambda *_args, **_kwargs: called.append(True) or {})
    monkeypatch.setattr(safety, "load_partnership_repeat_contact_guard", lambda *_args, **_kwargs: {"blocked": False})
    monkeypatch.setattr(safety, "generation_contract_current", lambda *_args, **_kwargs: False)
    result = safety.run_dispatch_preflight(
        PreflightCursor(item, touch, source_fingerprint=""), "queue-1",
    )
    assert result["reason_code"] == "generation_contract_outdated"
    assert called == []
