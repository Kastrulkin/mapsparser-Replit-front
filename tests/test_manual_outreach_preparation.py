import pytest
from services import contact_intelligence_service


class Cursor:
    def __init__(self,latest=None):self.latest=latest;self.sql=[];self.params=[]
    def execute(self,sql,params=None):self.sql.append(sql);self.params.append(params)
    def fetchone(self):
        if 'INSERT INTO' in self.sql[-1]:return {'id':'job','status':'queued'}
        return self.latest


def test_background_force_cannot_create_or_restart_job():
    for latest in (None,{'id':'old','status':'ready'},{'id':'old','status':'failed'}):
        cursor=Cursor(latest)
        result=contact_intelligence_service.enqueue_enrichment_job(cursor,'workstream',force=True)
        assert result['reason']=='manual_request_required'
        assert not any('INSERT' in x or 'UPDATE' in x for x in cursor.sql)


def test_explicit_manual_command_is_audited_and_duplicate_click_reused():
    cursor=Cursor()
    result=contact_intelligence_service.enqueue_enrichment_job(cursor,'workstream',requested_by_user_id='owner')
    assert result['id']=='job'
    authorization=cursor.params[-1][-1].adapted['generation_request']
    assert authorization['actor_user_id']=='owner'
    assert authorization['source']=='user_request'
    cursor=Cursor({'id':'job','status':'queued','result_json':{'generation_request':authorization}})
    assert contact_intelligence_service.enqueue_enrichment_job(cursor,'workstream',force=True,requested_by_user_id='owner')['reused']
    assert not any('INSERT' in x for x in cursor.sql)


def test_executor_rejects_legacy_job_before_reading_or_generating():
    cursor=Cursor()
    with pytest.raises(contact_intelligence_service.PersonalizationGenerationError):
        contact_intelligence_service.process_enrichment_job(cursor,{'id':'old'})
    assert cursor.sql==[]


def test_claim_ignores_unapproved_legacy_queue():
    cursor=Cursor()
    assert contact_intelligence_service.claim_next_enrichment_job(cursor) is None
    assert "job.result_json->'generation_request'->>'source' = 'user_request'" in cursor.sql[0]


def test_contact_sync_never_queues_generation(monkeypatch):
    monkeypatch.setattr(contact_intelligence_service,'exclude_public_channel_contacts',lambda *_:[])
    monkeypatch.setattr(contact_intelligence_service,'legacy_contact_candidates',lambda *_:[])
    monkeypatch.setattr(contact_intelligence_service,'upsert_contact_points',lambda *_:1)
    cursor=Cursor()
    result=contact_intelligence_service.sync_parsed_lead_contacts(cursor,{'id':'lead'})
    assert result=={'contacts_saved':1,'jobs_queued':0}
    assert cursor.sql==[]


def test_monitoring_has_no_draft_enqueue_path():
    import ast
    from pathlib import Path
    tree=ast.parse(Path('src/services/knowledge_public_telegram.py').read_text())
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='enqueue_enrichment_job' for n in ast.walk(tree))


def test_contact_search_preserves_old_drafts_and_never_calls_ai(monkeypatch):
    service=contact_intelligence_service
    grant={'source':'user_request','actor_user_id':'owner','workstream_id':'workstream','prepare_draft':False}
    class ResearchCursor(Cursor):
        def fetchone(self):
            if 'SELECT ws.*' in self.sql[-1]:
                return {'id':'workstream','lead_id':'lead','workstream_type':'localos_sales','selected_contact_point_id':'contact'}
            return {'id':'job','status':'ready','result_json':self.params[-1][0].adapted}
    monkeypatch.setattr(service,'_resolve_sender_mode',lambda *_:'localos')
    monkeypatch.setattr(service,'legacy_contact_candidates',lambda *_:[])
    monkeypatch.setattr(service,'_lead_website_identity_mismatched',lambda *_:False)
    monkeypatch.setattr(service,'collect_public_website_intelligence',lambda *_:([],[],[]))
    monkeypatch.setattr(service,'exclude_public_channel_contacts',lambda *_:[])
    monkeypatch.setattr(service,'upsert_contact_points',lambda *_:0)
    monkeypatch.setattr(service,'verify_contact_points',lambda *_:None)
    monkeypatch.setattr(service,'_select_best_contact',lambda *_:{'id':'contact','owner_type':'person','verification_status':'verified','contact_type':'email'})
    monkeypatch.setattr(service,'_sync_legacy_best_contact',lambda *_:None)
    monkeypatch.setattr(service,'upsert_native_research',lambda *_:{})
    def forbidden(*_,**__):pytest.fail('Contact search must not generate an outreach draft')
    monkeypatch.setattr(service,'generate_personalized_sequence',forbidden)
    cursor=ResearchCursor()
    result=service.process_enrichment_job(cursor,{'id':'job','workstream_id':'workstream','result_json':{'generation_request':grant}})
    assert result['result_json']['draft_prepared'] is False
    assert not any('outreachmessagedrafts' in sql for sql in cursor.sql)
