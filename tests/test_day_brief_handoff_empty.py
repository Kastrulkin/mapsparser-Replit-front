"""An empty day must not expose a bot link without a saved briefing."""
import pytest
from services import operator_day_brief, operator_work_handoff

class EmptyCursor:
    description = []
    def execute(self, *args):
        pass
    def fetchone(self):
        return None


def test_owner_without_saved_brief_receives_null_draft(monkeypatch):
    monkeypatch.setattr(operator_day_brief, 'authorize', lambda *a, **kw: {'role': 'owner'})
    monkeypatch.setattr(operator_day_brief.work_journal, 'local_day', lambda *a: '2026-10-23')
    monkeypatch.setattr(operator_day_brief, 'members', lambda *a: [])
    monkeypatch.setattr(operator_day_brief, 'assignments', lambda *a, **kw: [])
    monkeypatch.setattr(operator_day_brief, 'delivery_states', lambda *a: [])
    result = operator_day_brief.overview(EmptyCursor(), business='business', user='owner')
    assert result['draft'] is None


@pytest.mark.parametrize('platform', ['telegram', 'max'])
@pytest.mark.parametrize('item_id', [None, '', '   '])
def test_missing_brief_id_is_rejected_before_storage(monkeypatch, platform, item_id):
    monkeypatch.setattr(operator_day_brief, 'authorize', lambda *a, **kw: None)
    with pytest.raises(ValueError, match='Сначала сохраните черновик планёрки'):
        operator_work_handoff.prepare_handoff(EmptyCursor(), user_id='owner', business_id='business', platform=platform,
            item_type='day_brief', item_id=item_id, request_id='c3f7c39a-6eb6-44e8-85c8-96a4db736a01')


def test_saved_brief_keeps_its_identifier(monkeypatch):
    monkeypatch.setattr(operator_day_brief, 'authorize', lambda *a, **kw: {'role': 'owner'})
    monkeypatch.setattr(operator_day_brief.work_journal, 'local_day', lambda *a: '2026-10-23')
    monkeypatch.setattr(operator_day_brief, 'members', lambda *a: [])
    monkeypatch.setattr(operator_day_brief, 'assignments', lambda *a, **kw: [])
    monkeypatch.setattr(operator_day_brief, 'delivery_states', lambda *a: [])
    monkeypatch.setattr(operator_day_brief, 'draft', lambda *a, **kw: {'id':'saved-brief','version':1})
    result = operator_day_brief.overview(EmptyCursor(), business='business', user='owner')
    assert result['draft'] == {'id':'saved-brief','version':1}

@pytest.mark.parametrize('platform,host', [('telegram','t.me'),('max','max.ru')])
def test_saved_brief_handoff_preserves_selected_context(monkeypatch, platform, host):
    monkeypatch.setenv('MAX_BOT_USERNAME','localos_max_bot')
    monkeypatch.setattr(operator_day_brief, 'authorize', lambda *a, **kw: None)
    monkeypatch.setattr(operator_day_brief, 'draft', lambda *a, **kw: {'id':'brief','version':2})
    class BoundCursor(EmptyCursor):
        def fetchone(self):
            return {'telegram_id':'123','max_id':'456'}
    stored=[]
    monkeypatch.setattr(operator_work_handoff,'get_or_create_operator_conversation',lambda *a,**kw:{'id':'8c4c3681-3218-41c9-b561-21dab0bfa490'})
    monkeypatch.setattr(operator_work_handoff,'set_operator_pending_context',lambda c,i,p:stored.append(p))
    result=operator_work_handoff.prepare_handoff(BoundCursor(),user_id='owner',business_id='business',platform=platform,
        item_type='day_brief',item_id='brief',request_id='c3f7c39a-6eb6-44e8-85c8-96a4db736a01')
    assert result['url'].startswith('https://'+host+'/')
    assert result['selected_day_brief']=={'item_id':'brief','version':'2'}
    assert stored==[{'capability':'work.day_brief','selected_day_brief':{'item_id':'brief','version':'2'}}]
    assert 'screen=work_journal' in result['return_url']


def test_other_owners_brief_is_still_inaccessible(monkeypatch):
    monkeypatch.setattr(operator_day_brief,'authorize',lambda *a,**kw:None)
    monkeypatch.setattr(operator_day_brief,'draft',lambda *a,**kw:{})
    with pytest.raises(PermissionError,match='Планёрка недоступна'):
        operator_work_handoff.work_selection(EmptyCursor(),item_type='day_brief',user_id='owner',business_id='business',item_id='another-owner-brief')
