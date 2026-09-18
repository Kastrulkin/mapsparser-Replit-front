"""Native PostgreSQL regression coverage for review-reply mutations and stored roles.

The fixture creates a disposable local database through the existing guarded
migration helper.  Routes, session authentication, membership lookup and the
mobile control-scope resolver are real.  Only the model-backed draft generator
is replaced by a counted local seam: a denied request must not reach it, so it
cannot reserve credits or create a draft.
"""

import os
import uuid

import psycopg2
import pytest

from api import operator_api
from tests.test_legacy_business_data_pg import migrated_business_database, seed_user_and_business


MUTATION_CASES = (
    "web_generate",
    "web_manual_publish",
    "mobile_update",
    "mobile_manual_publish",
    "mobile_generate",
)


def route_client(database_url):
    from main import app

    assert os.environ.get("DATABASE_URL") == database_url
    return app.test_client()


def bearer(client, user_id):
    octet = (sum(user_id.encode("utf-8")) % 240) + 1
    response = client.post(
        "/api/auth/login",
        json={"email": f"{user_id}@benchmark.invalid", "password": "benchmark-password"},
        environ_overrides={"REMOTE_ADDR": f"198.51.100.{octet}"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def counted_generator(calls):
    def generate(*_args, **_kwargs):
        calls.append("generate")
        return {"status": "completed", "drafts": [], "finalization_result": {}}

    return generate


def state_snapshot(database_url, review_id, draft_id):
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT status, COALESCE(edited_text, '') FROM reviewreplydrafts WHERE id = %s",
            (draft_id,),
        )
        draft = cursor.fetchone()
        cursor.execute(
            "SELECT COALESCE(response_text, '') FROM externalbusinessreviews WHERE id = %s",
            (review_id,),
        )
        review = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM operatorcreditreservations")
        reservations = cursor.fetchone()
        return {
            "draft": tuple(draft or ()),
            "review": tuple(review or ()),
            "reservations": int((reservations or (0,))[0]),
        }
    finally:
        cursor.close()
        connection.close()


@pytest.fixture
def review_reply_fixture(migrated_business_database):
    owner, business_id = seed_user_and_business(migrated_business_database)
    direct_member, _unused_member_business = seed_user_and_business(migrated_business_database)
    direct_viewer, _unused_viewer_business = seed_user_and_business(migrated_business_database)
    network_member, _unused_network_member_business = seed_user_and_business(migrated_business_database)
    network_viewer, _unused_network_viewer_business = seed_user_and_business(migrated_business_database)
    revoked, _unused_revoked_business = seed_user_and_business(migrated_business_database)
    foreign, _foreign_business = seed_user_and_business(migrated_business_database)
    network_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    connection = psycopg2.connect(migrated_business_database)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO networks (id, owner_id, name, entity_group) VALUES (%s, %s, %s, %s)",
            (network_id, owner, "Review mutation network", "client"),
        )
        cursor.execute("UPDATE businesses SET network_id = %s WHERE id = %s", (network_id, business_id))
        memberships = (
            ("business_members", business_id, direct_member, "member", "active"),
            ("business_members", business_id, direct_viewer, "viewer", "active"),
            ("network_members", network_id, network_member, "member", "active"),
            ("network_members", network_id, network_viewer, "viewer", "active"),
            ("business_members", business_id, revoked, "viewer", "revoked"),
        )
        for table_name, scope_id, user_id, role, status in memberships:
            cursor.execute(
                f"INSERT INTO {table_name} (id, {'business_id' if table_name == 'business_members' else 'network_id'}, user_id, role, status) VALUES (%s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), scope_id, user_id, role, status),
            )
        cursor.execute(
            """
            INSERT INTO externalbusinessreviews
                (id, business_id, source, external_review_id, rating, author_name, text, response_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (review_id, business_id, "yandex", "review-external-id", 5, "Synthetic guest", "Спасибо за сервис", ""),
        )
        cursor.execute(
            """
            INSERT INTO reviewreplydrafts
                (id, business_id, review_id, user_id, source, rating, author_name, review_text, generated_text, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (draft_id, business_id, review_id, owner, "yandex", 5, "Synthetic guest", "Спасибо за сервис", "Спасибо за отзыв!", "draft"),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return {
        "database_url": migrated_business_database,
        "business_id": business_id,
        "review_id": review_id,
        "draft_id": draft_id,
        "owner": owner,
        "direct_member": direct_member,
        "direct_viewer": direct_viewer,
        "network_member": network_member,
        "network_viewer": network_viewer,
        "revoked": revoked,
        "foreign": foreign,
    }


def mutation_request(case, fixture):
    business_id = fixture["business_id"]
    draft_id = fixture["draft_id"]
    review_id = fixture["review_id"]
    if case == "web_generate":
        return (
            "post",
            "/api/operator/review-replies/generate",
            {"business_id": business_id, "limit": 1, "review_id": review_id},
        )
    if case == "web_manual_publish":
        return (
            "post",
            f"/api/operator/review-reply-drafts/{draft_id}/mark-manual-published",
            {"business_id": business_id},
        )
    scope_payload = {"scope_type": "business", "scope_id": business_id}
    if case == "mobile_update":
        return (
            "put",
            f"/api/operator/mobile/review-drafts/{draft_id}",
            {**scope_payload, "reply_text": "Уточнённый безопасный ответ"},
        )
    if case == "mobile_manual_publish":
        return (
            "post",
            f"/api/operator/mobile/review-drafts/{draft_id}/mark-manual-published",
            scope_payload,
        )
    if case == "mobile_generate":
        return (
            "post",
            f"/api/operator/mobile/reviews/{review_id}/generate",
            {**scope_payload, "confirmed": True},
        )
    raise AssertionError(f"Unknown mutation case: {case}")


def invoke_mutation(client, case, fixture, actor):
    method, path, payload = mutation_request(case, fixture)
    headers = bearer(client, fixture[actor])
    return getattr(client, method)(path, json=payload, headers=headers)


def assert_unchanged(before, after, generator_calls):
    assert generator_calls == []
    assert after == before


@pytest.mark.parametrize("actor", ("direct_viewer", "network_viewer"))
def test_stored_viewers_keep_mobile_review_reply_preview_access(review_reply_fixture, monkeypatch, actor):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )
    before = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])

    response = client.post(
        f"/api/operator/mobile/reviews/{fixture['review_id']}/generate",
        json={"scope_type": "business", "scope_id": fixture["business_id"]},
        headers=bearer(client, fixture[actor]),
    )

    after = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    assert response.status_code == 200
    assert response.get_json()["preview"]["confirmation_required"] is True
    assert_unchanged(before, after, generator_calls)


@pytest.mark.parametrize("case", MUTATION_CASES)
@pytest.mark.parametrize("actor", ("direct_viewer", "network_viewer", "revoked", "foreign"))
def test_stored_viewers_and_nonmembers_cannot_mutate_review_reply_state(
    review_reply_fixture,
    monkeypatch,
    case,
    actor,
):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )
    before = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])

    response = invoke_mutation(client, case, fixture, actor)

    after = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    assert response.status_code == 403, {
        "status": response.status_code,
        "before": before,
        "after": after,
        "generator_calls": generator_calls,
    }
    assert_unchanged(before, after, generator_calls)


@pytest.mark.parametrize("case", MUTATION_CASES)
@pytest.mark.parametrize("actor", ("owner", "direct_member", "network_member"))
def test_owner_and_nonviewer_members_keep_review_reply_mutation_access(
    review_reply_fixture,
    monkeypatch,
    case,
    actor,
):
    fixture = review_reply_fixture
    client = route_client(fixture["database_url"])
    generator_calls = []
    monkeypatch.setattr(
        operator_api,
        "generate_review_reply_drafts_for_unanswered_reviews",
        counted_generator(generator_calls),
    )

    response = invoke_mutation(client, case, fixture, actor)

    assert response.status_code == 200
    if case in {"web_generate", "mobile_generate"}:
        assert generator_calls == ["generate"]
        return
    assert generator_calls == []
    state = state_snapshot(fixture["database_url"], fixture["review_id"], fixture["draft_id"])
    if case == "mobile_update":
        assert state["draft"] == ("edited", "Уточнённый безопасный ответ")
        return
    assert state["draft"][0] == "manual_published"
    assert state["review"] == ("Спасибо за отзыв!",)
