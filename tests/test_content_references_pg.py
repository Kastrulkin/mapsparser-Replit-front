"""Opt-in integration test. TEMP tables shadow public tables; always rollback.

No model calls, provider writes, production fixture rows or schema migrations.
"""
import os
import pytest
from core.auth_context import AuthContext
from services import content_references
refs = content_references


def test_private_moderated_references_and_exclusions_pg(monkeypatch):
    if os.environ.get('CONTENT_REFERENCE_TEMP_PG_TEST') != '1':
        pytest.skip('explicit TEMP-table PostgreSQL test required')
    from database_manager import DatabaseManager
    from services import content_rules
    db = DatabaseManager()
    c = db.conn.cursor()
    try:
        c.execute('CREATE TEMP TABLE users(id TEXT PRIMARY KEY,is_active BOOLEAN,is_superadmin BOOLEAN) ON COMMIT DROP')
        c.execute('CREATE TEMP TABLE businesses(id TEXT PRIMARY KEY,name TEXT,business_type TEXT,industry TEXT) ON COMMIT DROP')
        c.execute('''CREATE TEMP TABLE userexamples(id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,
            example_type TEXT,example_text TEXT,origin TEXT,quality_status TEXT,metadata_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()) ON COMMIT DROP''')
        c.execute('''CREATE TEMP TABLE content_voice_profiles(business_id TEXT PRIMARY KEY,preferences_json JSONB,
            created_by TEXT,version INT DEFAULT 1,updated_at TIMESTAMPTZ DEFAULT NOW()) ON COMMIT DROP''')
        c.execute("INSERT INTO users VALUES('owner',TRUE,FALSE),('admin',TRUE,TRUE)")
        c.execute("INSERT INTO businesses VALUES('a','Фабрика A','Пошив брендированной одежды','apparel_manufacturing'),('b','Фабрика B','Пошив брендированной одежды','apparel_manufacturing'),('school','Школа','school','education_children')")
        monkeypatch.setattr(content_rules, 'can_manage', lambda *_: True)
        owner = AuthContext('owner')
        admin = AuthContext('admin', is_superadmin=True)
        payload = {'action': 'add', 'title': 'Образец одежды', 'url': 'https://example.com/work',
                   'technique': 'Показать реальную вещь и детали отделки', 'submit_for_review': True, 'request_id': 'repeat-safe'}
        refs.change_reference(c, 'a', owner, payload)
        refs.change_reference(c, 'a', owner, payload)
        c.execute('SELECT count(*) count FROM userexamples')
        assert c.fetchone()['count'] == 1
        own = refs.list_references(c, 'a', owner)
        item = next(r for r in own['items'] if r.get('owned'))
        assert item['moderation'] == 'pending'
        assert not own['can_moderate'] and own['pending'] == []
        assert all(r['id'] != item['id'] for r in refs.list_references(c, 'b', owner)['items'])
        assert any(r['id'] == item['id'] for r in refs.resolve_generation_references(c, 'a', 'apparel_manufacturing', []))
        assert refs.resolve_generation_references(c, 'b', 'apparel_manufacturing', []) == []
        with pytest.raises(PermissionError):
            refs.change_reference(c, 'a', owner, {'action': 'moderate_approve', 'id': item['id'], 'expected_version': 1, 'note': 'Проверено'})
        assert len(refs.list_references(c, 'b', admin)['pending']) == 1
        refs.change_reference(c, 'a', admin, {'action': 'moderate_approve', 'id': item['id'], 'expected_version': 1, 'note': 'Источник и редакционный приём проверены'})
        shared = refs.list_references(c, 'b', owner)
        assert any(r['id'] == item['id'] and r['scope'] == 'industry' for r in shared['items'])
        assert all(r['id'] != item['id'] for r in refs.list_references(c, 'school', owner)['items'])
        with pytest.raises(refs.ReferenceConflict):
            refs.change_reference(c, 'a', admin, {'action': 'moderate_approve', 'id': item['id'], 'expected_version': 1, 'note': 'Повторное решение'})
        default = refs.defaults('apparel_manufacturing')[0]
        refs.change_reference(c, 'a', owner, {'action': 'disable', 'id': default['id'], 'expected_version': 0})
        assert all(r['id'] != default['id'] for r in refs.resolve_generation_references(c, 'a', 'apparel_manufacturing', [default]))
        assert any(r['id'] == default['id'] for r in refs.resolve_generation_references(c, 'b', 'apparel_manufacturing', [default]))
        with pytest.raises(refs.ReferenceConflict):
            refs.change_reference(c, 'a', owner, {'action': 'enable', 'id': default['id'], 'expected_version': 0})
        refs.change_reference(c, 'a', owner, {'action': 'enable', 'id': default['id'], 'expected_version': 1})
        assert any(r['id'] == default['id'] for r in refs.resolve_generation_references(c, 'a', 'apparel_manufacturing', [default]))
        with pytest.raises(PermissionError):
            refs.change_reference(c, 'a', owner, {'action': 'remove', 'id': default['id'], 'expected_version': 2})
        refs.change_reference(c, 'a', owner, {'action': 'remove', 'id': item['id'], 'expected_version': 2})
        assert all(r['id'] != item['id'] for r in refs.resolve_generation_references(c, 'a', 'apparel_manufacturing', []))
        assert any(r['id'] == item['id'] for r in refs.resolve_generation_references(c, 'b', 'apparel_manufacturing', []))
    finally:
        db.conn.rollback()
        db.close()
