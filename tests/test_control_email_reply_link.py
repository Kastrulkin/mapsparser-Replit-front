from services import outreach_email_reply_service as service
from services.outreach_reply_tracking_service import record_bound_inbound_event


def test_human_reply_uses_message_identity_not_folder_uid(monkeypatch):
    from api import admin_prospecting
    recorded = []
    monkeypatch.setattr(admin_prospecting, '_record_reaction', lambda *args, **kwargs: (recorded.append(kwargs) or {'id':'reaction'}, None))
    reply = {'message_id':'<reply@provider>', 'provider_event_id':'email:sender:inbox:1','body':'Control reply'}
    service._record_human_reply({'id':'queue'}, {'id':'sender'}, reply, {'classification':'human_unknown'})
    service._record_human_reply({'id':'queue'}, {'id':'sender'}, {**reply,'provider_event_id':'email:sender:all:2'}, {'classification':'human_unknown'})
    assert recorded[0]['provider_message_id'] == recorded[1]['provider_message_id']
    assert recorded[0]['inbound_payload']['message_id'] == '<reply@provider>'


def test_existing_reaction_reports_duplicate(monkeypatch):
    from api import admin_prospecting
    monkeypatch.setattr(admin_prospecting, '_record_reaction', lambda *args, **kwargs: ({'id':'existing'}, 'Reaction already recorded'))
    assert service._record_human_reply({'id':'queue'},{'id':'sender'},{'body':'reply'}, {'classification':'human_unknown'}) == 'duplicate'


def test_bound_email_message_already_seen_in_another_folder_is_not_imported():
    class Cursor:
        queries = []
        def execute(self, query, params=None): self.queries.append(query)
        def fetchone(self): return {'id':'existing-event'}
    cursor = Cursor()
    result = record_bound_inbound_event(cursor,binding={'lead_id':'lead'},sender_account_id='sender',channel='email',provider_event_id='all:2',raw_reply='reply',classification={'classification':'human_unknown'},raw_payload={'message_id':'<reply@provider>'})
    assert result == 'duplicate'
    assert not any('INSERT INTO' in query for query in cursor.queries)


def test_native_campaign_reference_precedes_general_contact_binding(monkeypatch):
    monkeypatch.setenv('OUTREACH_EMAIL_THREAD_SYNC_ENABLED','true')
    monkeypatch.setenv('OUTREACH_THREAD_SYNC_BUSINESS_IDS','business')
    match={'id':'queue','provider_message_id':'<outbound@provider>','campaign_id':'campaign'}
    monkeypatch.setattr(service,'_load_non_author_queue_candidates',lambda *_: [match])
    calls=[]
    monkeypatch.setattr(service,'_record_human_reply',lambda candidate,*_: calls.append(candidate) or 'recorded')
    monkeypatch.setattr(service,'resolve_known_contact_binding',lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('Native reply must not use address-only binding')))
    class Connection:
        def cursor(self): return None
        def commit(self): pass
        def close(self): pass
    monkeypatch.setattr(service,'get_db_connection',lambda: Connection())
    result=service._sync_known_email_threads({'id':'sender','scope_type':'platform'},sent_messages=[],inbox_messages=[{'provider_event_id':'inbox:1','in_reply_to':'<outbound@provider>','body':'Test reply'}])
    assert calls==[match]
    assert result['imported']==1
    assert result['processed_event_ids']=={'inbox:1'}
