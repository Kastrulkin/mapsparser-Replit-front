"""Real stored subscription admission for the actual mobile review action name."""

import json

import psycopg2
import pytest

from api import operator_api
from tests.test_legacy_business_data_pg import migrated_business_database
from tests.test_operator_mobile_review_confirmation_readiness import (
    action_snapshot,
    confirm_action,
    review_preview,
)
from tests.test_operator_review_reply_viewer_readiness import (
    counted_generator,
    review_reply_fixture,
    route_client,
    state_snapshot,
)


def set_subscription_status(database_url, business_id, status):
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE businesses SET subscription_status = %s WHERE id = %s",
            (status, business_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def owner_action_count(database_url, owner_id):
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM operatoractions WHERE user_id = %s", (owner_id,))
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        connection.close()


@pytest.mark.parametrize("status, expected_code", (("inactive", 402), ("active", 200)))
def test_review_action_preview_uses_stored_subscription_capability(
    review_reply_fixture, monkeypatch, status, expected_code,
):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    calls = []
    monkeypatch.setattr(
        operator_api, "generate_review_reply_drafts_for_unanswered_reviews", counted_generator(calls),
    )
    set_subscription_status(fixture["database_url"], fixture["business_id"], status)
    before = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    count_before = owner_action_count(fixture["database_url"], fixture["owner"])

    response = review_preview(client, fixture, "owner", [fixture["review_id"]])

    count_after = owner_action_count(fixture["database_url"], fixture["owner"])
    assert response.status_code == expected_code, json.dumps({
        "status": response.status_code, "expected_code": expected_code,
        "actions_before": count_before, "actions_after": count_after,
        "generator_calls": calls,
    }, sort_keys=True)
    assert calls == []
    assert state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"]) == before
    if expected_code == 402:
        assert response.get_json()["capability"] == "maps.reviews"
        assert response.get_json()["payment_required"] is True
        assert count_after == count_before
    else:
        assert count_after == count_before + 1
        action_id = response.get_json()["preview"]["action_id"]
        assert action_snapshot(fixture["database_url"], action_id) == ("pending_approval", False, False)


@pytest.mark.parametrize("status, expected_code", (("inactive", 402), ("active", 200)))
def test_review_action_confirmation_rechecks_subscription_after_preview(
    review_reply_fixture, monkeypatch, status, expected_code,
):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    calls = []
    monkeypatch.setattr(
        operator_api, "generate_review_reply_drafts_for_unanswered_reviews", counted_generator(calls),
    )
    preview = review_preview(client, fixture, "owner", [fixture["review_id"]])
    assert preview.status_code == 200
    action_id = preview.get_json()["preview"]["action_id"]
    set_subscription_status(fixture["database_url"], fixture["business_id"], status)
    before = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    action_before = action_snapshot(fixture["database_url"], action_id)

    response = confirm_action(client, fixture, "owner", action_id)

    action_after = action_snapshot(fixture["database_url"], action_id)
    assert response.status_code == expected_code, json.dumps({
        "status": response.status_code, "expected_code": expected_code,
        "action_before": action_before, "action_after": action_after,
        "generator_calls": calls,
    }, sort_keys=True)
    if expected_code == 402:
        assert response.get_json()["capability"] == "maps.reviews"
        assert response.get_json()["payment_required"] is True
        assert calls == []
        assert action_after == action_before == ("pending_approval", False, False)
        assert state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"]) == before
    else:
        assert calls == ["generate"]
        assert action_after == ("completed", True, True)
