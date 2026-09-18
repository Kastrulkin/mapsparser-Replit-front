"""Native PostgreSQL causal coverage for mobile review-action confirmation.

The mobile review workspace prepares a pending ``operatoractions`` envelope
before a person confirms it.  Preparing that internal record is deliberately
kept distinct from generating drafts, reserving credits, or completing an
action.  These tests state the stored-role contract for the later confirm
boundary without changing the existing preview contract.
"""

import json
import uuid

import psycopg2
import pytest

from api import operator_api
from tests.test_legacy_business_data_pg import migrated_business_database
from tests.test_operator_review_reply_viewer_readiness import (
    bearer,
    counted_generator,
    review_reply_fixture,
    route_client,
    state_snapshot,
)


def review_preview(client, fixture, actor, review_ids, scope_type="business", scope_id=None):
    return client.post(
        "/api/operator/mobile/actions/preview",
        json={
            "scope_type": scope_type,
            "scope_id": scope_id or fixture["business_id"],
            "capability": "review_replies.generate",
            "input": {"review_ids": review_ids},
        },
        headers=bearer(client, fixture[actor]),
    )


def confirm_action(client, fixture, actor, action_id):
    return client.post(
        f"/api/operator/mobile/actions/{action_id}/confirm",
        json={},
        headers=bearer(client, fixture[actor]),
    )


def action_snapshot(database_url, action_id):
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT status, confirmed_at IS NOT NULL, executed_at IS NOT NULL FROM operatoractions WHERE id = %s",
            (action_id,),
        )
        return tuple(cursor.fetchone() or ())
    finally:
        cursor.close()
        connection.close()


PENDING_ACTION = ("pending_approval", False, False)


def assert_confirm_has_no_review_side_effect(before, after, action_before, action_after, generator_calls):
    assert generator_calls == [], f"generator_calls={json.dumps(generator_calls)}"
    assert after == before
    assert action_after == action_before == PENDING_ACTION


@pytest.mark.parametrize("actor", ("direct_viewer", "network_viewer"))
def test_stored_viewer_cannot_confirm_mobile_review_generation(review_reply_fixture, monkeypatch, actor):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )

    preview = review_preview(client, fixture, actor, [fixture["review_id"]])
    assert preview.status_code == 200
    action_id = preview.get_json()["preview"]["action_id"]
    before = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    action_before = action_snapshot(fixture["database_url"], action_id)

    response = confirm_action(client, fixture, actor, action_id)

    after = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    action_after = action_snapshot(fixture["database_url"], action_id)
    assert response.status_code == 403, json.dumps({
        "status": response.status_code,
        "before": before,
        "after": after,
        "action_before": action_before,
        "action_after": action_after,
        "generator_calls": generator_calls,
    }, sort_keys=True, default=str)
    assert_confirm_has_no_review_side_effect(before, after, action_before, action_after, generator_calls)


@pytest.mark.parametrize("actor", ("owner", "direct_member", "network_member"))
def test_owner_and_members_can_confirm_mobile_review_generation(review_reply_fixture, monkeypatch, actor):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )

    preview = review_preview(client, fixture, actor, [fixture["review_id"]])
    assert preview.status_code == 200
    action_id = preview.get_json()["preview"]["action_id"]

    response = confirm_action(client, fixture, actor, action_id)

    assert response.status_code == 200
    assert generator_calls == ["generate"]
    assert action_snapshot(fixture["database_url"], action_id) == ("completed", True, True)


def test_revoked_member_cannot_confirm_mobile_review_preview(review_reply_fixture, monkeypatch):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )

    preview = review_preview(client, fixture, "direct_member", [fixture["review_id"]])
    assert preview.status_code == 200
    action_id = preview.get_json()["preview"]["action_id"]
    connection = psycopg2.connect(fixture["database_url"])
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE business_members SET status = 'revoked' WHERE business_id = %s AND user_id = %s",
            (fixture["business_id"], fixture["direct_member"]),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    before = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    action_before = action_snapshot(fixture["database_url"], action_id)

    response = confirm_action(client, fixture, "direct_member", action_id)

    after = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    action_after = action_snapshot(fixture["database_url"], action_id)
    assert response.status_code == 403
    assert_confirm_has_no_review_side_effect(before, after, action_before, action_after, generator_calls)


def test_confirm_stops_before_any_review_generator_when_one_retained_target_is_viewer_only(
    review_reply_fixture,
    monkeypatch,
):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )
    second_owner = str(uuid.uuid4())
    second_business = str(uuid.uuid4())
    second_review = str(uuid.uuid4())
    connection = psycopg2.connect(fixture["database_url"])
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (id, email, password_hash, is_active, is_verified, is_superadmin) "
            "VALUES (%s, %s, %s, TRUE, TRUE, FALSE)",
            (second_owner, f"{second_owner}@benchmark.invalid", "not-used-by-login"),
        )
        cursor.execute(
            "SELECT network_id FROM businesses WHERE id = %s",
            (fixture["business_id"],),
        )
        network_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name, entity_group, subscription_tier, subscription_status, network_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (second_business, second_owner, "Second review target", "client", "concierge", "active", network_id),
        )
        cursor.execute(
            "INSERT INTO externalbusinessreviews "
            "(id, business_id, source, external_review_id, rating, author_name, text, response_text) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (second_review, second_business, "yandex", "second-review", 5, "Second guest", "Second synthetic review", ""),
        )
        cursor.execute(
            "UPDATE externalbusinessreviews SET published_at = NOW() WHERE id = %s",
            (fixture["review_id"],),
        )
        cursor.execute(
            "UPDATE externalbusinessreviews SET published_at = NOW() - INTERVAL '1 day' WHERE id = %s",
            (second_review,),
        )
        cursor.execute(
            "INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), fixture["business_id"], fixture["network_viewer"], "member", "active"),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    preview = review_preview(
        client,
        fixture,
        "network_viewer",
        [fixture["review_id"], second_review],
        scope_type="network",
        scope_id=network_id,
    )
    assert preview.status_code == 200
    action_id = preview.get_json()["preview"]["action_id"]
    before = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    action_before = action_snapshot(fixture["database_url"], action_id)

    response = confirm_action(client, fixture, "network_viewer", action_id)

    after = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    action_after = action_snapshot(fixture["database_url"], action_id)
    assert response.status_code == 403, json.dumps({
        "status": response.status_code,
        "before": before,
        "after": after,
        "action_before": action_before,
        "action_after": action_after,
        "generator_calls": generator_calls,
    }, sort_keys=True, default=str)
    assert_confirm_has_no_review_side_effect(before, after, action_before, action_after, generator_calls)


def test_completed_mobile_action_replay_does_not_reexecute_after_member_becomes_viewer(
    review_reply_fixture,
    monkeypatch,
):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )
    preview = review_preview(client, fixture, "direct_member", [fixture["review_id"]])
    assert preview.status_code == 200
    action_id = preview.get_json()["preview"]["action_id"]
    first = confirm_action(client, fixture, "direct_member", action_id)
    assert first.status_code == 200
    assert generator_calls == ["generate"]
    connection = psycopg2.connect(fixture["database_url"])
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE business_members SET role = 'viewer' WHERE business_id = %s AND user_id = %s",
            (fixture["business_id"], fixture["direct_member"]),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    replay = confirm_action(client, fixture, "direct_member", action_id)

    assert replay.status_code == 200
    assert replay.get_json()["idempotent"] is True
    assert generator_calls == ["generate"]
    assert action_snapshot(fixture["database_url"], action_id) == ("completed", True, True)


@pytest.mark.parametrize("actor, expected_status", (("direct_viewer", 403), ("owner", 200)))
def test_generic_mobile_confirm_applies_the_same_role_boundary_to_finance_delete(
    review_reply_fixture,
    actor,
    expected_status,
):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    transaction_id = str(uuid.uuid4())
    connection = psycopg2.connect(fixture["database_url"])
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO financialtransactions (id, user_id, business_id, amount, description, transaction_type, transaction_date) "
            "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE)",
            (transaction_id, fixture["owner"], fixture["business_id"], 100, "Synthetic guarded delete", "income"),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    preview = client.post(
        "/api/operator/mobile/actions/preview",
        json={
            "scope_type": "business",
            "scope_id": fixture["business_id"],
            "capability": "finance.transaction.delete",
            "input": {"business_id": fixture["business_id"], "transaction_id": transaction_id},
        },
        headers=bearer(client, fixture[actor]),
    )
    assert preview.status_code == 200
    action_id = preview.get_json()["preview"]["action_id"]
    action_before = action_snapshot(fixture["database_url"], action_id)

    response = confirm_action(client, fixture, actor, action_id)

    connection = psycopg2.connect(fixture["database_url"])
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM financialtransactions WHERE id = %s", (transaction_id,))
        remaining = cursor.fetchone()[0]
    finally:
        cursor.close()
        connection.close()
    action_after = action_snapshot(fixture["database_url"], action_id)
    expected_remaining = 1 if expected_status == 403 else 0
    assert response.status_code == expected_status, json.dumps({
        "status": response.status_code,
        "remaining": remaining,
        "expected_remaining": expected_remaining,
        "action_before": action_before,
        "action_after": action_after,
    }, sort_keys=True, default=str)
    assert remaining == expected_remaining
    if expected_status == 403:
        assert action_after == action_before == PENDING_ACTION
        return
    assert action_after == ("completed", True, True)
