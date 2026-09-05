"""Real PostgreSQL checks for scoped preferences, retries and concurrent writes."""
import importlib.util
import os
from pathlib import Path
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core.auth_context import AuthContext
from services import today_preferences_service
from services.product_telemetry_service import record_confirmed_user_action, record_product_event
from services.today_workspace import section_items, work_item


@pytest.fixture
def preference_db(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        if os.getenv("CI"):
            pytest.fail("LOCALOS_TEST_DATABASE_URL is mandatory for the isolated CI gate")
        pytest.skip("Set LOCALOS_TEST_DATABASE_URL to an isolated PostgreSQL database")
    parameters = psycopg2.extensions.parse_dsn(dsn)
    assert "test" in parameters.get("dbname", ""), "Refusing a non-test database"
    assert parameters.get("host", "") in {"localhost", "127.0.0.1", "postgres"} or parameters.get("host", "").startswith(("/tmp/", "/private/tmp/")), "Refusing a remote database"
    connection = psycopg2.connect(dsn,cursor_factory=RealDictCursor)
    connection.set_client_encoding("UTF8")
    schema = "test_today_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE users(id TEXT PRIMARY KEY,is_superadmin BOOLEAN DEFAULT FALSE)")
    cursor.execute("CREATE TABLE businesses(id TEXT PRIMARY KEY,network_id TEXT)")
    cursor.execute("""CREATE TABLE product_analytics_events(id TEXT PRIMARY KEY,event_name TEXT,channel TEXT,
        business_id TEXT,user_id TEXT,scope_type TEXT,scope_id TEXT,screen TEXT,target TEXT,
        properties_json JSONB,lead_id TEXT,journey_id TEXT,action_id TEXT,flow_type TEXT,
        entity_type TEXT,entity_id TEXT,occurred_at TIMESTAMPTZ DEFAULT NOW())""")
    cursor.execute("INSERT INTO users(id) VALUES ('user-1'),('user-2')")
    cursor.execute("INSERT INTO businesses VALUES ('b-1','network-1'),('b-2','network-1')")
    path = Path(__file__).parents[1] / "alembic_migrations/versions/20260905_add_today_preferences.py"
    spec = importlib.util.spec_from_file_location("today_migration",path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op,"execute",cursor.execute)
    migration.upgrade()
    migration.upgrade()  # Additive migration is safe to reapply.
    connection.commit()
    monkeypatch.setenv("LOCALOS_TODAY_ACTIVITY_ENABLED","true")
    monkeypatch.setenv("LOCALOS_TODAY_PROPOSALS_ENABLED","true")
    yield connection
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


SCOPE = {"kind":"business","id":"b-1","business_ids":["b-1"]}
NOW = datetime(2026,9,5,12,tzinfo=timezone.utc)


def test_get_is_pure_and_preference_is_scoped(preference_db):
    cursor = preference_db.cursor()
    initial = today_preferences_service.read_preferences(cursor,user_id="user-1",scope=SCOPE)
    assert initial["preference"]["revision"] == 0
    cursor.execute("SELECT COUNT(*) count FROM today_preferences")
    assert cursor.fetchone()["count"] == 0
    changed = today_preferences_service.change_preferences(cursor,user_id="user-1",scope=SCOPE,command={"action":"set","primary_flow":"content","expected_revision":0},now=NOW)
    assert changed["preference"]["revision"] == 1
    cursor.execute("SELECT event_name,signal_source,properties_json FROM product_analytics_events")
    decision = cursor.fetchone()
    assert decision["event_name"] == "today_priority_set"
    assert decision["signal_source"] == "preference_decision"
    assert decision["properties_json"]["primary_flow"] == "content"
    for user,scope in (("user-2",SCOPE),("user-1",{"kind":"business","id":"b-2"}),("user-1",{"kind":"network","id":"network-1"})):
        assert today_preferences_service.read_preferences(cursor,user_id=user,scope=scope)["preference"]["primary_flow"] == "overview"


def test_conflict_and_unavailable_flow_never_override(preference_db):
    cursor = preference_db.cursor()
    today_preferences_service.change_preferences(cursor,user_id="user-1",scope=SCOPE,command={"action":"set","primary_flow":"content","expected_revision":0},now=NOW)
    for command,allowed,code in (({"action":"set","primary_flow":"automation","expected_revision":0},today_preferences_service.FLOWS,"preference_conflict"),({"action":"set","primary_flow":"automation","expected_revision":1},["overview","content"],"flow_unavailable")):
        with pytest.raises(today_preferences_service.PreferenceError):
            today_preferences_service.change_preferences(cursor,user_id="user-1",scope=SCOPE,command=command,allowed_flows=allowed,now=NOW)
        assert today_preferences_service.load_record(cursor,user_id="user-1",scope=SCOPE)["primary_flow"] == "content"


def test_telemetry_retry_client_spoofing_and_admin_exclusion(preference_db):
    cursor = preference_db.cursor()
    auth = AuthContext(user_id="user-1")
    kwargs = dict(auth=auth,event_name="content_draft_saved",business_id="b-1",flow="content",operation_key="save:item-1:revision-2")
    first = record_confirmed_user_action(cursor,**kwargs)
    assert first == record_confirmed_user_action(cursor,**kwargs)
    record_product_event(cursor,event_name="content_draft_saved",surface="web",business_id="b-1",user_id="user-1",properties={"signal_source":"confirmed_user_action"},signal_source="client_observation",deduplication_key="client-id",flow_type="automation")
    for excluded in (AuthContext(user_id="user-1",is_superadmin=True),AuthContext(user_id="user-1",session_kind="demo",scope_business_id="b-1"),AuthContext(user_id="user-1",impersonating=True)):
        assert record_confirmed_user_action(cursor,**{**kwargs,"auth":excluded,"operation_key":uuid.uuid4().hex}) is None
    cursor.execute("SELECT COUNT(*) count FROM product_analytics_events WHERE signal_source='confirmed_user_action'")
    assert cursor.fetchone()["count"] == 1


def _seed_activity(cursor):
    for index in range(6):
        cursor.execute("""INSERT INTO product_analytics_events(id,user_id,business_id,event_name,flow_type,signal_source,occurred_at)
            VALUES (%s,'user-1','b-1','automation_configured','automation','confirmed_user_action',%s)""", (uuid.uuid4().hex,NOW-timedelta(days=3+index%3)))


def test_proposal_requires_two_days_consent_then_supports_undo_and_optout(preference_db):
    cursor = preference_db.cursor()
    record_confirmed_user_action(cursor,auth=AuthContext(user_id="user-1"),event_name="content_draft_saved",business_id="b-1",flow="content",operation_key="first")
    _seed_activity(cursor)
    record = today_preferences_service.load_record(cursor,user_id="user-1",scope=SCOPE)
    assert not today_preferences_service.evaluate_record(cursor,record=record,now=NOW)
    record = today_preferences_service.load_record(cursor,user_id="user-1",scope=SCOPE)
    assert not today_preferences_service.evaluate_record(cursor,record=record,now=NOW+timedelta(hours=1))
    assert today_preferences_service.evaluate_record(cursor,record=record,now=NOW+timedelta(days=1))
    view = today_preferences_service.read_preferences(cursor,user_id="user-1",scope=SCOPE)
    assert view["preference"]["primary_flow"] == "overview"
    proposal = view["priority_proposal"]
    result = today_preferences_service.change_preferences(cursor,user_id="user-1",scope=SCOPE,command={"action":"accept","proposal_id":proposal["id"],"expected_revision":1},now=NOW+timedelta(days=1))
    assert result["preference"]["primary_flow"] == "automation"
    result = today_preferences_service.change_preferences(cursor,user_id="user-1",scope=SCOPE,command={"action":"undo","expected_revision":2},now=NOW+timedelta(days=1))
    assert result["preference"]["primary_flow"] == "overview"
    result = today_preferences_service.change_preferences(cursor,user_id="user-1",scope=SCOPE,command={"action":"opt_out","expected_revision":3},now=NOW+timedelta(days=1))
    assert not result["preference"]["suggestions_enabled"]


def test_short_burst_and_tie_do_not_make_proposal():
    assert today_preferences_service.choose_candidate([{"flow":"automation","active_days":1,"confirmed_actions":50}],"content") is None
    assert today_preferences_service.choose_candidate([{"flow":"automation","active_days":3,"confirmed_actions":5},{"flow":"content","active_days":3,"confirmed_actions":5}],"content") is None


def test_urgent_work_precedes_selected_flow_and_result_never_looks_pending():
    def item(identity,flow,status,urgent=False):
        return work_item(entity_type="test",entity_id=identity,flow=flow,business_id="b-1",title=identity,status=status,url="/dashboard/content",now=NOW,urgent=urgent)
    sections = section_items([item("content","content","edited"),item("failure","automation","failed",True),item("done","content","published")],"content")
    assert [item["id"] for item in sections["needs_decision"]] == ["test:failure","test:content"]
    assert sections["results"][0]["status"] == "published"


def test_today_keeps_canonical_jobs_and_results_when_domain_source_fails(preference_db, monkeypatch):
    from services import today_workspace
    cursor = preference_db.cursor()
    monkeypatch.setattr(today_workspace,"allowed_priority_flows", lambda *_args, **_kwargs: list(today_preferences_service.FLOWS))
    # Exercise real SAVEPOINT rollback: this failed source must not abort other reads.
    def failed_source(cursor, *_args):
        cursor.execute("SELECT * FROM missing_domain_table")
    monkeypatch.setattr(today_workspace,"content_work",failed_source)
    monkeypatch.setattr(today_workspace,"influencer_work",lambda *_args: [])
    monkeypatch.setattr(today_workspace,"automation_work",lambda *_args: [])
    original = {"active_work":[{"id":"operator:1","title":"Проверка услуг","screen":"tasks","business_id":"b-1"}],
        "completed_results":[{"id":"result:1","title":"Готовый отчёт","screen":"progress","business_id":"b-1"}],
        "focus_action":{"id":"reviews","title":"Срочные отзывы","screen":"reviews","priority":110}}
    view = today_workspace.attach_today_workspace(cursor,scope=SCOPE,user_id="user-1",payload=original,now=NOW)
    assert view["work_sections"]["continue_work"][0]["title"] == "Проверка услуг"
    assert view["work_sections"]["results"][0]["title"] == "Готовый отчёт"
    assert view["work_sections"]["needs_decision"][0]["title"] == "Срочные отзывы"
    assert view["work_source_states"]["content"]["status"] == "error"
    assert view["data_warnings"] == [{"code":"today_source_unavailable","flow":"content"}]
    cursor.execute("SELECT COUNT(*) count FROM today_preferences")
    assert cursor.fetchone()["count"] == 0


def test_results_sort_by_recent_observation_not_identifier():
    def result(identity, when):
        return work_item(entity_type="test",entity_id=identity,flow="content",business_id="b-1",title=identity,
                         status="completed",url="/dashboard/content",now=NOW,updated_at=when)
    sections = section_items([result("a-old",NOW-timedelta(days=1)),result("z-new",NOW)],"content",limit=1)
    assert sections["results"][0]["entity_id"] == "z-new"


def test_compiled_artifact_migration_is_reapplicable_and_enforces_immutability(preference_db, monkeypatch):
    cursor = preference_db.cursor()
    cursor.execute("CREATE TABLE agent_blueprint_versions(id TEXT PRIMARY KEY)")
    path = Path(__file__).parents[1] / "alembic_migrations/versions/20260905_add_compiled_script_artifacts.py"
    spec = importlib.util.spec_from_file_location("compiled_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op,"execute",cursor.execute)
    migration.upgrade()
    migration.upgrade()
    cursor.execute("""INSERT INTO agent_blueprint_versions(id,compiled_artifact_json,compiled_artifact_hash)
        VALUES ('v-1','{"source":"original"}','sha256:original')""")
    cursor.execute("SAVEPOINT immutable")
    with pytest.raises(psycopg2.Error,match="immutable"):
        cursor.execute("UPDATE agent_blueprint_versions SET compiled_artifact_json='{}' WHERE id='v-1'")
    cursor.execute("ROLLBACK TO SAVEPOINT immutable")
    cursor.execute("UPDATE agent_blueprint_versions SET compiled_state='ready_approval' WHERE id='v-1'")
    cursor.execute("SELECT compiled_artifact_json,compiled_state FROM agent_blueprint_versions WHERE id='v-1'")
    row = cursor.fetchone()
    assert row["compiled_artifact_json"] == {"source":"original"}
    assert row["compiled_state"] == "ready_approval"
