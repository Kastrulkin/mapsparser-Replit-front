"""Desired-contract PostgreSQL regressions for social approval target binding.

These cases use the canonical isolated social publish database fixture.  They
exercise real approval, durable claim, resolver, adapter, and finalizer code;
only the outbound Telegram transport is replaced.
"""

import json
import sys
import uuid
from pathlib import Path

import psycopg2
import pytest

from tests.test_social_publish_uncertain_commit import social_publish_database, seed_approved_post


ROOT = Path(__file__).parents[1]


def _social_post_state(database_url, post_id):
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT business_id, content_plan_item_id, status, approved_at, approval_id, provider_post_id, metadata_json FROM social_posts WHERE id=%s",
            (post_id,),
        )
        row = cursor.fetchone()
        metadata = row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}")
        return {
            "business_id": str(row[0]),
            "item_id": str(row[1]),
            "status": str(row[2]),
            "approved_at": row[3],
            "approval_id": row[4],
            "provider_post_id": row[5],
            "metadata": metadata,
        }
    finally:
        cursor.close()
        connection.close()


def _prepare_post_for_fresh_approval(database_url, post_id):
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE social_posts
            SET status='needs_review', approved_at=NULL, approval_id=NULL,
                provider_post_id=NULL, provider_post_url=NULL,
                base_text=%s, platform_text=%s, media_json='[]'::jsonb,
                metadata_json='{}'::jsonb
            WHERE id=%s
            """,
            (
                "A practical local-business update with a clear customer benefit.",
                "A practical local-business update with a clear customer benefit.",
                post_id,
            ),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _set_telegram_chat(database_url, business_id, chat_id):
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE businesses SET telegram_chat_id=%s WHERE id=%s", (chat_id, business_id))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _telegram_chat(database_url, business_id):
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT telegram_chat_id FROM businesses WHERE id=%s", (business_id,))
        row = cursor.fetchone()
        return str(row[0] or "")
    finally:
        cursor.close()
        connection.close()


def _attach_selected_asset(database_url, post_id, content_hash, target_id=""):
    state = _social_post_state(database_url, post_id)
    asset_id = str(uuid.uuid4())
    usage_id = str(uuid.uuid4())
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO photo_assets(
                id, business_id, source, original_url, storage_key, versions_json,
                metadata_json, content_hash, analysis_status, created_by
            )
            VALUES (%s,%s,'upload','/synthetic/photo','synthetic/photo',
                    '{"original":{"storage_path":"synthetic/photo","mime_type":"image/jpeg"}}'::jsonb,
                    '{}'::jsonb,%s,'not_analyzed',NULL)
            """,
            (asset_id, state["business_id"], content_hash),
        )
        cursor.execute(
            """
            INSERT INTO photo_asset_usage_events(
                id, photo_asset_id, business_id, usage_type, target_id, target_platform, metadata_json
            )
            VALUES (%s,%s,%s,'publication',%s,'telegram','{}'::jsonb)
            """,
            (usage_id, asset_id, state["business_id"], target_id or post_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return asset_id


def _replace_asset_hash(database_url, asset_id, content_hash):
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE photo_assets SET content_hash=%s WHERE id=%s", (content_hash, asset_id))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _remove_asset_selection(database_url, asset_id):
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM photo_asset_usage_events WHERE photo_asset_id=%s", (asset_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _snapshot_has_sensitive_value(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = str(key).lower()
            if any(marker in normalized_key for marker in ("token", "secret", "password", "credential", "auth_data")):
                return True
            if _snapshot_has_sensitive_value(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_snapshot_has_sensitive_value(item) for item in value)
    return False


def _approved_snapshot(state):
    snapshot = state["metadata"].get("approval_publish_snapshot")
    assert isinstance(snapshot, dict)
    assert snapshot.get("schema") == "localos_social_publish_approval_v1"
    assert snapshot.get("approval_id") == str(state["approval_id"])
    assert _snapshot_has_sensitive_value(snapshot) is False
    assert "synthetic-test-token" not in json.dumps(snapshot, sort_keys=True)
    return snapshot


def _transport_recorder(observed):
    class Response:
        status = 200

        def read(self):
            return json.dumps({"ok": True, "result": {"message_id": 917}}).encode("utf-8")

        def close(self):
            return None

    def transport(request, timeout=15):
        payload = json.loads(request.data.decode("utf-8"))
        observed.append(str(payload.get("chat_id") or ""))
        return Response()

    return transport


def _freshly_approved_post(database_url):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(database_url)
    _prepare_post_for_fresh_approval(database_url, post_id)
    approved = social_post_service.approve_social_post(user_id, post_id)
    assert approved["status"] == "approved"
    return social_post_service, user_id, post_id


def _assert_review_without_receipt(database_url, post_id):
    state = _social_post_state(database_url, post_id)
    assert state["status"] == "needs_review"
    assert state["approved_at"] is None
    assert state["approval_id"] is None
    assert state["provider_post_id"] is None
    assert "approval_publish_snapshot" not in state["metadata"]
    assert "publish_attempt" not in state["metadata"]


def _replace_snapshot(database_url, post_id, snapshot):
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE social_posts SET metadata_json=%s::jsonb WHERE id=%s",
            (json.dumps({"approval_publish_snapshot": snapshot}), post_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def test_desired_real_approval_persists_nonsecret_v1_snapshot(social_publish_database):
    _service, _user_id, post_id = _freshly_approved_post(social_publish_database)
    _approved_snapshot(_social_post_state(social_publish_database, post_id))


def test_item_level_local_media_is_bound_by_stable_asset_identity(social_publish_database):
    service, _user_id, post_id = _freshly_approved_post(social_publish_database)
    state = _social_post_state(social_publish_database, post_id)
    asset_id = _attach_selected_asset(social_publish_database, post_id, "c" * 64, state["item_id"])
    _prepare_post_for_fresh_approval(social_publish_database, post_id)
    approved = service.approve_social_post(_user_id, post_id)
    assert approved["status"] == "approved"
    media = _approved_snapshot(_social_post_state(social_publish_database, post_id))["media"]
    assert media == [
        {
            "asset_id": asset_id,
            "asset_version": 1,
            "content_hash": "c" * 64,
            "storage_path": "synthetic/photo",
            "public_url": "/synthetic/photo",
            "mime_type": "image/jpeg",
        }
    ]


def test_unconfigured_text_approval_is_non_sendable_and_requires_fresh_approval(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    _prepare_post_for_fresh_approval(social_publish_database, post_id)
    before = _social_post_state(social_publish_database, post_id)
    _set_telegram_chat(social_publish_database, before["business_id"], "")
    approved = social_post_service.approve_social_post(user_id, post_id)
    assert approved["status"] == "approved"
    snapshot = _approved_snapshot(_social_post_state(social_publish_database, post_id))
    assert snapshot["binding"]["state"] == "connection_unbound"
    queued = social_post_service.queue_social_post(user_id, post_id)
    assert queued["status"] == "queued"
    original_approval_id = str(queued["approval_id"])
    _set_telegram_chat(social_publish_database, before["business_id"], "@connected_after_text_approval")
    observed = []
    monkeypatch.setattr(social_post_service, "telegram_urlopen", _transport_recorder(observed))

    result = social_post_service.publish_social_post(user_id, post_id)

    assert observed == []
    assert result["status"] == "needs_review"
    _assert_review_without_receipt(social_publish_database, post_id)
    reapproved = social_post_service.approve_social_post(user_id, post_id)
    assert reapproved["status"] == "approved"
    assert str(reapproved["approval_id"]) != original_approval_id
    assert "state" not in _approved_snapshot(_social_post_state(social_publish_database, post_id))["binding"]


def test_telegram_target_drift_after_real_approval_never_reaches_transport(social_publish_database, monkeypatch):
    service, user_id, post_id = _freshly_approved_post(social_publish_database)
    before = _social_post_state(social_publish_database, post_id)
    approved_chat = _telegram_chat(social_publish_database, before["business_id"])
    changed_chat = "@changed_after_approval"
    _set_telegram_chat(social_publish_database, before["business_id"], changed_chat)
    observed = []
    monkeypatch.setattr(service, "telegram_urlopen", _transport_recorder(observed))

    result = service.publish_social_post(user_id, post_id)

    assert approved_chat != changed_chat
    assert observed == []
    assert result["status"] == "needs_review"
    _assert_review_without_receipt(social_publish_database, post_id)


@pytest.mark.parametrize("malformed", (None, {"schema": "localos_social_publish_approval_v1", "approval_id": "wrong-approval"}))
def test_desired_legacy_or_malformed_approved_snapshot_never_reaches_claim_or_transport(social_publish_database, monkeypatch, malformed):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    if malformed is None:
        _replace_snapshot(social_publish_database, post_id, None)
    else:
        _replace_snapshot(social_publish_database, post_id, malformed)
    adapter_calls = []
    real_adapter = social_post_service._publish_api_post

    def adapter(cursor, post, *args, **kwargs):
        adapter_calls.append(str(post.get("id") or ""))
        return real_adapter(cursor, post, *args, **kwargs)

    observed = []
    monkeypatch.setattr(social_post_service, "_publish_api_post", adapter)
    monkeypatch.setattr(social_post_service, "telegram_urlopen", _transport_recorder(observed))

    result = social_post_service.publish_social_post(user_id, post_id)

    assert adapter_calls == []
    assert observed == []
    assert result["status"] == "needs_review"
    _assert_review_without_receipt(social_publish_database, post_id)


def _assert_media_drift_is_stopped_before_adapter(database_url, monkeypatch, mode):
    service, user_id, post_id = _freshly_approved_post(database_url)
    asset_id = _attach_selected_asset(database_url, post_id, "a" * 64)
    _prepare_post_for_fresh_approval(database_url, post_id)
    approved = service.approve_social_post(user_id, post_id)
    assert approved["status"] == "approved"
    if mode == "hash":
        _replace_asset_hash(database_url, asset_id, "b" * 64)
    else:
        replacement_asset_id = _attach_selected_asset(database_url, post_id, "a" * 64)
        _remove_asset_selection(database_url, asset_id)
        assert replacement_asset_id != asset_id
    adapter_calls = []
    real_adapter = service._publish_api_post

    def adapter(cursor, post, *args, **kwargs):
        adapter_calls.append(str(post.get("id") or ""))
        return real_adapter(cursor, post, *args, **kwargs)

    monkeypatch.setattr(service, "_publish_api_post", adapter)
    monkeypatch.setattr(service, "telegram_urlopen", _transport_recorder([]))

    result = service.publish_social_post(user_id, post_id)

    assert adapter_calls == []
    assert result["status"] == "needs_review"
    _assert_review_without_receipt(database_url, post_id)


def test_telegram_media_hash_drift_after_real_approval_never_reaches_adapter(social_publish_database, monkeypatch):
    _assert_media_drift_is_stopped_before_adapter(social_publish_database, monkeypatch, "hash")


def test_telegram_media_asset_identity_drift_after_real_approval_never_reaches_adapter(social_publish_database, monkeypatch):
    _assert_media_drift_is_stopped_before_adapter(social_publish_database, monkeypatch, "identity")


def test_unchanged_telegram_approval_uses_current_destination_and_real_receipt(social_publish_database, monkeypatch):
    service, user_id, post_id = _freshly_approved_post(social_publish_database)
    state = _social_post_state(social_publish_database, post_id)
    approved_chat = _telegram_chat(social_publish_database, state["business_id"])
    observed = []
    monkeypatch.setattr(service, "telegram_urlopen", _transport_recorder(observed))

    result = service.publish_social_post(user_id, post_id)

    assert result["status"] == "published"
    assert observed == [approved_chat]
    assert _social_post_state(social_publish_database, post_id)["provider_post_id"] == "917"


def test_telegram_target_changed_after_claim_never_redirects_provider_payload(social_publish_database, monkeypatch):
    service, user_id, post_id = _freshly_approved_post(social_publish_database)
    before = _social_post_state(social_publish_database, post_id)
    approved_chat = _telegram_chat(social_publish_database, before["business_id"])
    changed_chat = "@changed_after_claim"
    observed = []
    real_adapter = service._publish_api_post

    def mutate_then_dispatch(cursor, post, *args, **kwargs):
        _set_telegram_chat(social_publish_database, before["business_id"], changed_chat)
        return real_adapter(cursor, post, *args, **kwargs)

    monkeypatch.setattr(service, "_publish_api_post", mutate_then_dispatch)
    monkeypatch.setattr(service, "telegram_urlopen", _transport_recorder(observed))

    result = service.publish_social_post(user_id, post_id)

    assert changed_chat not in observed
    if observed:
        assert observed == [approved_chat]
        assert result["status"] == "published"
    else:
        assert result["status"] == "needs_review"
        _assert_review_without_receipt(social_publish_database, post_id)
