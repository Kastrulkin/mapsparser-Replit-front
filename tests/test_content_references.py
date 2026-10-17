import pytest
from core.auth_context import AuthContext
from services import content_references
refs = content_references


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'file:///etc/passwd', 'http://localhost/',
    'http://127.0.0.1/', 'http://10.0.0.1/', 'https://example.internal/',
    'https://user:password@example.com/', 'https://example.com:8000/', 'https://[::1]/'])
def test_public_link_validation(url):
    with pytest.raises(ValueError):
        refs.public_url(url)


def test_url_normalization():
    assert refs.public_url('https://EXAMPLE.com/work#anchor') == 'https://example.com/work'
    assert refs.source_label({'source_url': 'https://t.me/s/vacges2'}) == '@vacges2'
    assert refs.source_label({'source_url': 'https://kodmerch.ru/hoodie'}) == 'КОДМЕРЧ'


def test_disabled_reference_and_private_scope(monkeypatch):
    monkeypatch.setattr(refs, 'settings', lambda *_: {'disabled_ids': ['default']})
    monkeypatch.setattr(refs, '_stored', lambda *_: [
        {'id': 'own', 'business_id': 'b', 'example_text': 'Показывать детали вещи',
         'metadata_json': {'url': 'https://example.com/', 'title': 'Свой пример', 'moderation': 'pending'}},
    ])
    result = refs.resolve_generation_references(None, 'b', 'apparel_manufacturing', [{'id': 'default'}])
    assert [r['id'] for r in result] == ['own']
    assert result[0]['scope'] == 'business'
    assert result[0]['source_type'] == 'editorial_guidance'


def test_no_business_keeps_existing_fixture_contract():
    assert refs.resolve_generation_references(None, '', '', [{'id': 'existing'}]) == [{'id': 'existing'}]


def test_extra_prompt_material_is_bounded_and_relevant(monkeypatch):
    monkeypatch.setattr(refs, 'settings', lambda *_: {})
    rows = [{'id': str(n), 'business_id': 'b', 'example_text': 'Общий пример изделия', 'metadata_json': {}} for n in range(10)]
    rows[0]['example_text'] = 'Худи: показать капюшон и манжеты'
    monkeypatch.setattr(refs, '_stored', lambda *_: rows)
    result = refs.resolve_generation_references(None, 'b', 'apparel_manufacturing', [], topic='Худи: капюшон')
    assert len(result) == 5 and result[0]['id'] == '0'


@pytest.mark.parametrize('auth', [AuthContext('u'), AuthContext('u', is_superadmin=True, session_kind='demo'),
    AuthContext('u', is_superadmin=True, impersonating=True)])
def test_non_moderator_does_not_query_admin_data(auth):
    assert not refs.moderator(None, auth)


def test_unprivileged_write_rejected(monkeypatch):
    from services import content_rules
    monkeypatch.setattr(content_rules, 'can_manage', lambda *_: False)
    with pytest.raises(PermissionError):
        refs.change_reference(None, 'b', AuthContext('u'), {'action': 'add'})
