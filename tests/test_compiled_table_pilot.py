import importlib.util
import json
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core.auth_context import AuthContext
from services.compiled_input_snapshots import create_snapshot, resolve_snapshot, SnapshotUnavailable
from services.compiled_pilot_access import compiled_pilot_allowed
from services.compiled_script_artifact import build_artifact, generate_candidate_from_description, validate_artifact
from services.compiled_table_contract import normalize_table_input, normalize_table_contract, table_manifest


CONTRACT = {"version": 1, "columns": ["email", "amount"], "required_columns": ["email"], "dedupe_columns": ["email"], "version_name": "Проверка"}
DIGEST = "sha256:" + "a" * 64


def test_table_contract_preserves_zero_and_leading_zero_text():
    value = {"rows": [{"email": "001", "amount": "0"}]}
    assert normalize_table_input(value) == value
    assert normalize_table_input({"rows": []}) == {"rows": []}
    with pytest.raises(ValueError):
        normalize_table_input({"rows": [{"amount": 0}]})


@pytest.mark.parametrize("value", [
    {"rows": [{}] * 201}, {"rows": [None]}, {"rows": [{"amount": "x" * 1001}]},
    {"rows": [{"unknown": "x"}]}, {"rows": [], "source": "other-business"},
])
def test_table_rejects_invalid_input_at_gateway(value):
    with pytest.raises(ValueError):
        normalize_table_input(value, CONTRACT["columns"])


def test_table_limits_bytes_independently_of_row_count_and_handles_boundary():
    assert len(normalize_table_input({"rows": [{"email": str(index)} for index in range(200)]})["rows"]) == 200
    with pytest.raises(ValueError):
        normalize_table_input({"rows": [{"email": "я" * 1000} for _index in range(20)]})


@pytest.mark.parametrize("change", [{"dedupe_columns": []}, {"columns": ["email", "email"]}, {"required_columns": ["foreign"]}, {"version": 3}, {"version": True}])
def test_table_rules_are_explicit_and_versioned(change):
    with pytest.raises(ValueError):
        normalize_table_contract({**CONTRACT, **change})


def test_generator_must_supply_source_but_cannot_change_table_contract():
    captured = []
    def generator(prompt):
        captured.append(prompt)
        return json.dumps({"source": "def process(input_payload):\n    return {}", "manifest": {"kind": "invented"}, "fixtures": [{"input": {"rows": []}, "expected": {}}]})
    result = generate_candidate_from_description("Проверить таблицу", business_id="biz", user_id="user", generator=generator, runner_image_digest=DIGEST, table_contract=CONTRACT)
    assert result["status"] == "ready"
    assert result["candidate"]["manifest"] == table_manifest(CONTRACT, DIGEST)
    assert result["candidate"]["source"].endswith("return {}")
    assert "Frozen table contract" in captured[0]
    tampered = table_manifest(CONTRACT, DIGEST)
    tampered["required_columns"] = []
    with pytest.raises(ValueError):
        build_artifact(result["candidate"]["source"], tampered, [{"input": {"rows": []}, "expected": {}, "source": "user"}])


def test_model_fixtures_cannot_block_independent_table_validation():
    fixture = {"input": {"rows": []}, "expected": {}, "source": "user"}
    result = generate_candidate_from_description("Table", business_id="biz", user_id="user",
        generator=lambda _prompt: json.dumps({"source": "def process(input_payload):\n    return {}", "fixtures": "invented"}),
        table_contract=CONTRACT, validation_fixtures=[fixture], runner_image_digest=DIGEST)
    assert result["status"] == "ready"
    assert result["candidate"]["fixtures"] == [fixture]


def test_top_level_kind_cannot_disable_pilot_oracle_without_changing_hash():
    artifact = build_artifact("def process(input_payload):\n    return {}", table_manifest(CONTRACT, DIGEST), [{"input": {"rows": []}, "expected": {}, "source": "user"}])
    artifact["kind"] = "localos.python_transform.v1"
    checked = validate_artifact(artifact)
    assert not checked["valid"]
    assert any(error["code"] == "kind_mismatch" for error in checked["errors"])


def test_aggregate_examples_cannot_exceed_runner_request_budget():
    from services.compiled_script_artifact import validate_candidate
    table = {"rows": [{"email": str(index), "amount": "я" * 450} for index in range(15)]}
    normalize_table_input(table, CONTRACT["columns"])
    examples = [{"input": table, "expected": table, "source": "user"} for _index in range(16)]
    checked = validate_candidate("def process(input_payload):\n    return {}", table_manifest(CONTRACT, DIGEST), examples)
    assert any(error["code"] == "artifact_size_limit" for error in checked["errors"])


def test_version_two_reports_original_duplicate_rows_without_changing_v1():
    from services.compiled_script_runtime import execute_pilot
    rows = {"rows": [{"email": "a"}, {"email": " A "}, {"email": ""}]}
    example = [{"input": rows, "expected": {}, "source": "user"}]
    first = build_artifact("def process(input_payload):\n    return {}", table_manifest(CONTRACT, DIGEST), example)
    second = build_artifact("def process(input_payload):\n    return {}", table_manifest({**CONTRACT, "version": 2}, DIGEST), example)
    assert execute_pilot(first, rows)["report"]["errors"] == [{"row": 3, "code": "required", "columns": ["email"]}]
    assert execute_pilot(second, rows)["report"] == {"received": 3, "accepted": 1, "duplicates": 1, "invalid": 1,
        "errors": [{"row": 2, "code": "duplicate"}, {"row": 3, "code": "required", "columns": ["email"]}]}


def test_compiled_cohort_is_fail_closed_and_each_stage_has_own_switch(monkeypatch):
    monkeypatch.setenv("COMPILED_SCRIPT_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("COMPILED_SCRIPT_EXECUTE_ENABLED", "false")
    monkeypatch.delenv("COMPILED_SCRIPT_PILOT_BUSINESS_IDS", raising=False)
    assert not compiled_pilot_allowed("biz")
    monkeypatch.setenv("COMPILED_SCRIPT_PILOT_BUSINESS_IDS", "other, biz")
    assert compiled_pilot_allowed("biz")
    assert not compiled_pilot_allowed("biz", execute=True)
    assert not compiled_pilot_allowed("foreign")
    monkeypatch.setenv("COMPILED_SCRIPT_PILOT_BUSINESS_IDS", "*")
    assert not compiled_pilot_allowed("biz")


@pytest.fixture
def snapshot_db(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires an isolated PostgreSQL database")
    parameters = psycopg2.extensions.parse_dsn(dsn)
    assert "test" in parameters.get("dbname", "")
    assert parameters.get("host", "").startswith(("/tmp/", "/private/tmp/", "localhost", "127.0.0.1", "postgres"))
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_compiled_snapshots_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    path = Path(__file__).parents[1] / "alembic_migrations/versions/20260906_add_compiled_input_snapshots.py"
    spec = importlib.util.spec_from_file_location("snapshot_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op, "execute", cursor.execute)
    migration.upgrade()
    migration.upgrade()
    connection.commit()
    yield connection
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def test_snapshot_pins_data_and_is_owner_and_blueprint_scoped(snapshot_db):
    cursor = snapshot_db.cursor()
    value = {"rows": [{"email": "001", "amount": "0"}]}
    snapshot = create_snapshot(cursor, auth=AuthContext("user"), blueprint_id="bp", business_id="biz", input_payload=value)
    snapshot_db.commit()
    value["rows"][0]["amount"] = "changed after admission"
    resolved = resolve_snapshot(cursor, snapshot["id"], "biz", "user", "bp")
    assert resolved["input"]["rows"][0]["amount"] == "0"
    assert resolved["content_hash"] == snapshot["hash"]
    for business, user, blueprint in [("foreign", "user", "bp"), ("biz", "other", "bp"), ("biz", "user", "other")]:
        with pytest.raises(SnapshotUnavailable):
            resolve_snapshot(cursor, snapshot["id"], business, user, blueprint)
    with pytest.raises(psycopg2.Error):
        cursor.execute("UPDATE compiled_input_snapshots SET input_json = '{}'::jsonb WHERE id = %s", (snapshot["id"],))
    snapshot_db.rollback()
    assert resolve_snapshot(cursor, snapshot["id"], "biz", "user")["input"]["rows"][0]["amount"] == "0"


def test_snapshot_expiry_and_demo_access_are_rejected(snapshot_db):
    cursor = snapshot_db.cursor()
    with pytest.raises(SnapshotUnavailable):
        create_snapshot(cursor, auth=AuthContext("demo", session_kind="demo", scope_business_id="biz"), blueprint_id="bp", business_id="biz", input_payload={"rows": []})
    cursor.execute("""INSERT INTO compiled_input_snapshots(id,business_id,user_id,blueprint_id,source_kind,source_name,schema_version,content_hash,input_json,row_count,expires_at)
        VALUES ('expired','biz','user','bp','user_table','table','localos_table_input_v1','invalid','{}',0,NOW()-INTERVAL '1 second')""")
    with pytest.raises(SnapshotUnavailable):
        resolve_snapshot(cursor, "expired", "biz", "user")


def test_snapshot_quota_is_scoped_and_does_not_insert_over_limit(snapshot_db):
    from services.compiled_input_snapshots import SnapshotQuotaExceeded
    cursor = snapshot_db.cursor()
    for _index in range(100):
        create_snapshot(cursor, auth=AuthContext("user"), blueprint_id="bp", business_id="biz", input_payload={"rows": []})
    with pytest.raises(SnapshotQuotaExceeded):
        create_snapshot(cursor, auth=AuthContext("user"), blueprint_id="bp", business_id="biz", input_payload={"rows": []})
    create_snapshot(cursor, auth=AuthContext("other-user"), blueprint_id="bp", business_id="biz", input_payload={"rows": []})
    cursor.execute("SELECT COUNT(*) count FROM compiled_input_snapshots")
    assert cursor.fetchone()["count"] == 101


def test_retention_scrubs_raw_rows_keeps_report_and_waits_for_running_job(snapshot_db):
    from services.compiled_input_snapshots import purge_expired_snapshots
    cursor = snapshot_db.cursor()
    cursor.execute("""CREATE TABLE agent_runs(id TEXT PRIMARY KEY, input_snapshot_id TEXT,
        status TEXT, input_json JSONB, output_json JSONB, updated_at TIMESTAMPTZ,
        error_text TEXT, completed_at TIMESTAMPTZ, next_attempt_at TIMESTAMPTZ, lease_token TEXT)""")
    for key, status in [("done", "completed"), ("waiting", "queued"), ("busy", "running")]:
        cursor.execute("""INSERT INTO compiled_input_snapshots(id,business_id,user_id,blueprint_id,source_kind,
            source_name,schema_version,content_hash,input_json,row_count,expires_at)
            VALUES (%s,'biz','user','bp','user_table','test','localos_table_input_v1','hash',
            '{"rows":[{"email":"private@example.test"}]}',1,NOW()-INTERVAL '1 hour')""", (key,))
        cursor.execute("""INSERT INTO agent_runs(id,input_snapshot_id,status,input_json,output_json)
            VALUES (%s,%s,%s,'{"rows":[{"email":"private@example.test"}]}',
            '{"rows":[{"email":"private@example.test"}],"report":{"accepted":1}}')""", (key, key, status))
    assert purge_expired_snapshots(cursor) == {"purged_snapshots": 2, "expired_runs": 1}
    cursor.execute("SELECT * FROM agent_runs WHERE id='done'")
    done = cursor.fetchone()
    assert done["input_json"] == {"snapshot_id": "done", "data_expired": True}
    assert done["output_json"] == {"report": {"accepted": 1}, "data_expired": True}
    cursor.execute("SELECT status,error_text FROM agent_runs WHERE id='waiting'")
    assert dict(cursor.fetchone()) == {"status": "failed", "error_text": "compiled_input_expired"}
    cursor.execute("SELECT COUNT(*) count FROM compiled_input_snapshots")
    assert cursor.fetchone()["count"] == 1
    cursor.execute("UPDATE agent_runs SET status='completed' WHERE id='busy'")
    assert purge_expired_snapshots(cursor)["purged_snapshots"] == 1
    assert purge_expired_snapshots(cursor)["purged_snapshots"] == 0
