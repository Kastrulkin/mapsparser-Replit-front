"""Native PostgreSQL proof. Creates and drops an isolated LOCAL test database.

PYTHONPATH=src python3 -m unittest discover -s tests -p test_inbound_case_pilot.py -v
No production DSN, network providers, model calls or notifications are used.
"""
import ast
import json
import pathlib
import unittest
import uuid
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql

from services.inbound_case_contract import CaseError, STEPS, digest
from services.inbound_case_service import InboundCaseService
from services.agent_blueprint_runner import AgentBlueprintRunner
from core.action_orchestrator import ActionOrchestrator
from flask import Flask
from api.inbound_cases_api import inbound_cases_bp

ROOT = pathlib.Path(__file__).resolve().parents[1]


class InboundCasePilotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = "localos_case_test_" + uuid.uuid4().hex[:12]
        cls.admin = psycopg2.connect(dbname="postgres", host="/tmp")
        cls.admin.autocommit = True
        with cls.admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database)))
        cls.conn = cls.connect()
        # Apply the actual table DDL, not a fake in-memory approximation.
        with cls.conn.cursor() as cursor:
            external_tree = ast.parse((ROOT / "alembic_migrations/versions/20250207_add_external_sources_tables.py").read_text())
            external_upgrade = next(node for node in external_tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
            cursor.execute(ast.literal_eval(external_upgrade.body[0].value.args[0]))
            for name in ("20260523_add_agent_blueprint_layer.py", "20260609_add_custom_agent_integration_tables.py",
                         "20260905_add_agent_trigger_admission.py", "20260710_add_agent_run_queue.py"):
                tree = ast.parse((ROOT / "alembic_migrations/versions" / name).read_text())
                upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
                for statement in upgrade.body:
                    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                        call = statement.value
                        if isinstance(call.func, ast.Attribute) and call.func.attr == "execute":
                            cursor.execute(ast.literal_eval(call.args[0]))
            cursor.execute("""INSERT INTO agent_blueprints(id,business_id,name,category,status,created_by_user_id)
                VALUES ('bp','business-a','Inbound review','operations','active','user-a')""")
            cursor.execute("""INSERT INTO agent_blueprint_versions(id,blueprint_id,version_number,goal,steps_json,created_by_user_id)
                VALUES ('v1','bp',1,'Preparation only',%s::jsonb,'user-a')""", (json.dumps(STEPS),))
        cls.conn.commit()

    @classmethod
    def connect(cls):
        return psycopg2.connect(dbname=cls.database, host="/tmp", cursor_factory=RealDictCursor)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        with cls.admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cls.database)))
        cls.admin.close()

    def setUp(self):
        self.cursor = self.conn.cursor()
        self.client = {"id": "client-a", "metadata_json": {"inbound_case_bindings": [{
            "enabled": True, "source_system": "fixture", "source_tenant": "tenant-a",
            "business_id": "business-a", "version_id": "v1", "actors": {
                "staff-a": {"user_id": "user-a", "operations": ["prepare", "read", "review"]},
                "staff-b": {"user_id": "user-b", "operations": ["prepare", "read", "review"]},
            }}]}}
        self.body = {"source_system": "fixture", "source_tenant": "tenant-a", "actor_id": "staff-a",
            "reviewer_actor_id": "staff-a", "source_id": uuid.uuid4().hex, "source_version": "source-v1",
            "title": "Incoming question", "summary": "Approved source preparation", "proposed_reply": "Please provide the reference.",
            "missing_information": []}
        self.service = InboundCaseService(self.cursor, self.client, lambda *args: True)
        # A native provider invocation is a test failure, including model steps.
        self.model_guard = patch("services.agent_blueprint_runner.build_bounded_model_artifact_payload", side_effect=AssertionError("paid model called"))
        self.model_guard.start()

    def tearDown(self):
        self.model_guard.stop()
        self.conn.rollback()
        self.cursor.close()

    def decision(self, run, **extra):
        return {**self.body, "review_hash": run["review_hash"], "decision": "accepted", "reply": self.body["proposed_reply"], **extra}

    def assertCode(self, code, fn):
        with self.assertRaises(CaseError) as error:
            fn()
        self.assertEqual(code, error.exception.code)

    def test_preparation_review_replay_and_restore(self):
        run = self.service.prepare(self.body)
        self.assertEqual("waiting_approval", run["status"])
        self.assertEqual(0, run["credits_spent"])
        self.assertEqual(run["run_id"], self.service.prepare(self.body)["run_id"])
        result = self.service.review(run["run_id"], self.decision(run))
        self.assertEqual("completed", result["status"])
        self.assertFalse(result["resolution"]["external_dispatch_performed"])
        self.assertEqual(result, self.service.review(run["run_id"], self.decision(run)))
        self.conn.commit()
        with self.connect() as restored:
            fresh = InboundCaseService(restored.cursor(), self.client, lambda *args: True)
            self.assertEqual("accepted", fresh.read(run["run_id"], self.body)["resolution"]["decision"])

    def test_parallel_source_cases_do_not_supersede_each_other(self):
        one = self.service.prepare(self.body)
        two = self.service.prepare({**self.body, "source_id": "second-source"})
        self.assertNotEqual(one["run_id"], two["run_id"])
        self.assertEqual("waiting_approval", self.service.read(one["run_id"], self.body)["status"])

    def test_generic_start_and_queue_cannot_charge_or_supersede_case_reviews(self):
        from services.agent_run_queue import enqueue_agent_run
        run = self.service.prepare(self.body)
        self.assertEqual("inbound_case_route_required", AgentBlueprintRunner(self.cursor, ActionOrchestrator({})).start_run("v1", {}, {"user_id": "user-a"})["error"])
        self.cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id='v1'")
        version = self.cursor.fetchone()
        with patch("services.agent_run_queue.reserve_agent_run_credits", side_effect=AssertionError("credits reserved")):
            result = enqueue_agent_run(self.cursor, blueprint={"id": "bp", "business_id": "business-a"}, version=version,
                input_payload={}, user_data={"user_id": "user-a"}, idempotency_key="generic-start")
        self.assertEqual("INBOUND_CASE_ROUTE_REQUIRED", result["code"])
        self.assertEqual("waiting_approval", self.service.read(run["run_id"], self.body)["status"])

    def test_tenant_actor_and_membership_are_server_owned(self):
        self.assertCode("case_binding_required", lambda: self.service.prepare({**self.body, "source_tenant": "other"}))
        self.assertCode("case_actor_denied", lambda: self.service.prepare({**self.body, "actor_id": "forged"}))
        denied = InboundCaseService(self.cursor, self.client, lambda *args: False)
        self.assertCode("case_business_access_denied", lambda: denied.prepare(self.body))
        run = self.service.prepare(self.body)
        self.assertCode("case_reviewer_denied", lambda: self.service.read(run["run_id"], {**self.body, "actor_id": "staff-b"}))
        self.assertCode("case_reviewer_denied", lambda: self.service.review(run["run_id"], self.decision(run, actor_id="staff-b")))

    def test_immutable_source_and_exact_review(self):
        run = self.service.prepare(self.body)
        self.assertCode("source_revision_conflict", lambda: self.service.prepare({**self.body, "proposed_reply": "Changed text"}))
        self.assertCode("source_version_stale", lambda: self.service.review(run["run_id"], self.decision(run, source_version="old")))
        self.assertCode("case_review_stale", lambda: self.service.review(run["run_id"], self.decision(run, review_hash="old")))
        self.assertCode("case_new_preview_required", lambda: self.service.review(run["run_id"], self.decision(run, reply="Changed")))
        self.assertFalse(AgentBlueprintRunner(self.cursor, ActionOrchestrator({})).approve(run["run_id"], run["approval_id"], {"user_id": "user-a"})["success"])
        self.assertFalse(AgentBlueprintRunner(self.cursor, ActionOrchestrator({})).reject(run["run_id"], run["approval_id"], {"user_id": "user-a"})["success"])

    def test_edit_creates_new_preview_and_invalidates_old(self):
        old = self.service.prepare(self.body)
        revised = self.service.prepare({**self.body, "source_version": "source-v2", "proposed_reply": "Revised draft", "replaces_run_id": old["run_id"]})
        self.assertNotEqual(old["review_hash"], revised["review_hash"])
        self.assertEqual("superseded", self.service.read(old["run_id"], self.body)["status"])
        self.assertCode("case_not_waiting_review", lambda: self.service.review(old["run_id"], self.decision(old)))

    def test_missing_evidence_requires_clarification(self):
        run = self.service.prepare({**self.body, "missing_information": ["Check complete source"]})
        self.assertCode("case_new_preview_required", lambda: self.service.review(run["run_id"], self.decision(run)))
        result = self.service.review(run["run_id"], self.decision(run, decision="clarification_requested", reason="Check source", reply=""))
        self.assertEqual("clarification_requested", result["resolution"]["decision"])

    def test_paused_and_mutated_preset_fail_closed(self):
        self.cursor.execute("UPDATE agent_blueprints SET status='paused' WHERE id='bp'")
        self.assertCode("case_automation_paused", lambda: self.service.prepare(self.body))
        self.cursor.execute("UPDATE agent_blueprints SET status='active' WHERE id='bp'")
        self.cursor.execute("UPDATE agent_blueprint_versions SET steps_json=steps_json || %s::jsonb WHERE id='v1'", (json.dumps([{"type": "capability", "capability": "email.send"}]),))
        self.assertCode("case_preset_changed", lambda: self.service.prepare(self.body))

    def test_two_concurrent_deliveries_create_one_run(self):
        def prepare(_):
            with self.connect() as conn:
                return InboundCaseService(conn.cursor(), self.client, lambda *args: True).prepare(self.body)["run_id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(prepare, [1, 2]))
        self.assertEqual(ids[0], ids[1])

    def test_http_auth_scope_tenant_and_audit_contract(self):
        app = Flask(__name__)
        app.register_blueprint(inbound_cases_bp)
        client = {**self.client, "status": "live", "allowed_scopes": ["cases:prepare", "cases:read", "cases:review"]}
        web = app.test_client()
        with patch.dict(os.environ, {"LOCALOS_INBOUND_CASES_ENABLED": "true"}), \
                patch("api.inbound_cases_api.get_db_connection", self.connect), \
                patch("api.inbound_cases_api.load_agent_client_by_key", side_effect=lambda _c, key: client if key == "fixture-key" else None), \
                patch("api.inbound_cases_api.membership", return_value=True), \
                patch("api.inbound_cases_api.log_agent_action") as audit:
            self.assertEqual(401, web.post("/api/agent-api/inbound-cases", json=self.body).status_code)
            headers = {"X-LocalOS-Agent-Key": "fixture-key"}
            response = web.post("/api/agent-api/inbound-cases", json={**self.body, "business_id": "forged-business"}, headers=headers)
            self.assertEqual(200, response.status_code)
            self.assertEqual("business-a", response.json["case"]["business_id"])
            self.assertEqual("no-store", response.headers["Cache-Control"])
            run_id = response.json["case"]["run_id"]
            client["allowed_scopes"] = ["cases:prepare"]
            query = {key: self.body[key] for key in ("source_system", "source_tenant", "actor_id")}
            self.assertEqual(403, web.get("/api/agent-api/inbound-cases/" + run_id, query_string=query, headers=headers).status_code)
            self.assertNotIn(self.body["proposed_reply"], repr(audit.call_args))
        with patch.dict(os.environ, {"LOCALOS_INBOUND_CASES_ENABLED": "false"}):
            self.assertEqual(503, web.post("/api/agent-api/inbound-cases", json=self.body).status_code)


if __name__ == "__main__":
    unittest.main()
