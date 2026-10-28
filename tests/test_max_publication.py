"""Provider boundaries: immutable approval, complete media and uncertain writes."""
import pytest
from services import max_publication
from services.max_transport import MaxTransportError


@pytest.fixture
def publishing(monkeypatch):
    from services.social_posts import approval_binding, media_delivery
    monkeypatch.setenv('MAX_ENABLED', 'true')
    monkeypatch.setenv('MAX_PUBLISH_ENABLED', 'true')
    for name in ('snapshot_is_well_formed', 'snapshot_is_sendable', 'current_snapshot_matches'):
        monkeypatch.setattr(approval_binding, name, lambda *args: True)
    monkeypatch.setattr(approval_binding, 'frozen_external_account', lambda *args: (
        {'source': 'max_bot', 'external_id': '-123'}, {'sender': {'bot_id': '1'}}))
    monkeypatch.setattr(approval_binding, '_account_auth_data', lambda *args: {'bot_token': 'synthetic'})
    monkeypatch.setattr(media_delivery, '_approved_media_assets', lambda *args: [])
    monkeypatch.setattr(max_publication, 'probe_channel', lambda *args: {'bot_id': '1', 'chat_id': '-123'})
    class Transport:
        def __init__(self, *args): pass
        calls = []
        error = None
        def call(self, method, path, **kwargs):
            self.calls.append((method, path, kwargs))
            if self.error: raise self.error
            return {'message': {'body': {'mid': 'accepted-mid'}, 'url': 'https://max.ru/message'}}
    monkeypatch.setattr(max_publication, 'MaxTransport', Transport)
    return Transport, approval_binding, media_delivery


def test_publication_returns_provider_evidence_and_exact_target(publishing):
    transport, _, _ = publishing
    result = max_publication.publish_max_post(None, {'platform_text': 'Approved'}, {})
    assert result['publish_outcome'] == 'accepted'
    assert result['provider_post_id'] == 'accepted-mid'
    assert transport.calls == [('POST', '/messages', {'params': {'chat_id': '-123'}, 'body': {'text': 'Approved', 'attachments': []}})]


def test_changed_destination_or_content_after_upload_never_posts(publishing, monkeypatch):
    transport, binding, media = publishing
    monkeypatch.setattr(media, '_approved_media_assets', lambda *args: [{'id': 'one'}])
    checks = iter([True, False])
    monkeypatch.setattr(binding, 'current_snapshot_matches', lambda *args: next(checks))
    monkeypatch.setattr(max_publication, 'upload_media', lambda *args: {'type': 'image', 'payload': {'token': 'uploaded'}})
    result = max_publication.publish_max_post(None, {'platform_text': 'Approved'}, {})
    assert result['publish_outcome'] == 'not_attempted'
    assert not transport.calls


def test_media_failure_cannot_publish_a_partial_set(publishing, monkeypatch):
    transport, _, media = publishing
    monkeypatch.setattr(media, '_approved_media_assets', lambda *args: [{'id': 'one'}, {'id': 'two'}])
    def upload(_, asset):
        if asset['id'] == 'two': raise ValueError('unavailable')
        return {'type': 'image', 'payload': {'token': 'uploaded'}}
    monkeypatch.setattr(max_publication, 'upload_media', upload)
    result = max_publication.publish_max_post(None, {'platform_text': 'Approved'}, {})
    assert result['publish_outcome'] == 'not_attempted'
    assert not transport.calls


def test_timeout_is_uncertain_and_never_retried(publishing):
    transport, _, _ = publishing
    transport.error = MaxTransportError('max_connection_failed', uncertain=True)
    result = max_publication.publish_max_post(None, {'platform_text': 'Approved'}, {})
    assert result['publish_outcome'] == 'uncertain'
    assert len(transport.calls) == 1


def test_revoked_rights_before_send_never_posts(publishing, monkeypatch):
    transport, _, _ = publishing
    count = []
    def probe(*args):
        count.append(1)
        if len(count) == 2: raise PermissionError()
        return {'bot_id': '1', 'chat_id': '-123'}
    monkeypatch.setattr(max_publication, 'probe_channel', probe)
    result = max_publication.publish_max_post(None, {'platform_text': 'Approved'}, {})
    assert result['publish_outcome'] == 'not_attempted'
    assert not transport.calls


@pytest.mark.parametrize('channel,allowed',[('-123',True),('-456',False)])
def test_limited_rollout_only_allows_exact_channel(monkeypatch,channel,allowed):
    monkeypatch.setenv('MAX_ENABLED','true')
    monkeypatch.setenv('MAX_PUBLISH_ENABLED','false')
    monkeypatch.setenv('MAX_PUBLISH_CHAT_IDS','-123')
    assert max_publication.max_publish_enabled(channel) is allowed


def test_limited_rollout_rejects_other_target_before_provider(publishing,monkeypatch):
    transport,_,_=publishing
    monkeypatch.setenv('MAX_PUBLISH_ENABLED','false')
    monkeypatch.setenv('MAX_PUBLISH_CHAT_IDS','-456')
    result=max_publication.publish_max_post(None,{'platform_text':'Approved'}, {})
    assert result['publish_outcome']=='not_attempted' and not transport.calls
