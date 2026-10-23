from services import outreach_campaign_service as svc

class Cursor:
    def __init__(self):self.calls=[];self.rows=[]
    def execute(self,query,params=()):
        self.calls.append((query,params));q=' '.join(query.split())
        self.rows=[]
        if 'MAX(ws.workstream_type)' in q:
            self.rows=[{'id':'c','status':'draft','touch_count':4,'quality_passed':True,'senders_ready':True,'policy_json':{'human_copy_hash':'h'},'workstream_id':'w','lead_id':'l','version':1}]
        elif 'SELECT touch.*' in q or 'SELECT t.*, c.lead_id' in q:
            self.rows=[{'id':f't{i}','sequence_index':i,'channel':'telegram','lead_id':'l','workstream_id':'w','angle_type':'invite','scheduled_at':'2026-10-23T13:00:00+03:00','sender_account_id':'s','generated_text':'approved text','message_brief_json':{'source_fact_fingerprint':'f'}} for i in range(4)]
        elif 'SELECT COUNT(*)' in q:self.rows=[{'count':0}]
        elif 'RETURNING id, version, status' in q:self.rows=[{'id':'c','version':1,'status':'approved'}]
    def fetchone(self):return self.rows[0] if self.rows else None
    def fetchall(self):return self.rows


def test_first_only_approves_and_enqueues_one_touch_without_touching_tail(monkeypatch):
    monkeypatch.setattr(svc,'is_localos_author_lane',lambda c:False)
    monkeypatch.setattr(svc,'runtime_touch_channel_status',lambda t:'ready')
    monkeypatch.setattr(svc,'generation_contract_current',lambda *a,**k:True)
    monkeypatch.setattr(svc,'current_outreach_source_fact_fingerprint',lambda *a:'f')
    monkeypatch.setattr(svc,'sender_scope_preflight_reason',lambda t:None)
    monkeypatch.setattr(svc,'record_campaign_event',lambda *a,**k:None)
    c=Cursor();svc.approve_campaign(c,'c',user_id='owner',first_touch_only=True)
    queue=[p for q,p in c.calls if 'INSERT INTO outreachsendqueue' in q]
    assert len(queue)==1
    assert 't0' in queue[0] and all(f't{i}' not in queue[0] for i in [1,2,3])
    updates=[(q,p) for q,p in c.calls if "SET status = 'approved', approved_text" in q]
    assert len(updates)==1 and 'sequence_index = 0' in updates[0][0] and updates[0][1]==('c',True)
