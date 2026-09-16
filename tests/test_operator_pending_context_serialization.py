import json
from datetime import datetime, timezone
from services.operator_conversations import set_operator_pending_context

class Cursor:
    def execute(self, query, params):
        self.params=params


def test_observation_timestamp_survives_pending_context():
    cursor=Cursor()
    now=datetime(2026,9,16,10,0,tzinfo=timezone.utc)
    set_operator_pending_context(cursor,'conversation',{'observation':{'occurred_at':now,'id':'note'}})
    saved=json.loads(cursor.params[0])
    assert saved['observation']['id']=='note'
    assert datetime.fromisoformat(saved['observation']['occurred_at'])==now
    assert cursor.params[1]=='conversation'
