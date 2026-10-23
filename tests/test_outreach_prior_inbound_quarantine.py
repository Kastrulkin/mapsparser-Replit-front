from services import outreach_email_reply_service

class Cursor:
    def __init__(self,rows):self.rows=rows;self.calls=[];self.fetchone_rows=[{'id':'event'}]
    def execute(self,q,p=()):self.calls.append((q,p))
    def fetchall(self):return self.rows
    def fetchone(self):return self.fetchone_rows.pop(0) if self.fetchone_rows else None
class Connection:
    def __init__(self,rows):self.c=Cursor(rows);self.commits=0;self.rollbacks=0
    def cursor(self):return self.c
    def commit(self):self.commits+=1
    def rollback(self):self.rollbacks+=1
    def close(self):pass

def test_prior_message_is_durably_recorded_and_only_exact_scoped_campaign_paused(monkeypatch):
    conn=Connection([{'id':'q','lead_id':'l','workstream_id':'w','touch_id':'t','campaign_id':'c'}])
    monkeypatch.setattr(outreach_email_reply_service,'get_db_connection',lambda:conn)
    ok=outreach_email_reply_service._quarantine_unmatched_scoped_message({'id':'s'},
      {'from_email':'known@example.test','provider_event_id':'inbound-1','body':'Прежнее сообщение'},
      [{'id':'q','recipient_value':'known@example.test'},{'id':'unrelated','recipient_value':'other@example.test'}])
    assert ok and conn.commits==1
    assert conn.c.calls[0][1]==(['q'],'s')
    insert=next(p for q,p in conn.c.calls if 'INSERT INTO outreach_inbound_events' in q)
    assert insert[-2].adapted['reply_to_current_touch'] is False
    assert insert[-2].adapted['affected_campaign_ids']==['c']
    queue_update=next((q,p) for q,p in conn.c.calls if 'UPDATE outreachsendqueue' in q)
    assert "delivery_status='paused'" in queue_update[0] and queue_update[1]==('c',)
    assert not any("delivery_status='sent'" in q for q,p in conn.c.calls)

def test_foreign_or_ambiguous_peer_does_not_produce_a_receipt(monkeypatch):
    def forbidden():raise AssertionError('database must not be used')
    monkeypatch.setattr(outreach_email_reply_service,'get_db_connection',forbidden)
    assert not outreach_email_reply_service._quarantine_unmatched_scoped_message({'id':'s'},
      {'from_email':'unknown@example.test','provider_event_id':'event'},[{'id':'q','recipient_value':'known@example.test'}])

def test_missing_durable_context_keeps_existing_fail_closed_path(monkeypatch):
    conn=Connection([]);monkeypatch.setattr(outreach_email_reply_service,'get_db_connection',lambda:conn)
    assert not outreach_email_reply_service._quarantine_unmatched_scoped_message({'id':'s'},
      {'from_email':'known@example.test','provider_event_id':'event'},[{'id':'q','recipient_value':'known@example.test'}])
    assert conn.commits==0 and conn.rollbacks==1

def test_already_recorded_prior_inbound_replays_without_new_event(monkeypatch):
    conn=Connection([{'id':'q','lead_id':'l','workstream_id':'w','touch_id':'t','campaign_id':'c'}]);conn.c.fetchone_rows=[None,{'id':'existing-event'}]
    monkeypatch.setattr(outreach_email_reply_service,'get_db_connection',lambda:conn)
    assert outreach_email_reply_service._quarantine_unmatched_scoped_message({'id':'s'},
      {'from_email':'known@example.test','provider_event_id':'event'},[{'id':'q','recipient_value':'known@example.test'}])
    assert conn.commits==1
