#!/usr/bin/env python3
"""Real API/PostgreSQL/runner proof using internal manual-source staging only.

This is not evidence of a model-generation or a real-user pilot. Every account,
table and balance used here belongs to the synthetic isolated staging fixture.
"""
import json
import subprocess
import uuid

import requests


BASE_URL = "http://127.0.0.1:18006"
CONTAINER = "localos-plan-20260906-app-1"
SOURCE = """def process(input_payload):
    accepted = []
    errors = []
    seen = []
    duplicates = 0
    invalid = 0
    for index, row in enumerate(input_payload.get('rows', [])):
        missing = [column for column in ['email'] if not row.get(column, '').strip()]
        if missing:
            invalid += 1
            errors.append({'row': index + 1, 'code': 'required', 'columns': missing})
            continue
        key = row.get('email', '').strip().lower()
        if key in seen:
            duplicates += 1
            errors.append({'row': index + 1, 'code': 'duplicate'})
            continue
        seen.append(key)
        accepted.append(row)
    return {'schema': 'localos_compiled_script_result_v1', 'rows': accepted,
        'report': {'received': len(input_payload.get('rows', [])), 'accepted': len(accepted),
            'duplicates': duplicates, 'invalid': invalid, 'errors': errors}}
"""


def container_python(source):
    result = subprocess.run(["docker", "exec", CONTAINER, "python", "-c", source],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main():
    guard = container_python("import os; print(os.getenv('APP_ENV'),os.getenv('POSTGRES_DB'))")
    if guard != "staging localos_staging":
        raise RuntimeError("Only the synthetic isolated staging container is supported")
    session = requests.Session()
    response = session.post(BASE_URL + "/api/auth/login", json={"email": "admin@localos-e2e.invalid", "password": "LocalOS-E2E-2026!"}, timeout=15)
    response.raise_for_status()
    session.headers["X-CSRF-Token"] = session.cookies.get("localos_csrf", "")
    session.headers["Origin"] = BASE_URL
    business_id = container_python("from scripts.staging_fixture_cli import owner_business_id; print(owner_business_id())")
    # Give the synthetic test account credits; no real balance is touched.
    container_python("from database_manager import get_db_connection; c=get_db_connection(); q=c.cursor(); q.execute(\"UPDATE users SET credits_balance=100 WHERE email='admin@localos-e2e.invalid'\"); c.commit(); c.close()")
    def call(method, path, payload=None, expected=200):
        result = session.request(method, BASE_URL + path, json=payload, timeout=60)
        if result.status_code != expected:
            raise AssertionError(f"{method} {path}: {result.status_code}: {result.text[:1200]}")
        return result.json()
    blueprint = call("POST", "/api/agent-blueprints", {"business_id": business_id, "name": "[E2E] Compiled table proof", "execution_mode": "one_off"}, 201)["blueprint"]
    prefix = "/api/agent-blueprints/" + blueprint["id"] + "/compiled-script"
    rows = [{"email": "a@example.test", "amount": "001"}, {"email": " A@example.test ", "amount": "0"}, {"email": "", "amount": "5"}]
    expected = {"schema": "localos_compiled_script_result_v1", "rows": [rows[0]], "report": {
        "received": 3, "accepted": 1, "duplicates": 1, "invalid": 1,
        "errors": [{"row": 2, "code": "duplicate"}, {"row": 3, "code": "required", "columns": ["email"]}],
    }}
    compile_payload = {"description": "Synthetic table proof", "source": SOURCE,
        "idempotency_key": str(uuid.uuid4()), "table_contract": {"version": 2, "columns": ["email", "amount"],
        "required_columns": ["email"], "dedupe_columns": ["email"], "version_name": "Проверка таблицы"},
        "fixtures": [{"input": {"rows": rows}, "expected": expected, "source": "user"}]}
    compiled = call("POST", prefix + "/compile", compile_payload, 201)
    replay = call("POST", prefix + "/compile", compile_payload)
    assert replay["artifact"] == compiled["artifact"]
    version_id = compiled["candidate_version"]["id"]
    assert replay["candidate_version"]["id"] == version_id
    for _attempt in range(10):
        preview = call("POST", prefix + "/preview", {"version_id": version_id, "input": {"rows": rows}})
        assert preview["preview"]["status"] == "passed"
    call("POST", prefix + "/approve", {"version_id": version_id,
        "approval_digest": preview["approval_digest"], "fixture_digest": preview["fixture_digest"]})
    details = call("GET", "/api/agent-blueprints/" + blueprint["id"])
    assert details["compiled_approved_version"]["id"] == version_id
    run_ids = []
    for number in range(5):
        table = {"rows": rows if number == 0 else [{"email": f"b{number}@example.test", "amount": "0"}]}
        snapshot = call("POST", prefix + "/snapshots", {"input": table}, 201)["snapshot"]
        payload = {"version_id": version_id, "snapshot_id": snapshot["id"], "idempotency_key": str(uuid.uuid4())}
        queued = call("POST", prefix + "/run", payload, 202)
        run_id = queued["run"]["id"]
        run_ids.append(run_id)
        assert call("POST", prefix + "/run", payload)["run"]["id"] == run_id
        worker_source = "\n".join([
            "import json", "from database_manager import DatabaseManager",
            "from services.agent_run_queue import claim_next_agent_run, execute_claimed_compiled_agent_run",
            "for attempt in range(10):",
            "    db=DatabaseManager(); cursor=db.conn.cursor(); run=claim_next_agent_run(cursor)",
            "    assert run, 'expected queued staging run'",
            "    cursor.execute('SELECT name FROM agent_blueprints WHERE id=%s', (run['blueprint_id'],))",
            "    assert cursor.fetchone()['name']=='[E2E] Compiled table proof'",
            "    db.conn.commit(); db.rollback_and_close()",
            "    result=execute_claimed_compiled_agent_run(run)",
            "    assert result and result.get('success'), result",
            "    if run['id']==" + repr(run_id) + ": break",
            "else: raise AssertionError('staging queue did not reach target run')",
            "print(json.dumps({'status':result['run']['status'],'run_id':result['run']['id']}))",
        ])
        worker_result = json.loads(container_python(worker_source).splitlines()[-1])
        assert worker_result["status"] == "completed"
        result = call("GET", "/api/agent-runs/" + run_id)["run"]["output_json"]
        assert result["runtime_ai_calls"] == 0 and result["external_effects"] == []
        assert result["rows"] == table["rows"][:1]
        assert result["report"] == (expected["report"] if number == 0 else {"received": 1, "accepted": 1, "duplicates": 0, "invalid": 0, "errors": []})
    assert len(set(run_ids)) == 5
    print(json.dumps({"status": "passed", "mode": "internal_manual_source_staging",
        "model_generation_tested": False, "real_user_pilot": False,
        "blueprint_id": blueprint["id"], "version_id": version_id, "run_ids": run_ids,
        "compile_replay": True, "run_replay": True, "runtime_ai_calls": 0,
        "table_contract_version": 2, "previews": 10, "runs": 5}, ensure_ascii=False))


if __name__ == "__main__":
    main()
