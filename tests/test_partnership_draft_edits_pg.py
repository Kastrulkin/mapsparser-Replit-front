import pytest
from tests.test_operator_voice_pg import pg
from services import operator_audio
from services.partnership_draft_edits import save_draft
from services.outreach_draft_review import draft_review_digest

@pytest.fixture
def drafts(pg,monkeypatch):
    conn,c=pg
    c.execute('CREATE TABLE prospectingleads(id TEXT PRIMARY KEY,business_id TEXT,intent TEXT,email TEXT,selected_channel TEXT)')
    c.execute("INSERT INTO prospectingleads VALUES('lead','b','partnership_outreach','public@example.test','email')")
    c.execute('CREATE TABLE lead_workstreams(id TEXT PRIMARY KEY,client_business_id TEXT,workstream_type TEXT)')
    c.execute("INSERT INTO lead_workstreams VALUES('work','b','client_partnership')")
    c.execute("CREATE TABLE outreachmessagedrafts(id TEXT PRIMARY KEY,lead_id TEXT,workstream_id TEXT,status TEXT,channel TEXT,generated_text TEXT,edited_text TEXT,approved_text TEXT,updated_at TIMESTAMPTZ DEFAULT NOW(),learning_note_json JSONB)")
    c.execute("INSERT INTO outreachmessagedrafts(id,lead_id,workstream_id,status,channel,generated_text) VALUES('draft','lead','work','generated','email','Original')")
    c.execute('CREATE TABLE IF NOT EXISTS agent_action_ledger(id TEXT PRIMARY KEY,business_id TEXT,action_type TEXT,capability TEXT,risk_level TEXT,status TEXT,input_summary TEXT,metadata_json JSONB)')
    def authorize(cursor,user,business,**kwargs):
        if user!='manager' or business!='b':raise PermissionError('Denied')
        return {'role':'business_user'}, {'capabilities':['partnerships']}
    monkeypatch.setattr(operator_audio,'authorize_actor',authorize)
    return conn,c

def digest(c):
    c.execute('SELECT d.*,l.email,l.selected_channel FROM outreachmessagedrafts d JOIN prospectingleads l ON l.id=d.lead_id')
    row=dict(c.fetchone());row['canonical_review']=None
    return draft_review_digest(row)

def test_save_keeps_draft_unapproved_and_audits_actor(drafts):
    conn,c=drafts
    before=digest(c)
    result=save_draft(c,business_id='b',user_id='manager',draft_id='draft',text='Reviewed letter',expected_digest=before)
    assert result['status']=='generated'
    c.execute('SELECT edited_text,approved_text,status FROM outreachmessagedrafts')
    assert c.fetchone()=={'edited_text':'Reviewed letter','approved_text':None,'status':'generated'}
    c.execute('SELECT metadata_json FROM agent_action_ledger')
    assert c.fetchone()['metadata_json']['user_id']=='manager'
    with pytest.raises(ValueError,match='изменился'):
        save_draft(c,business_id='b',user_id='manager',draft_id='draft',text='Stale',expected_digest=before)

@pytest.mark.parametrize('status',['approved','sent','delivered'])
def test_approved_and_sent_text_cannot_be_changed(drafts,status):
    _,c=drafts;c.execute('UPDATE outreachmessagedrafts SET status=%s',(status,))
    with pytest.raises(ValueError,match='утверждено'):
        save_draft(c,business_id='b',user_id='manager',draft_id='draft',text='New',expected_digest=digest(c))

def test_foreign_workstream_and_staff_are_denied(drafts):
    _,c=drafts
    with pytest.raises(PermissionError):save_draft(c,business_id='b',user_id='staff',draft_id='draft',text='New',expected_digest=digest(c))
    c.execute("UPDATE lead_workstreams SET client_business_id='other'")
    with pytest.raises(PermissionError):save_draft(c,business_id='b',user_id='manager',draft_id='draft',text='New',expected_digest=digest(c))

@pytest.mark.parametrize('mail',['jur@example.test','legal@example.test','privacy@example.test'])
def test_service_mailboxes_not_selected_for_partnerships(pg,mail):
    from services.contact_intelligence_service import _select_best_contact
    _,c=pg
    c.execute('CREATE TABLE lead_contact_points(id TEXT,lead_id TEXT,contact_type TEXT,value TEXT,verification_status TEXT,stale_after TIMESTAMPTZ,owner_type TEXT,confidence FLOAT,updated_at TIMESTAMPTZ DEFAULT NOW())')
    c.execute("INSERT INTO lead_contact_points(id,lead_id,contact_type,value,verification_status,owner_type,confidence) VALUES('legal','lead','email',%s,'verified','organization',1),('pr','lead','email','pr@example.test','confirmed_source','organization',.8)",(mail,))
    assert _select_best_contact(c,{'lead_id':'lead','selected_contact_point_id':'legal'})['id']=='pr'


def test_campaign_draft_requires_its_own_editor(drafts):
    from psycopg2.extras import Json
    _,c=drafts
    c.execute('UPDATE outreachmessagedrafts SET learning_note_json=%s',(Json({'campaign_id':'campaign'}),))
    with pytest.raises(ValueError,match='редактор кампании'):
        save_draft(c,business_id='b',user_id='manager',draft_id='draft',text='New',expected_digest=digest(c))
    c.execute('SELECT generated_text,edited_text,approved_text FROM outreachmessagedrafts')
    assert c.fetchone()=={'generated_text':'Original','edited_text':None,'approved_text':None}
