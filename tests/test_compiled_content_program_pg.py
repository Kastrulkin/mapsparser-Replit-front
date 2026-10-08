from psycopg2.extras import Json
from tests.test_outreach_continuation_pg import db
from tests.test_compiled_content_program import version
from services.compiled_content_handoff import scope_digest
from services.compiled_content_program import contract_for, dispatch_fence


def test_dispatch_is_fenced_by_pause_binding_version_and_lease(db):
    conn, cursor = db
    cursor.execute('CREATE TABLE agent_runs(id TEXT PRIMARY KEY,blueprint_id TEXT,blueprint_version_id TEXT,status TEXT,lease_token TEXT)')
    cursor.execute('CREATE TABLE agent_blueprints(id TEXT PRIMARY KEY,status TEXT,metadata_json JSONB,compiled_approved_version_id TEXT)')
    cursor.execute('CREATE TABLE agent_blueprint_versions(id TEXT PRIMARY KEY,compiled_artifact_hash TEXT,compiled_state TEXT)')
    cursor.execute('CREATE TABLE telegramcontrolpreferences(user_id TEXT PRIMARY KEY,telegram_id TEXT)')
    scope = contract_for(version(), 'b')['scope']
    consent = {'version_id':'v','scope':scope,'scope_digest':scope_digest(version_id='v',scope=scope),'telegram_id':'123','artifact_hash':'hash'}
    cursor.execute("INSERT INTO agent_runs VALUES('run','pilot','v','running','lease')")
    cursor.execute("INSERT INTO agent_blueprints VALUES('pilot','draft',%s,'v')", (Json({'compiled_content_handoff_consent':consent}),))
    cursor.execute("INSERT INTO agent_blueprint_versions VALUES('v','hash','approved')")
    cursor.execute("INSERT INTO telegramcontrolpreferences VALUES('owner','123')")
    run = {'id':'run','blueprint_id':'pilot','blueprint_version_id':'v','lease_token':'lease'}
    assert dispatch_fence(cursor, run, 'hash', scope)
    assert not dispatch_fence(cursor, {**run,'lease_token':'stale'}, 'hash', scope)
    assert not dispatch_fence(cursor, run, 'changed', scope)
    cursor.execute("UPDATE agent_blueprints SET status='paused'")
    assert not dispatch_fence(cursor, run, 'hash', scope)
    cursor.execute("UPDATE agent_blueprints SET status='draft'")
    cursor.execute("UPDATE telegramcontrolpreferences SET telegram_id='other'")
    assert not dispatch_fence(cursor, run, 'hash', scope)
