from datetime import date

from services import operator_editorial


class Cursor:
    def __init__(self):
        self.statements = []
        self.rowcount = 1

    def execute(self, query, params=()):
        self.statements.append((query, params))


def _row():
    return {
        'id': 'item-1', 'plan_id': 'plan-1', 'business_id': 'business-1',
        'theme': 'Тема', 'goal': 'Бриф', 'scheduled_for': date(2026, 10, 20),
        'status': 'draft_generated', 'draft_text': 'Текст публикации для проверки.',
        'metadata_json': {'selected_channels': ['telegram']}, 'updated_at': 'v1',
        'content_type': 'news', 'source_kind': 'owner', 'source_ref': 'Бриф',
        'plan_status': 'active',
    }


def test_chat_editor_rejects_stale_content_version(monkeypatch):
    cursor = Cursor()
    monkeypatch.setattr(operator_editorial, 'authorize_actor', lambda *_args: None)
    monkeypatch.setattr(operator_editorial, '_items', lambda *_args, **_kwargs: [_row()])

    result = operator_editorial.update_item_fields(cursor, 'business-1', 'user-1', {
        'item_id': 'item-1', 'plan_id': 'plan-1', 'version': 'stale', 'scheduled_for': '2026-10-21',
    })

    assert result['status'] == 'blocked'
    assert cursor.statements == []


def test_chat_editor_saves_date_and_channels_on_the_shared_content_item(monkeypatch):
    cursor = Cursor()
    monkeypatch.setattr(operator_editorial, 'authorize_actor', lambda *_args: None)
    current = _row()
    updated = {**current, 'scheduled_for': date(2026, 10, 21), 'metadata_json': {'selected_channels': ['telegram', 'vk']}}
    calls = iter(([current], [updated]))
    monkeypatch.setattr(operator_editorial, '_items', lambda *_args, **_kwargs: next(calls))
    version = operator_editorial._version(current)

    result = operator_editorial.update_item_fields(cursor, 'business-1', 'user-1', {
        'item_id': 'item-1', 'plan_id': 'plan-1', 'version': version,
        'scheduled_for': '2026-10-21', 'selected_channels': ['telegram', 'vk'],
    })

    assert result['status'] == 'completed'
    assert result['selected_item']['plan_id'] == 'plan-1'
    assert any('UPDATE contentplanitems SET' in query for query, _params in cursor.statements)
    assert any('UPDATE social_posts SET scheduled_for' in query for query, _params in cursor.statements)


def test_invalid_channels_do_not_partially_save_text(monkeypatch):
    cursor = Cursor()
    current = _row()
    monkeypatch.setattr(operator_editorial, 'authorize_actor', lambda *_args: None)
    monkeypatch.setattr(operator_editorial, '_items', lambda *_args, **_kwargs: [current])
    result = operator_editorial.update_item_fields(cursor, 'business-1', 'user-1', {
        'item_id':'item-1', 'version':operator_editorial._version(current),
        'draft_text':'Новый текст', 'selected_channels':['unsupported'],
    })
    assert result['status'] == 'clarification_required'
    assert not cursor.statements
