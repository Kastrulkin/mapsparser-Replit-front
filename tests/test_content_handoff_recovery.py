import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services import content_publish_notifications as notifications


class AssetCursor:
    description = []

    def __init__(self, row=None):
        self.row = row
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))

    def fetchone(self):
        return self.row


def test_id_only_photo_is_loaded_from_business_library():
    cursor = AssetCursor({"id": "photo", "storage_key": "s3://bucket/photo.jpg",
                          "versions_json": {"original": {"mime_type": "image/jpeg"}},
                          "metadata_json": {"upload": {"original_name": "work.jpg"}}})
    result = notifications._selected_photos(cursor, {
        "business_id": "branch", "media_json": [{"photo_asset_id": "photo"}]})
    assert result[0]["storage_path"] == "s3://bucket/photo.jpg"
    assert result[0]["original_name"] == "work.jpg"
    sql, params = cursor.queries[0]
    assert params == ("photo", "branch")
    assert "business_id IN" in sql and "library.id = target.id" in sql
    assert "category IS DISTINCT FROM 'document'" in sql
    assert "disk_import_available" in sql


def test_missing_or_foreign_id_never_falls_back_to_another_photo():
    cursor = AssetCursor()
    assert notifications._selected_photos(cursor, {
        "business_id": "branch", "media_json": [{"photo_asset_id": "foreign"}]}) == []
    assert len(cursor.queries) == 1
    assert notifications._selected_photos(cursor, {
        "media_json": [{"photo_asset_id": "foreign"}]}) == []


def test_existing_full_photo_identity_is_stable():
    cursor = AssetCursor()
    photo = {"id": "p", "storage_path": "s3://bucket/p.jpg", "mime_type": "image/jpeg"}
    resolved = notifications._selected_photos(cursor, {"business_id": "b", "media_json": [photo]})
    assert resolved == [notifications._normalize_photo(photo)]
    assert not cursor.queries


def completion_error():
    # Exercise the small pure classification function without initializing the
    # queue facade's unrelated integrations or connecting to any database.
    source = Path("src/services/agent_run_queue.py").read_text()
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "_compiled_completion_error")
    namespace = {}
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), function], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "completion-policy", "exec"), namespace)
    return namespace["_compiled_completion_error"]


@pytest.mark.parametrize("status", ["needs_attention", "uncertain", "blocked", "failed"])
def test_delivery_failure_is_not_a_completed_run(status):
    classify = completion_error()
    assert classify({"handoff": {"status": status}}) == "compiled_content_handoff_needs_attention"
    assert classify({"handoff": {"result": {"status": status}}}) == "compiled_content_handoff_needs_attention"


def test_success_empty_and_unrelated_compiled_results_are_unchanged():
    classify = completion_error()
    for result in ({}, {"requests": []}, {"handoff": {"status": "completed"}},
                   {"handoff": {"result": {"status": "nothing_due"}}}):
        assert classify(result) == ""
    assert classify({}, "explicit failure") == "explicit failure"


def test_next_day_10am_moscow_boundary():
    item = {"scheduled_for": datetime(2026, 10, 20, tzinfo=timezone.utc),
            "business_timezone": "Europe/Moscow", "lead_days": "1", "handoff_time": "10:00"}
    assert not notifications.handoff_due(item, datetime(2026, 10, 19, 6, 59, tzinfo=timezone.utc))
    assert notifications.handoff_due(item, datetime(2026, 10, 19, 7, 0, tzinfo=timezone.utc))
    assert not notifications.handoff_due(item, datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc))


@pytest.mark.parametrize('scope,requested', [({}, 'other'), ({'compiled_dispatch': {'run_id': 'run'}}, 'post')])
def test_one_time_delivery_cannot_change_another_post_or_compiled_scope(monkeypatch, scope, requested):
    cursor = AssetCursor({'id': 'post', 'status': 'approved', 'publish_mode': 'manual'})
    connection = type('Connection', (), {'cursor': lambda self: cursor})()
    monkeypatch.setattr(notifications, 'handoff_plan_current', lambda *_: True)
    assert notifications.claim_handoff_part(connection, {'id': 'post'}, 'photo',
        compiled_scope=scope, one_time_post_id=requested) == {'status': 'paused'}


@pytest.fixture
def sender_state(monkeypatch):
    from services import operator_audio, business_input_settings
    photo = {'id': 'photo', 'storage_path': 's3://bucket/photo.jpg', 'public_url': '',
             'mime_type': 'image/jpeg', 'original_name': 'work.jpg'}
    post = {'id': 'post', 'business_id': 'branch', 'platform': 'telegram', 'status': 'approved',
            'publish_mode': 'manual', 'scheduled_for': datetime(2026, 10, 16, tzinfo=timezone.utc),
            'platform_text': 'Approved text', 'metadata_json': {}}

    class Cursor:
        description = []

        def execute(self, sql, params=None):
            if sql.startswith('SELECT * FROM social_posts'):
                self.row = post.copy()
            elif 'JOIN users' in sql:
                self.row = {'user_id': params[0], 'telegram_id': 'chat-' + params[0], 'is_active': True}
            elif sql.startswith('SELECT metadata_json'):
                self.row = {'metadata_json': post['metadata_json']}
            elif sql.startswith('UPDATE social_posts SET metadata_json'):
                post['metadata_json'] = json.loads(params[0])
                self.row = None
            else:
                raise AssertionError(sql)

        def fetchone(self):
            return self.row

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *_a, **_k: None)
    monkeypatch.setattr(business_input_settings, 'resolve', lambda *_: {'timezone': 'Europe/Moscow'})
    monkeypatch.setattr(notifications, 'handoff_plan_current', lambda *_: True)
    monkeypatch.setattr(notifications, 'handoff_kit_complete', lambda *_a, **_k: True)
    monkeypatch.setattr(notifications, '_selected_photos', lambda *_: [photo])
    monkeypatch.setattr(notifications, 'handoff_due', lambda *_: False)

    def for_user(user):
        scope = {'business_id': 'branch', 'user_id': user, 'telegram_id': 'chat-' + user,
                 'scope_type': 'business', 'scope_id': 'branch', 'required_platforms': ['telegram'],
                 'lead_days': '1', 'handoff_time': '10:00'}
        item = {**post, **scope, 'selected_photos': [photo], 'selected_photo': photo}
        item['revision'] = notifications.handoff_revision(item)
        return item, scope

    return Connection(), post, for_user


def test_two_recipients_are_independent_and_replay_sends_nothing(sender_state):
    connection, post, for_user = sender_state
    calls = []
    for user in ['irina', 'alex', 'irina', 'alex']:
        item, scope = for_user(user)
        assert notifications.deliver_content_publish_handoff(connection, item,
            send_photo=lambda *_: calls.append((user, 'photo')) or {'success': True, 'message_id': len(calls)},
            send_text=lambda *_a, **_k: calls.append((user, 'text')) or {'success': True, 'message_id': len(calls)},
            compiled_scope=scope, one_time_post_id='post') == 'sent'
    assert calls == [('irina', 'photo'), ('irina', 'text'), ('alex', 'photo'), ('alex', 'text')]
    assert post['status'] == 'approved'


def test_partial_send_does_not_repeat_successful_photo(sender_state):
    connection, post, for_user = sender_state
    item, scope = for_user('irina')
    assert notifications.deliver_content_publish_handoff(connection, item,
        send_photo=lambda *_: {'success': True, 'message_id': 1},
        send_text=lambda *_a, **_k: {'success': False, 'message_id': 0, 'publish_outcome': 'not_attempted'},
        compiled_scope=scope, one_time_post_id='post') == 'needs_attention'
    assert notifications.deliver_content_publish_handoff(connection, item,
        send_photo=lambda *_: pytest.fail('Photo must not be repeated'),
        send_text=lambda *_a, **_k: pytest.fail('Retry backoff must be respected'),
        compiled_scope=scope, one_time_post_id='post') == 'retry_wait'
    post['metadata_json']['staff_handoff']['telegram_deliveries']['irina']['parts']['text:0']['attempted_at'] = (
        datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    assert notifications.deliver_content_publish_handoff(connection, item,
        send_photo=lambda *_: pytest.fail('Photo must not be repeated'),
        send_text=lambda *_a, **_k: {'success': True, 'message_id': 2},
        compiled_scope=scope, one_time_post_id='post') == 'sent'


def test_unknown_outcome_is_not_retried(sender_state):
    connection, _, for_user = sender_state
    item, scope = for_user('irina')
    assert notifications.deliver_content_publish_handoff(connection, item,
        send_photo=lambda *_: {'success': False, 'message_id': 0, 'publish_outcome': 'uncertain'},
        send_text=lambda *_a, **_k: pytest.fail('No text after unknown photo outcome'),
        compiled_scope=scope, one_time_post_id='post') == 'needs_attention'
    assert notifications.deliver_content_publish_handoff(connection, item,
        send_photo=lambda *_: pytest.fail('Unknown send must not be repeated'),
        send_text=lambda *_a, **_k: pytest.fail('Unknown send must not be repeated'),
        compiled_scope=scope, one_time_post_id='post') == 'uncertain'


def test_normal_scheduler_does_not_get_manual_date_override(sender_state):
    connection, _, for_user = sender_state
    item, scope = for_user('irina')
    assert notifications.deliver_content_publish_handoff(connection, item,
        send_photo=lambda *_: pytest.fail('Outside date window'),
        send_text=lambda *_a, **_k: pytest.fail('Outside date window'),
        compiled_scope=scope) == 'stale'
