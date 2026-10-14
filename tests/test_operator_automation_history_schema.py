from services import operator_agent_management as management


def test_status_reads_existing_queued_timestamp_and_preserves_response_name(monkeypatch):
    monkeypatch.setattr(management, '_authorized_actor', lambda *a, **k: {'id': 'owner'})
    monkeypatch.setattr(management, '_resolve_blueprint', lambda *a, **k: ({'id':'automation','name':'Pilot','status':'draft'}, None))
    monkeypatch.setattr(management, '_versions', lambda *a: ({}, {}))
    class Cursor:
        def execute(self, query, params):
            assert 'queued_at AS created_at' in query
            assert 'ORDER BY queued_at DESC' in query
            assert params == ('automation',)
        def fetchall(self):
            return [{'id':'run','status':'completed','created_at':'2026-10-14','error_text':None}]
    result = management.configure(Cursor(), business_id='business', user_id='owner', arguments={'operation':'status','blueprint_id':'automation'})
    assert result['status'] == 'completed'
    assert result['runs'][0]['created_at'] == '2026-10-14'
