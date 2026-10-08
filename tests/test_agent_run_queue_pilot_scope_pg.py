from tests.test_outreach_continuation_pg import db
from services.agent_run_queue import claim_next_agent_run


def test_pilot_queue_does_not_claim_or_recover_other_automations(db, monkeypatch):
    conn, cursor = db
    cursor.execute('CREATE TABLE agent_blueprints(id TEXT PRIMARY KEY,status TEXT)')
    cursor.execute("INSERT INTO agent_blueprints VALUES ('pilot','draft'),('riderra','active')")
    cursor.execute('''CREATE TABLE agent_runs(id TEXT PRIMARY KEY,blueprint_id TEXT,status TEXT,
        queued_at TIMESTAMPTZ DEFAULT NOW(),started_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,
        heartbeat_at TIMESTAMPTZ,next_attempt_at TIMESTAMPTZ,updated_at TIMESTAMPTZ DEFAULT NOW(),
        attempt_count INTEGER DEFAULT 0,max_attempts INTEGER DEFAULT 3,lease_token TEXT,error_text TEXT)''')
    cursor.execute("INSERT INTO agent_runs(id,blueprint_id,status,queued_at) VALUES ('other','riderra','queued',NOW()-INTERVAL '1 day'),('test','pilot','queued',NOW())")
    cursor.execute("INSERT INTO agent_runs(id,blueprint_id,status,heartbeat_at,lease_token) VALUES ('stale-other','riderra','running',NOW()-INTERVAL '1 day','keep-this-lease')")
    monkeypatch.setenv('AGENT_RUN_QUEUE_BLUEPRINT_IDS','pilot')
    claimed = claim_next_agent_run(cursor)
    assert claimed['id'] == 'test'
    assert claim_next_agent_run(cursor) is None
    cursor.execute("SELECT status,lease_token,attempt_count FROM agent_runs WHERE id='stale-other'")
    assert dict(cursor.fetchone()) == {'status':'running','lease_token':'keep-this-lease','attempt_count':0}
    cursor.execute("SELECT status FROM agent_runs WHERE id='other'")
    assert cursor.fetchone()['status'] == 'queued'
    monkeypatch.delenv('AGENT_RUN_QUEUE_BLUEPRINT_IDS')
    claimed = claim_next_agent_run(cursor)
    assert claimed['id'] == 'other'
