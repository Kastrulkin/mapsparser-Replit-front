from psycopg2.extras import Json
from tests.test_outreach_continuation_pg import db
from services.compiled_content_handoff import handoff_targets, scope_digest
from services.compiled_content_program import delivery_context, dispatch_fence


def test_network_fence_checks_all_bindings_and_exact_plans(db):
    conn,cursor=db
    cursor.execute('ALTER TABLE users ADD COLUMN name TEXT')
    cursor.execute('ALTER TABLE businesses ADD COLUMN name TEXT,ADD COLUMN address TEXT,ADD COLUMN subscription_tier TEXT,ADD COLUMN subscription_status TEXT,ADD COLUMN subscription_ends_at TIMESTAMPTZ')
    cursor.execute("INSERT INTO business_members VALUES ('b','u2','manager','active'),('b2','u','manager','active')")
    cursor.execute('CREATE TABLE contentplans(id TEXT,business_id TEXT,plan_status TEXT)')
    cursor.execute("INSERT INTO contentplans VALUES ('pa','b','generated'),('pb','b2','generated')")
    cursor.execute('CREATE TABLE agent_runs(id TEXT,blueprint_id TEXT,blueprint_version_id TEXT,status TEXT,lease_token TEXT)')
    cursor.execute('CREATE TABLE agent_blueprints(id TEXT,status TEXT,metadata_json JSONB,compiled_approved_version_id TEXT)')
    cursor.execute('CREATE TABLE agent_blueprint_versions(id TEXT,compiled_artifact_hash TEXT,compiled_state TEXT,compiled_artifact_json JSONB)')
    cursor.execute('CREATE TABLE telegramcontrolpreferences(user_id TEXT,telegram_id TEXT)')
    cursor.execute("INSERT INTO telegramcontrolpreferences VALUES ('u','100'),('u2','200')")
    scope={'business_id':'b','business_ids':['b','b2'],'recipient_user_ids':['u','u2'],'plan_ids':{'b':['pa'],'b2':['pb']},
        'platforms':['max','telegram','vk'],'lead_days':1,'time':'10:00','timezone':'UTC'}
    contract={'version':2,'scope':scope,'capability':'content.publish_handoff'}
    context=delivery_context(cursor,contract)
    consent={'version_id':'v','scope':scope,'scope_digest':scope_digest(version_id='v',scope=scope),
        'artifact_hash':'hash','approved_by_user_id':'u','delivery_context_digest':context['digest']}
    cursor.execute("INSERT INTO agent_runs VALUES ('run','pilot','v','running','lease')")
    cursor.execute("INSERT INTO agent_blueprints VALUES ('pilot','active',%s,'v')",(Json({'compiled_content_handoff_consent':consent}),))
    cursor.execute("INSERT INTO agent_blueprint_versions VALUES ('v','hash','approved',%s)",(Json({'manifest':{'content_handoff_contract':contract}}),))
    run={'id':'run','blueprint_id':'pilot','blueprint_version_id':'v','lease_token':'lease'}
    assert dispatch_fence(cursor,run,'hash',scope)
    target=handoff_targets(scope)[0]
    assert dispatch_fence(cursor,run,'hash',target)
    assert not dispatch_fence(cursor,run,'hash',{**target,'plan_ids':['foreign']})
    cursor.execute("UPDATE telegramcontrolpreferences SET telegram_id='changed' WHERE user_id='u2'")
    assert not dispatch_fence(cursor,run,'hash',scope)
