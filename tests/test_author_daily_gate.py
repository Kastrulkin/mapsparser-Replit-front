from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

import services.outreach_campaign_service as campaign_service
import services.outreach_safety_service as safety_service
from services.outreach_safety_service import (
    AUTHOR_CHANNEL_DAILY_LIMITS,
    AUTHOR_DAILY_LIMIT,
    AUTHOR_POLICY_VERSION,
    is_localos_author_lane,
    reserve_localos_author_daily_slot,
)
from services.outreach_campaign_service import record_manual_touch


class GateCursor:
    def __init__(self, counts):
        self.counts = counts
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, tuple(params)))

    def fetchone(self):
        return self.counts


class ManualTouchCursor:
    def __init__(self, *rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, tuple(params)))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class DispatchFingerprintCursor:
    def __init__(self, item, touches):
        self.fetchone_rows = [item, None]
        self.fetchall_rows = [touches]
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, tuple(params)))

    def fetchone(self):
        return self.fetchone_rows.pop(0) if self.fetchone_rows else None

    def fetchall(self):
        return self.fetchall_rows.pop(0) if self.fetchall_rows else []


def author_item(*, channel="email", creator_profile_id="creator-1"):
    return {
        "workstream_type": "creator_collaboration",
        "sender_mode": "localos_for_partner",
        "creator_profile_id": creator_profile_id,
        "channel": channel,
        "sender_scope_type": "platform",
        "sender_business_id": None,
        "sender_channel": channel,
        "sender_identity": "localosgo@gmail.com",
        "policy_json": {
            "sender_mode": "localos_for_partner",
            "author_policy_version": AUTHOR_POLICY_VERSION,
            "daily_limit": AUTHOR_DAILY_LIMIT,
            "channel_daily_limits": dict(AUTHOR_CHANNEL_DAILY_LIMITS),
        },
    }


def test_author_gate_serializes_concurrent_reservations_and_uses_moscow_day():
    cursor = GateCursor({"total_count": 1, "channel_count": 1, "duplicate_author": False})

    result = reserve_localos_author_daily_slot(
        cursor,
        queue_id="queue-2",
        item=author_item(),
    )

    assert result["allowed"] is True
    assert "pg_advisory_xact_lock" in cursor.calls[0][0]
    activity_sql = cursor.calls[1][0]
    assert "AT TIME ZONE 'Europe/Moscow'" in activity_sql
    assert "(activity.occurred_at, activity.queue_id) < (current.occurred_at, %s)" in activity_sql


def test_author_gate_counts_sending_unknown_and_manual_history_but_retry_is_idempotent():
    cursor = GateCursor({"total_count": AUTHOR_DAILY_LIMIT, "channel_count": 150, "duplicate_author": False})

    result = reserve_localos_author_daily_slot(
        cursor,
        queue_id="same-queue-retry",
        item=author_item(),
    )

    assert result["allowed"] is True
    activity_sql = cursor.calls[1][0]
    assert "queue.delivery_status IN ('sending', 'sent', 'delivered')" in activity_sql
    assert "LIKE '%%send_uncertain%%'" in activity_sql
    assert "queue.delivery_status = 'sending'" in activity_sql
    assert "OR lower(COALESCE(queue.error_text, '')) LIKE '%%send_uncertain%%'" in activity_sql
    assert "activity.accounting_state = 'consumed'" in activity_sql
    assert "event.event_type IN ('manual_sent', 'manual_reply')" in activity_sql
    assert "legacy_creator_activity AS" in activity_sql
    assert "provider_verified_at" in activity_sql
    assert "ELSE collaboration.updated_at" not in activity_sql
    assert "collaboration.status IN" not in activity_sql
    assert "EXISTS (" in activity_sql
    assert "sender.scope_type = 'platform'" in activity_sql
    assert "sender.business_id IS NULL" in activity_sql
    assert "sender.channel = evidence.channel" in activity_sql
    assert "lower(BTRIM(sender.sender_identity)) = evidence.sender_identity" in activity_sql
    assert "'[_ -]+', '', 'g'" in activity_sql
    assert "WHEN 'telegramdm' THEN 'telegram'" in activity_sql
    assert "WHEN 'vkmessages' THEN 'vk'" in activity_sql
    assert "ELSE NULL" in activity_sql
    assert "activity.queue_id = %s" in activity_sql


def test_legacy_activity_contributes_across_all_platform_author_channels():
    cursor = GateCursor({"total_count": 2, "channel_count": 1, "duplicate_author": False})

    result = reserve_localos_author_daily_slot(
        cursor,
        queue_id="current-email-queue",
        item=author_item(channel="email"),
    )

    activity_sql, params = cursor.calls[1]
    assert "sender.channel = evidence.channel" in activity_sql
    assert "evidence.sender_identity" in activity_sql
    assert "localosgo@gmail.com" not in params
    assert result["author_daily_count"] == 2


def test_confirmed_send_after_later_claim_still_consumes_the_slot():
    cursor = GateCursor({"total_count": AUTHOR_DAILY_LIMIT + 1, "channel_count": 150, "duplicate_author": False})

    result = reserve_localos_author_daily_slot(
        cursor,
        queue_id="later-claimed-queue",
        item=author_item(),
    )

    activity_sql = cursor.calls[1][0]
    consumed_guard = activity_sql.index("activity.accounting_state = 'consumed'")
    reservation_order = activity_sql.index(
        "(activity.occurred_at, activity.queue_id) < (current.occurred_at, %s)"
    )
    assert consumed_guard < reservation_order
    assert result["reason_code"] == "author_daily_limit_reached"


def test_author_gate_blocks_cross_channel_second_touch_for_same_profile():
    cursor = GateCursor({"total_count": 1, "channel_count": 1, "duplicate_author": True})

    result = reserve_localos_author_daily_slot(
        cursor,
        queue_id="telegram-queue",
        item=author_item(channel="telegram", creator_profile_id="shared-profile"),
    )

    assert result["allowed"] is False
    assert result["reason_code"] == "author_already_reserved_today"


def test_author_gate_uses_normalized_contact_to_merge_duplicate_profiles():
    cursor = GateCursor({"total_count": 1, "channel_count": 1, "duplicate_author": True})
    item = author_item(channel="email", creator_profile_id="duplicate-profile-b")
    item["normalized_value"] = " Shared@Example.Test "

    result = reserve_localos_author_daily_slot(
        cursor,
        queue_id="second-profile-queue",
        item=item,
    )

    assert result["reason_code"] == "author_already_reserved_today"
    activity_sql, params = cursor.calls[1]
    assert "COUNT(DISTINCT person_key)" in activity_sql
    assert "normalized_contact = %s" in activity_sql
    assert "shared@example.test" in params


def test_author_gate_enforces_total_and_channel_caps():
    total_cursor = GateCursor({"total_count": AUTHOR_DAILY_LIMIT + 1, "channel_count": 1, "duplicate_author": False})
    channel_cursor = GateCursor({"total_count": 26, "channel_count": 26, "duplicate_author": False})

    total_result = reserve_localos_author_daily_slot(
        total_cursor,
        queue_id="queue-total",
        item=author_item(channel="vk"),
    )
    channel_result = reserve_localos_author_daily_slot(
        channel_cursor,
        queue_id="queue-channel",
        item=author_item(channel="telegram"),
    )

    assert total_result["reason_code"] == "author_daily_limit_reached"
    assert channel_result["reason_code"] == "author_channel_daily_limit_reached"
    assert channel_result["channel"] == "telegram"


def test_author_gate_requires_exact_policy_and_canonical_profile():
    cursor = GateCursor({})
    stale_policy = author_item()
    stale_policy["policy_json"]["daily_limit"] = 201
    extra_channel_policy = author_item()
    extra_channel_policy["policy_json"]["channel_daily_limits"]["manual"] = 1
    missing_profile = author_item(creator_profile_id="")

    assert reserve_localos_author_daily_slot(
        cursor,
        queue_id="queue-policy",
        item=stale_policy,
    )["reason_code"] == "author_daily_policy_not_approved"
    assert reserve_localos_author_daily_slot(
        cursor,
        queue_id="queue-profile",
        item=missing_profile,
    )["reason_code"] == "author_canonical_profile_missing"
    assert reserve_localos_author_daily_slot(
        cursor,
        queue_id="queue-extra-channel",
        item=extra_channel_policy,
    )["reason_code"] == "author_daily_policy_not_approved"
    assert cursor.calls == []


def test_non_author_lane_keeps_legacy_policy_path():
    assert is_localos_author_lane({
        "workstream_type": "localos_sales",
        "sender_mode": "localos",
        "policy_json": {"sender_mode": "localos", "daily_limit": 10},
    }) is False


def test_manual_touch_accepts_user_confirmed_historical_send_with_actual_chronology(monkeypatch):
    occurred_at = datetime.now(timezone.utc) - timedelta(days=7)
    cursor = ManualTouchCursor(
        {
            "id": "touch-1",
            "campaign_id": "campaign-1",
            "lead_id": "lead-1",
            "workstream_id": "workstream-1",
            "workstream_type": "creator_collaboration",
            "scope_type": "platform",
            "business_id": None,
            "channel": "manual",
            "status": "manual_expired",
            "sequence_index": 1,
        },
        None,
    )
    learning_calls = []
    campaign_event_calls = []
    monkeypatch.setattr(
        campaign_service,
        "record_learning_event",
        lambda *args, **kwargs: learning_calls.append(kwargs),
    )
    monkeypatch.setattr(
        campaign_service,
        "record_campaign_event",
        lambda *args, **kwargs: campaign_event_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "services.outreach_yougile_sync_service.enqueue_touch_sent_projection",
        lambda *_args, **_kwargs: None,
    )

    result = record_manual_touch(
        cursor,
        "campaign-1",
        "touch-1",
        "sent",
        user_id="user-1",
        occurred_at=occurred_at,
    )

    assert result["evidence_kind"] == "user_confirmed"
    delivery_call = next(call for call in cursor.calls if "delivery_json = delivery_json" in call[0])
    assert delivery_call[1][1].adapted["manual_occurred_at"] == occurred_at.isoformat()
    assert delivery_call[1][1].adapted["evidence_kind"] == "user_confirmed"
    workstream_call = next(call for call in cursor.calls if "UPDATE lead_workstreams" in call[0])
    assert "last_contact_at = %s" in workstream_call[0]
    assert "next_action_at = %s + INTERVAL '4 days'" in workstream_call[0]
    assert "last_contact_at IS NULL OR last_contact_at <= %s" in workstream_call[0]
    assert "lifecycle_status NOT IN ('replied', 'converted', 'closed_lost', 'suppressed')" in workstream_call[0]
    assert "status <> 'paused'" in workstream_call[0]
    assert occurred_at in workstream_call[1]
    resume_calls = [
        call for call in cursor.calls
        if "prior_manual_touch_pending" in call[0] or "manual_touch_timeout" in call[0]
    ]
    assert resume_calls
    assert all("updated_at <= %s" in query for query, _params in resume_calls)
    assert all(params[-1] == occurred_at for _query, params in resume_calls)
    assert learning_calls[0]["occurred_at"] == occurred_at
    assert learning_calls[0]["payload"]["evidence_kind"] == "user_confirmed"
    assert learning_calls[0]["payload"]["occurred_at"] == occurred_at.isoformat()
    assert campaign_event_calls[0][1]["payload"]["occurred_at"] == occurred_at.isoformat()
    assert campaign_event_calls[0][1]["payload"]["evidence_kind"] == "user_confirmed"

    assert is_localos_author_lane({
        "workstream_type": "client_partnership",
        "sender_mode": "partner_business",
        "policy_json": {"sender_mode": "partner_business", "daily_limit": 10},
    }) is False


def test_manual_touch_historical_reply_uses_actual_time_without_provider_proof(monkeypatch):
    occurred_at = datetime.now(timezone.utc) - timedelta(days=3)
    cursor = ManualTouchCursor(
        {
            "id": "touch-1",
            "campaign_id": "campaign-1",
            "lead_id": "lead-1",
            "workstream_id": "workstream-1",
            "workstream_type": "creator_collaboration",
            "scope_type": "platform",
            "business_id": None,
            "channel": "manual",
            "status": "manual_sent",
            "sequence_index": 1,
        },
        None,
    )
    learning_calls = []
    relationship_calls = []
    room_calls = []
    monkeypatch.setattr(
        campaign_service,
        "classify_inbound_event",
        lambda _payload: {
            "classification": "interested",
            "is_human": True,
            "stops_campaign": True,
            "confidence": 1.0,
            "creates_suppression": False,
        },
    )
    monkeypatch.setattr(
        campaign_service,
        "upsert_relationship_from_reply",
        lambda *args, **kwargs: relationship_calls.append(kwargs),
    )
    monkeypatch.setattr(
        campaign_service,
        "mirror_inbound_to_room",
        lambda *args, **kwargs: room_calls.append(kwargs),
    )
    monkeypatch.setattr(campaign_service, "mark_room_ready_after_positive_reply", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        campaign_service,
        "record_learning_event",
        lambda *args, **kwargs: learning_calls.append(kwargs),
    )
    monkeypatch.setattr(campaign_service, "record_campaign_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "services.outreach_yougile_sync_service.enqueue_touch_sent_projection",
        lambda *_args, **_kwargs: None,
    )

    result = record_manual_touch(
        cursor,
        "campaign-1",
        "touch-1",
        "reply",
        user_id="user-1",
        note="Да, интересно",
        occurred_at=occurred_at,
    )

    inbound_call = next(call for call in cursor.calls if "INSERT INTO outreach_inbound_events" in call[0])
    assert inbound_call[1][-1] == occurred_at
    assert inbound_call[1][-2].adapted["evidence_kind"] == "user_confirmed"
    assert "provider_event_id" not in inbound_call[1][-2].adapted
    assert room_calls[0]["occurred_at"] == occurred_at
    assert relationship_calls[0]["provider_event_id"] is None
    assert {call["occurred_at"] for call in learning_calls} == {occurred_at}
    assert all(call["payload"]["evidence_kind"] == "user_confirmed" for call in learning_calls)
    assert result["evidence_kind"] == "user_confirmed"


@pytest.mark.parametrize(
    ("occurred_at", "message"),
    [
        (datetime.now(), "must include a timezone"),
        (datetime.now(timezone.utc) + timedelta(minutes=2), "must not be in the future"),
    ],
)
def test_manual_touch_rejects_invalid_actual_time_before_database_access(occurred_at, message):
    cursor = GateCursor({})

    with pytest.raises(ValueError, match=message):
        record_manual_touch(
            cursor,
            "campaign-1",
            "touch-1",
            "sent",
            user_id="user-1",
            occurred_at=occurred_at,
        )

    assert cursor.calls == []


def test_native_author_dispatch_remains_blocked_without_trusted_reply_window_receipt():
    safety = Path("src/services/outreach_safety_service.py").read_text(encoding="utf-8")
    campaign = Path("src/services/outreach_campaign_service.py").read_text(encoding="utf-8")

    assert '"reason_code": "author_reply_preflight_unverified"' in safety
    assert '"complete_sender_window_reply_sync_receipt_missing"' in safety
    assert '"current_reply_sync_cycle_cutoff_missing"' in safety
    assert '"author_policy_version": AUTHOR_POLICY_VERSION' in campaign
    assert '"channel_daily_limits": AUTHOR_CHANNEL_DAILY_LIMITS' in campaign


def test_author_preflight_carries_sender_identity_and_runs_generic_guards_before_receipt():
    safety = Path("src/services/outreach_safety_service.py").read_text(encoding="utf-8")
    preflight = safety[safety.index("def run_dispatch_preflight("):safety.index("def persist_preflight_result(")]

    assert "s.sender_identity" in preflight
    assert preflight.index("reserve_localos_author_daily_slot(") < preflight.index("sent_today_row")
    assert preflight.index("sent_today_row") < preflight.index("cross_channel_cooldown")
    assert preflight.index("cross_channel_cooldown") < preflight.index("load_trusted_email_reply_sync_receipt")
    assert "failed.classification IN ('permanent_delivery_failure', 'bounce')" in preflight
    assert "previous_creator.id::text" in preflight
    assert "previous_contact.normalized_value" in preflight
    assert '"gap": "exact_recipient_scope_missing"' in preflight
    assert "required_recipient_emails=[recipient_email]" in preflight
    assert "required_covered_through=author_reply_sync_started_at" in preflight
    assert "'author_already_contacted'::text AS reason_code" in preflight
    assert "creator_collaborations collaboration" in preflight
    assert "provider_message_id" in preflight


def test_preflight_result_carries_the_selected_sender_identity(monkeypatch):
    cursor = GateCursor({
        "id": "queue-1",
        "lead_id": "lead-1",
        "workstream_id": "workstream-1",
        "campaign_touch_id": None,
        "sender_identity": "localosgo@gmail.com",
    })
    monkeypatch.setattr(
        safety_service,
        "load_partnership_repeat_contact_guard",
        lambda *_args, **_kwargs: {"blocked": False},
    )

    result = safety_service.run_dispatch_preflight(cursor, "queue-1")

    assert result["reason_code"] == "campaign_approval_required"
    assert result["item"]["sender_identity"] == "localosgo@gmail.com"
    assert "s.sender_identity" in cursor.calls[0][0]


def test_author_dispatch_uses_creator_bridge_fingerprint_and_fails_closed_on_change(monkeypatch):
    fingerprint = "facts:creator-bridge-current"
    touch = {
        "id": "touch-1",
        "sequence_index": 0,
        "channel": "email",
        "status": "approved",
        "message_brief_json": {"source_fact_fingerprint": fingerprint},
        "quality_gate_json": {"passed": True},
    }
    campaign_snapshot = {
        "id": "campaign-1",
        "version": 1,
        "workstream_id": "workstream-1",
        "lead_id": "lead-1",
        "scope_type": "business",
        "business_id": "business-1",
        "sender_profile_id": None,
        "policy_json": {"sender_mode": "localos_for_partner"},
    }
    item = {
        **campaign_snapshot,
        "campaign_id": "campaign-1",
        "campaign_touch_id": "touch-1",
        "campaign_status": "approved",
        "touch_status": "approved",
        "approved_at": datetime(2026, 9, 7, tzinfo=timezone.utc),
        "approved_snapshot_hash": safety_service.approval_snapshot_hash(
            campaign_snapshot,
            [touch],
        ),
        "campaign_workstream_id": "workstream-1",
        "workstream_type": "creator_collaboration",
        "sender_mode": "localos_for_partner",
        "sender_account_id": None,
        "sequence_index": 0,
    }
    monkeypatch.setattr(
        safety_service,
        "load_partnership_repeat_contact_guard",
        lambda *_args, **_kwargs: {"blocked": False},
    )
    monkeypatch.setattr(
        safety_service,
        "generation_contract_current",
        lambda *_args, **_kwargs: True,
    )
    calls = []
    monkeypatch.setattr(
        campaign_service,
        "current_outreach_source_fact_fingerprint",
        lambda _cursor, workstream_id, sender_mode: calls.append(
            (workstream_id, sender_mode)
        ) or fingerprint,
    )

    result = safety_service.run_dispatch_preflight(
        DispatchFingerprintCursor(item, [touch]),
        "queue-1",
    )
    assert calls == [("workstream-1", "localos_for_partner")]
    assert result["reason_code"] == "sender_account_missing"

    monkeypatch.setattr(
        campaign_service,
        "current_outreach_source_fact_fingerprint",
        lambda *_args, **_kwargs: "",
    )
    changed = safety_service.run_dispatch_preflight(
        DispatchFingerprintCursor(item, [touch]),
        "queue-1",
    )
    assert changed["reason_code"] == "source_facts_changed"


def test_author_preview_defaults_to_email_and_rejects_unreserved_manual_channels():
    campaign = Path("src/services/outreach_campaign_service.py").read_text(encoding="utf-8")
    preview_block = campaign[campaign.index("def build_preview("):campaign.index("def persist_preview(")]
    persist_block = campaign[campaign.index("def persist_preview("):campaign.index("def approve_campaign(")]
    approval_block = campaign[campaign.index("def approve_campaign("):campaign.index("def change_campaign_status(")]
    manual_block = campaign[
        campaign.index("def record_manual_touch("):
        campaign.index("def record_campaign_business_outcome(")
    ]

    assert '"channel": "email"' in preview_block
    assert '"skip_if_unavailable": False' in preview_block
    assert "author_channel_unsupported:" in preview_block
    assert 'raise ValueError("Author campaign channel unsupported")' in persist_block
    assert 'raise ValueError("Author campaign channel unsupported")' in approval_block
    assert "reserve_localos_author_daily_slot" not in manual_block


@pytest.mark.integration
def test_author_gate_query_executes_on_migrated_postgres(postgres_container, run_migrations):
    database_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://",
        "postgresql://",
        1,
    )
    connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        result = reserve_localos_author_daily_slot(
            connection.cursor(),
            queue_id=str(uuid.uuid4()),
            item=author_item(creator_profile_id=str(uuid.uuid4())),
        )
        assert result["allowed"] is True
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.integration
def test_author_gate_null_predicates_are_conservative_on_postgres(postgres_container):
    database_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://",
        "postgresql://",
        1,
    )
    connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            WITH legacy_cases(provider_verified_at) AS (
                VALUES (NULL::text), ('not-a-timestamp'::text)
            ),
            global_cap_cases(workstream_type, sender_mode, creator_id) AS (
                VALUES
                    (NULL::text, NULL::text, 'creator-1'::text),
                    ('creator_collaboration'::text, NULL::text, 'creator-2'::text),
                    (NULL::text, 'localos_for_partner'::text, 'creator-3'::text)
            )
            SELECT
                (
                    SELECT COUNT(*)::int
                    FROM legacy_cases
                    WHERE NOT COALESCE(
                        pg_input_is_valid(provider_verified_at, 'timestamp with time zone'),
                        FALSE
                    )
                ) AS conservative_legacy_rows,
                (
                    SELECT COUNT(*)::int
                    FROM global_cap_cases
                    WHERE NOT COALESCE(
                        workstream_type = 'creator_collaboration'
                        AND sender_mode = 'localos_for_partner'
                        AND creator_id IS NOT NULL,
                        FALSE
                    )
                ) AS conservative_global_rows
            """
        )
        result = dict(cursor.fetchone())
        assert result == {
            "conservative_legacy_rows": 2,
            "conservative_global_rows": 3,
        }
    finally:
        connection.close()
