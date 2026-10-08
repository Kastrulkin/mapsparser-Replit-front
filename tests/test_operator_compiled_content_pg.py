import json
from tests.test_outreach_continuation_pg import db
from tests.test_compiled_content_program import version
from services.operator_compiled_content import _load
import pytest


def test_chat_load_cannot_cross_business_and_run_uses_approved_version(db):
    connection, cursor = db
    cursor.execute('CREATE TABLE agent_blueprints(id TEXT, business_id TEXT, status TEXT, compiled_approved_version_id TEXT)')
    cursor.execute('CREATE TABLE agent_blueprint_versions(id TEXT, blueprint_id TEXT, version_number INT, execution_mode TEXT, trigger TEXT, schedule_json JSONB, steps_json JSONB)')
    cursor.execute("INSERT INTO agent_blueprints VALUES('pilot','business','draft','approved')")
    source = version()
    source['steps_json'][0]['payload']['business_id'] = 'business'
    for identifier, number in [('approved', 1), ('candidate', 2)]:
        cursor.execute('INSERT INTO agent_blueprint_versions VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)',
            (identifier, 'pilot', number, source['execution_mode'], source['trigger'],
             json.dumps(source['schedule_json']), json.dumps(source['steps_json'])))
    assert _load(cursor, 'business', 'pilot', 'compile')[1]['id'] == 'candidate'
    assert _load(cursor, 'business', 'pilot', 'run')[1]['id'] == 'approved'
    with pytest.raises(ValueError, match='agent_not_found'):
        _load(cursor, 'other-business', 'pilot', 'compile')
