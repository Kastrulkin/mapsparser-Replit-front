"""Source-bound cases using the native agent runner, approvals and event journal.

No model, provider, scheduler, mailbox consumer or domain writer is introduced.
The caller owns the transaction. Each source revision is immutable.
"""
import json
import uuid

from services.agent_blueprint_runner import AgentBlueprintRunner
from core.action_orchestrator import ActionOrchestrator
from services.inbound_case_contract import (
    CONTRACT, CaseError, digest, normalize_case, object_value, review_payload,
    resolve_binding, text, validate_preset,
)


class InboundCaseRunner(AgentBlueprintRunner):
    _inbound_case_runtime = True

    def __init__(self, cursor):
        # The exact preset has only artifacts and a human gate. Do not even
        # register external handlers in this provider-free preparation runtime.
        super().__init__(cursor, orchestrator=ActionOrchestrator({}))

    def _supersede_pending_runs(self, blueprint_id):
        # Each source case has its own human decision; preparing another case
        # must not cancel a colleague's pending review.
        return

    def _create_openclaw_preview_observations(self, *args, **kwargs):
        return

    def _advance_run(self, run_id, user_data):
        run = self._load_run_header(run_id)
        validate_preset(self._load_version(run["blueprint_version_id"]) or {})
        super()._advance_run(run_id, user_data)

    def _build_artifact_payload(self, run, step):
        case = object_value(run["input_json"])["case"]
        if step["artifact_type"] == "inbound_case_review":
            return review_payload(case)
        self.cursor.execute("SELECT output_json FROM agent_run_steps WHERE run_id=%s AND step_key='review_case'", (run["id"],))
        row = self.cursor.fetchone()
        decision = object_value(row["output_json"]) if row else {}
        return {"contract": CONTRACT, "source_id": case["source_id"], **decision,
                "preparation_only": True, "external_dispatch_performed": False, "credits_spent": 0}

    def _build_approval_payload(self, run, step):
        payload = self._latest_artifact_payload(run["id"], "inbound_case_review")
        return {"contract": CONTRACT, "review_hash": digest(payload), "artifact": payload}

    def load_run(self, run_id, user_data=None):
        run = self._load_run_header(run_id)
        if not run:
            raise CaseError("case_not_found", 404)
        self.cursor.execute("SELECT * FROM agent_approvals WHERE run_id=%s ORDER BY requested_at DESC LIMIT 1", (run_id,))
        approval = self.cursor.fetchone()
        review = object_value(approval["payload_json"]) if approval else {}
        resolution = self._latest_artifact_payload(run_id, "inbound_case_resolution")
        return {"run_id": run_id, "business_id": run["business_id"], "status": run["status"],
                "approval_id": approval["id"] if approval else None,
                "review_hash": review.get("review_hash"), "review": review.get("artifact"),
                "resolution": resolution or None, "updated_at": run["updated_at"],
                "credits_spent": 0, "preparation_only": True}


class InboundCaseService:
    def __init__(self, cursor, client, check_membership):
        self.cursor, self.client, self.check_membership = cursor, client, check_membership
        self.runner = InboundCaseRunner(cursor)

    def _authorize(self, body, operation):
        for key, limit in (("source_system", 64), ("source_tenant", 128), ("actor_id", 128)):
            text(body.get(key), limit, True)
        binding, user = resolve_binding(self.client, body, operation)
        if not self.check_membership(self.cursor, binding["business_id"], user):
            raise CaseError("case_business_access_denied", 403)
        return binding, user

    def _version(self, binding, require_active=True):
        self.cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id=%s FOR SHARE", (binding["version_id"],))
        version = self.cursor.fetchone()
        validate_preset(version or {})
        self.cursor.execute("SELECT * FROM agent_blueprints WHERE id=%s FOR SHARE", (version["blueprint_id"],))
        blueprint = self.cursor.fetchone()
        if not blueprint or blueprint["business_id"] != binding["business_id"]:
            raise CaseError("case_binding_invalid", 403)
        if require_active and blueprint["status"] != "active":
            raise CaseError("case_automation_paused")
        return version

    def prepare(self, body):
        case = normalize_case(body)
        binding, user = self._authorize(case, "prepare")
        self._authorize({**case, "actor_id": case["reviewer_actor_id"]}, "review")
        version = self._version(binding, require_active=False)
        event_key = digest([case["source_id"], case["source_version"]])
        source = "inbound_case:" + digest([case["source_system"], case["source_tenant"]])
        # One transaction for event + native run + human review. No network I/O.
        self.cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (digest([binding["business_id"], source, event_key]),))
        self.cursor.execute("SELECT id,payload_json FROM agent_trigger_events WHERE business_id=%s AND source=%s AND source_event_key=%s", (binding["business_id"], source, event_key))
        prior = self.cursor.fetchone()
        # actor is authorization, not part of the immutable prepared material.
        material = {key: value for key, value in case.items() if key != "actor_id"}
        material_hash = digest(material)
        if prior:
            event = object_value(prior["payload_json"])
            if event.get("material_hash") != material_hash or event.get("client_id") != self.client["id"]:
                raise CaseError("source_revision_conflict")
            self.cursor.execute("SELECT run_id FROM agent_trigger_run_links WHERE trigger_event_id=%s", (prior["id"],))
            link = self.cursor.fetchone()
            if not link:
                raise CaseError("case_link_missing")
            return self.runner.load_run(link["run_id"])
        self._version(binding)
        if case["replaces_run_id"]:
            previous, previous_case, _ = self._bound_run(case["replaces_run_id"], case, "review")
            if previous_case["source_id"] != case["source_id"] or previous["status"] != "waiting_approval":
                raise CaseError("case_replacement_invalid")
            if previous_case.get("reviewer_actor_id") != case["actor_id"]:
                raise CaseError("case_reviewer_denied", 403)
        event_id = str(uuid.uuid4())
        self.cursor.execute("""INSERT INTO agent_trigger_events
            (id,business_id,source,event_type,status,payload_json,source_event_key)
            VALUES (%s,%s,%s,'inbound.case.prepared','received',%s::jsonb,%s)""",
            (event_id, binding["business_id"], source,
             json.dumps({"material_hash": material_hash, "client_id": self.client["id"]}), event_key))
        result = self.runner.start_run(version["id"], {"case": material, "client_id": self.client["id"],
            "trigger_event_id": event_id, "external_side_effects_allowed": False}, user)
        if not result.get("success"):
            raise CaseError(result.get("error", "case_preparation_failed"))
        run = result["run"]
        self.cursor.execute("""INSERT INTO agent_trigger_run_links
            (id,trigger_event_id,blueprint_id,blueprint_version_id,run_id,status)
            VALUES (%s,%s,%s,%s,%s,'waiting_approval')""",
            (str(uuid.uuid4()), event_id, version["blueprint_id"], version["id"], run["run_id"]))
        self.cursor.execute("UPDATE agent_trigger_events SET status='dispatched',updated_at=NOW() WHERE id=%s", (event_id,))
        if case["replaces_run_id"]:
            self.cursor.execute("UPDATE agent_approvals SET status='superseded',decision_reason='Replaced by new preview',decided_at=NOW() WHERE run_id=%s AND status='pending'", (case["replaces_run_id"],))
            self.cursor.execute("UPDATE agent_runs SET status='superseded',completed_at=NOW(),updated_at=NOW() WHERE id=%s", (case["replaces_run_id"],))
            self.cursor.execute("UPDATE agent_trigger_run_links SET status='superseded',updated_at=NOW() WHERE run_id=%s", (case["replaces_run_id"],))
        return run

    def _bound_run(self, run_id, body, operation, require_active=True):
        binding, user = self._authorize(body, operation)
        self._version(binding, require_active)
        self.cursor.execute("SELECT * FROM agent_runs WHERE id=%s AND business_id=%s FOR UPDATE", (run_id, binding["business_id"]))
        run = self.cursor.fetchone()
        if not run:
            raise CaseError("case_not_found", 404)
        payload = object_value(run["input_json"])
        case = payload.get("case", {})
        if (payload.get("client_id") != self.client["id"] or run["blueprint_version_id"] != binding["version_id"]
                or case.get("source_system") != body.get("source_system") or case.get("source_tenant") != body.get("source_tenant")):
            raise CaseError("case_binding_mismatch", 403)
        if operation == "read" and body.get("actor_id") != case.get("reviewer_actor_id") and user["user_id"] != run["created_by_user_id"]:
            raise CaseError("case_reviewer_denied", 403)
        return run, case, user

    def read(self, run_id, body):
        self._bound_run(run_id, body, "read", require_active=False)
        return self.runner.load_run(run_id)

    def review(self, run_id, body):
        run, case, user = self._bound_run(run_id, body, "review")
        if body.get("actor_id") != case.get("reviewer_actor_id"):
            raise CaseError("case_reviewer_denied", 403)
        if body.get("source_version") != case.get("source_version"):
            raise CaseError("source_version_stale")
        decision = body.get("decision")
        if decision not in {"accepted", "rejected", "clarification_requested"}:
            raise CaseError("invalid_case_decision", 400)
        reply = text(body.get("reply", ""), 12000, decision == "accepted")
        reason = text(body.get("reason", ""), 2000, decision != "accepted")
        current = self.runner.load_run(run_id)
        if not current["approval_id"] or body.get("review_hash") != current["review_hash"]:
            raise CaseError("case_review_stale")
        reviewed = current["review"] or {}
        if decision == "accepted" and (reply != reviewed.get("proposed_reply") or reviewed.get("missing_information")):
            # Edits require another immutable source version + a fresh preview.
            raise CaseError("case_new_preview_required")
        resolution = {"decision": decision, "reply": reply, "reason": reason,
                      "review_hash": current["review_hash"], "actor_id": body.get("actor_id")}
        if current["resolution"]:
            saved = current["resolution"]
            if all(saved.get(key) == value for key, value in resolution.items()):
                return current
            raise CaseError("case_already_decided")
        if run["status"] != "waiting_approval":
            raise CaseError("case_not_waiting_review")
        self.cursor.execute("""UPDATE agent_approvals SET status=%s,decided_by_user_id=%s,
            decision_reason=%s,decided_at=NOW() WHERE id=%s AND status='pending'""",
            ("approved" if decision == "accepted" else "rejected", user["user_id"], reason or decision, current["approval_id"]))
        if self.cursor.rowcount != 1:
            raise CaseError("case_already_decided")
        self.cursor.execute("UPDATE agent_run_steps SET status='completed',output_json=%s::jsonb,completed_at=NOW() WHERE run_id=%s AND step_key='review_case'", (json.dumps(resolution), run_id))
        self.cursor.execute("UPDATE agent_runs SET status='running',updated_at=NOW() WHERE id=%s", (run_id,))
        self.runner._advance_run(run_id, user)
        self.cursor.execute("UPDATE agent_trigger_run_links SET status='completed',updated_at=NOW() WHERE run_id=%s", (run_id,))
        return self.runner.load_run(run_id)
