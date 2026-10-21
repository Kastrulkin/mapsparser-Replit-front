import uuid
from datetime import datetime, timezone
import pytest
from services import operator_partner_work, operator_audio, operator_work_handoff

USER = 'user'
BUSINESS = 'business'
LEAD = str(uuid.uuid4())


class Cursor:
    def __init__(self, lead=None, drafts=None):
        self.lead = lead
        self.drafts = drafts or []
        self.query = ''
        self.calls = []
    def execute(self, query, params=()):
        self.query = query; self.calls.append((query, params))
    def fetchone(self): return self.lead
    def fetchall(self): return ([self.lead] if self.lead else []) if 'JOIN lead_workstreams' in self.query else self.drafts


def lead():
    return {'id': LEAD, 'business_id': BUSINESS, 'name': 'Детская студия', 'selected_channel': 'email',
            'workstream_id': 'workstream', 'workstream_status': 'new', 'workstream_updated_at': None, 'status': 'new', 'email': 'public@example.test', 'updated_at': datetime(2026, 10, 17, tzinfo=timezone.utc)}


@pytest.fixture
def allowed(monkeypatch):
    def authorize(cursor, user_id, business_id, **kwargs):
        if user_id != USER or business_id != BUSINESS: raise PermissionError('Denied')
        assert kwargs == {'require_write': True, 'check_subscription': False}
        return {}, {'capabilities': ['partnerships']}
    monkeypatch.setattr(operator_audio, 'authorize_actor', authorize)


def test_selection_uses_business_workstream_and_does_not_copy_contacts(allowed):
    cursor = Cursor(lead())
    selected = operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD,
        expected_updated_at='2026-10-17T00:00:00.000Z')
    assert cursor.calls[0][1] == (LEAD, BUSINESS)
    assert "ws.client_business_id=%s" in cursor.calls[0][0]
    assert "ws.workstream_type='client_partnership'" in cursor.calls[0][0]
    assert selected['name'] == 'Детская студия'
    assert 'email' not in selected
    before = selected['version']
    cursor.lead['email'] = 'changed@example.test'
    assert operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD)['version'] != before


def test_denied_tier_and_foreign_or_missing_lead_never_return_details(allowed, monkeypatch):
    with pytest.raises(PermissionError): operator_partner_work.partner_selection(Cursor(lead()), user_id='other', business_id=BUSINESS, item_id=LEAD)
    with pytest.raises(PermissionError): operator_partner_work.partner_selection(Cursor(), user_id=USER, business_id=BUSINESS, item_id=LEAD)
    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *a, **kw: ({}, {'capabilities': ['operator']}))
    cursor = Cursor(lead())
    with pytest.raises(PermissionError): operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD)
    assert cursor.calls == []


def test_preparing_returns_confirmation_only_and_send_requires_review(allowed):
    cursor = Cursor(lead())
    selection = operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD)
    result, pending = operator_partner_work.route(cursor, user_id=USER, business_id=BUSINESS, message='Подготовь первое письмо', selected=selection)
    assert result['status'] == 'approval_required'
    assert result['approval']['envelope']['payload'] == {'lead_id': LEAD, 'version': selection['version']}
    assert pending['selected_partner'] == selection
    assert not any('INSERT' in query or 'UPDATE' in query for query, _ in cursor.calls)
    result, _ = operator_partner_work.route(cursor, user_id=USER, business_id=BUSINESS, message='Отправь письмо', selected=selection)
    assert 'отдельно подтвердите' in result['chat_response']
    assert result['external_writes_performed'] is False


def test_current_draft_is_shown_and_stale_read_refreshes_but_stale_write_is_denied(allowed):
    cursor = Cursor(lead(), [{'id': 'draft', 'edited_text': 'Проверенный текст предложения.', 'status': 'edited', 'channel': 'email'}])
    selection = operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD)
    cursor.lead['status'] = 'draft_ready'
    result, pending = operator_partner_work.route(cursor, user_id=USER, business_id=BUSINESS, message='Покажи письмо', selected=selection)
    assert 'Проверенный текст предложения.' in result['chat_response']
    assert pending['selected_partner']['version'] != selection['version']
    with pytest.raises(ValueError): operator_partner_work.route(cursor, user_id=USER, business_id=BUSINESS, message='Подготовь первое письмо', selected=selection)


def test_cancel_rejects_only_this_business_user_and_conversation(allowed):
    cursor = Cursor(lead())
    selection = operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD)
    result, pending = operator_partner_work.route(cursor, user_id=USER, business_id=BUSINESS, message='Отмена', selected=selection, conversation_id='conversation')
    assert result['status'] == 'cancelled' and pending == {}
    assert cursor.calls[-1][1] == (BUSINESS, USER, 'conversation')
    assert "capability='partnerships.selected_draft'" in cursor.calls[-1][0]


def test_unknown_handoff_type_is_rejected():
    with pytest.raises(ValueError): operator_work_handoff.work_selection(Cursor(), item_type='other')


def test_legacy_flask_date_accepts_same_second_but_rejects_stale_card(allowed):
    row = lead()
    row['updated_at'] = row['updated_at'].replace(microsecond=123456)
    cursor = Cursor(row)
    selected = operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD,
        expected_updated_at='Sat, 17 Oct 2026 00:00:00 GMT')
    assert selected['item_id'] == LEAD
    with pytest.raises(ValueError):
        operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD,
            expected_updated_at='Fri, 16 Oct 2026 00:00:00 GMT')


def test_queue_preserves_actor_on_deployed_queue_contract(allowed, monkeypatch):
    from services import contact_intelligence_service, lead_workstream_service
    cursor = Cursor(lead())
    cursor.connection = object()
    monkeypatch.setattr(lead_workstream_service, 'resolve_workstream', lambda *args, **kwargs: {'id': 'workstream'})
    captured = {}
    def enqueue(cursor, workstream_id, *, force=False, allow_paid_enrichment=False, requested_by_user_id=''):
        captured.update(actor=requested_by_user_id, paid=allow_paid_enrichment, workstream=workstream_id)
        return {'id': 'job', 'status': 'queued'}
    monkeypatch.setattr(contact_intelligence_service, 'enqueue_enrichment_job', enqueue)
    result = operator_partner_work.queue_first_note(cursor, user_id=USER, business_id=BUSINESS, lead_id=LEAD)
    assert result['id'] == 'job'
    assert captured == {'actor': USER, 'paid': False, 'workstream': 'workstream'}


def test_partner_read_uses_human_channel_and_draft_status_labels(allowed):
    cursor = Cursor(lead(), [{'id': 'draft', 'generated_text': 'Точный текст', 'status': 'generated', 'channel': 'email'}])
    cursor.lead['selected_channel'] = 'manual'
    cursor.lead['status'] = 'imported'
    selection = operator_partner_work.partner_selection(cursor, user_id=USER, business_id=BUSINESS, item_id=LEAD)
    result, _ = operator_partner_work.route(cursor, user_id=USER, business_id=BUSINESS, message='Покажи письмо', selected=selection)
    text = result['chat_response']
    assert 'Канал нужно выбрать' in text and 'Добавлен' in text and 'Эл. почта · Черновик' in text
    assert not any(marker in text for marker in ['generated', 'imported', 'manual'])
