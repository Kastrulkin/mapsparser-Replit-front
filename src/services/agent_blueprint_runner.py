import json
import uuid
from typing import Any, Dict, List, Optional

from core.action_orchestrator import ActionOrchestrator


RUNNING_STATUSES = {"running", "waiting_approval"}
DANGEROUS_CAPABILITY_WORDS = ("send", "publish", "payment", "delete", "destructive", "mass")


def parse_json_field(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed
        except Exception:
            return fallback
    return fallback


def normalize_steps(value: Any) -> List[Dict[str, Any]]:
    parsed = parse_json_field(value, [])
    if not isinstance(parsed, list):
        return []
    steps = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or f"step_{index + 1}").strip()
        step_type = str(item.get("type") or "artifact").strip().lower()
        title = str(item.get("title") or key).strip()
        steps.append({**item, "key": key, "type": step_type, "title": title})
    return steps


def default_supervised_outreach_steps() -> List[Dict[str, Any]]:
    return [
        {
            "key": "source_leads",
            "type": "artifact",
            "title": "Найти потенциальных клиентов",
            "artifact_type": "lead_source_plan",
            "payload": {"status": "planned", "scope": "supervised_outreach"},
        },
        {
            "key": "shortlist",
            "type": "artifact",
            "title": "Сформировать shortlist",
            "artifact_type": "lead_shortlist",
            "payload": {"status": "draft", "items": []},
        },
        {
            "key": "approve_shortlist",
            "type": "approval",
            "title": "Подтвердить shortlist",
            "approval_type": "shortlist",
        },
        {
            "key": "draft_messages",
            "type": "artifact",
            "title": "Подготовить черновики сообщений",
            "artifact_type": "message_drafts",
            "payload": {"status": "draft", "items": []},
        },
        {
            "key": "approve_drafts",
            "type": "approval",
            "title": "Подтвердить черновики",
            "approval_type": "drafts",
        },
        {
            "key": "send_limited_batch",
            "type": "capability",
            "title": "Отправить лимитированную пачку",
            "capability": "outreach.send_batch",
            "requires_approval": True,
            "payload": {"daily_limit": 10},
        },
        {
            "key": "record_outcomes",
            "type": "artifact",
            "title": "Сохранить ответы и outcomes",
            "artifact_type": "outreach_outcomes",
            "payload": {"status": "pending", "items": []},
        },
    ]


def default_supervised_outreach_version_payload() -> Dict[str, Any]:
    return {
        "goal": "Supervised outreach: найти лиды, подготовить shortlist и черновики, отправлять только после подтверждения человека.",
        "inputs_schema": {
            "type": "object",
            "properties": {
                "geo": {"type": "string"},
                "industry": {"type": "string"},
                "limit": {"type": "integer", "default": 30},
            },
        },
        "steps": default_supervised_outreach_steps(),
        "capability_allowlist": ["outreach.send_batch"],
        "approval_policy": {
            "required_for": ["shortlist", "drafts", "external_send"],
            "daily_send_limit": 10,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "artifacts": {"type": "array"},
                "approvals": {"type": "array"},
            },
        },
    }


class AgentBlueprintRunner:
    def __init__(self, cursor, orchestrator: Optional[ActionOrchestrator] = None):
        self.cursor = cursor
        self.orchestrator = orchestrator or ActionOrchestrator({})

    def start_run(self, blueprint_version_id: str, input_payload: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
        version = self._load_version(blueprint_version_id)
        if not version:
            return {"success": False, "error": "blueprint_version_not_found"}
        blueprint = self._load_blueprint(str(version.get("blueprint_id") or ""))
        if not blueprint:
            return {"success": False, "error": "blueprint_not_found"}

        run_id = str(uuid.uuid4())
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        self.cursor.execute(
            """
            INSERT INTO agent_runs (
                id, blueprint_id, blueprint_version_id, business_id, status,
                input_json, output_json, created_by_user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (
                run_id,
                version.get("blueprint_id"),
                version.get("id"),
                blueprint.get("business_id"),
                "running",
                json.dumps(input_payload or {}, ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                user_id,
            ),
        )
        self._advance_run(run_id, user_data)
        return {"success": True, "run": self.load_run(run_id)}

    def approve(self, run_id: str, approval_id: str, user_data: Dict[str, Any], decision_reason: str = "") -> Dict[str, Any]:
        approval = self._load_approval(run_id, approval_id)
        if not approval:
            return {"success": False, "error": "approval_not_found"}
        if approval.get("status") != "pending":
            return {"success": False, "error": "approval_already_decided"}
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        self.cursor.execute(
            """
            UPDATE agent_approvals
            SET status = 'approved',
                decided_by_user_id = %s,
                decision_reason = %s,
                decided_at = NOW()
            WHERE id = %s AND run_id = %s
            """,
            (user_id, decision_reason or None, approval_id, run_id),
        )
        self.cursor.execute(
            """
            UPDATE agent_run_steps
            SET status = 'completed',
                output_json = %s::jsonb,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                json.dumps({"approval_id": approval_id, "decision": "approved"}, ensure_ascii=False),
                approval.get("step_id"),
            ),
        )
        self.cursor.execute(
            "UPDATE agent_runs SET status = 'running', updated_at = NOW() WHERE id = %s",
            (run_id,),
        )
        self._advance_run(run_id, user_data)
        return {"success": True, "run": self.load_run(run_id)}

    def reject(self, run_id: str, approval_id: str, user_data: Dict[str, Any], decision_reason: str = "") -> Dict[str, Any]:
        approval = self._load_approval(run_id, approval_id)
        if not approval:
            return {"success": False, "error": "approval_not_found"}
        if approval.get("status") != "pending":
            return {"success": False, "error": "approval_already_decided"}
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        self.cursor.execute(
            """
            UPDATE agent_approvals
            SET status = 'rejected',
                decided_by_user_id = %s,
                decision_reason = %s,
                decided_at = NOW()
            WHERE id = %s AND run_id = %s
            """,
            (user_id, decision_reason or None, approval_id, run_id),
        )
        self.cursor.execute(
            """
            UPDATE agent_run_steps
            SET status = 'rejected',
                output_json = %s::jsonb,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                json.dumps({"approval_id": approval_id, "decision": "rejected"}, ensure_ascii=False),
                approval.get("step_id"),
            ),
        )
        self.cursor.execute(
            """
            UPDATE agent_runs
            SET status = 'rejected',
                error_text = 'approval rejected',
                completed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (run_id,),
        )
        return {"success": True, "run": self.load_run(run_id)}

    def _advance_run(self, run_id: str, user_data: Dict[str, Any]) -> None:
        run = self._load_run_header(run_id)
        if not run or run.get("status") not in RUNNING_STATUSES:
            return
        version = self._load_version(str(run.get("blueprint_version_id") or ""))
        if not version:
            self._fail_run(run_id, "blueprint version missing")
            return
        steps = normalize_steps(version.get("steps_json"))
        completed_indexes = self._completed_step_indexes(run_id)
        next_index = 0
        while next_index in completed_indexes:
            next_index += 1
        if next_index >= len(steps):
            self.cursor.execute(
                """
                UPDATE agent_runs
                SET status = 'completed',
                    output_json = %s::jsonb,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(self._build_run_output(run_id), ensure_ascii=False), run_id),
            )
            return
        step = steps[next_index]
        step_type = str(step.get("type") or "artifact")
        if step_type == "approval":
            self._create_approval_step(run, step, next_index, user_data)
            return
        if step_type == "capability":
            completed = self._execute_capability_step(run, version, step, next_index, user_data)
            if completed:
                self._advance_run(run_id, user_data)
            return
        self._create_artifact_step(run, step, next_index)
        self._advance_run(run_id, user_data)

    def _create_artifact_step(self, run: Dict[str, Any], step: Dict[str, Any], step_index: int) -> None:
        step_id = self._insert_step(run, step, step_index, "completed", {}, {"artifact": True})
        artifact_id = str(uuid.uuid4())
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        self.cursor.execute(
            """
            INSERT INTO agent_artifacts (id, run_id, step_id, artifact_type, title, payload_json)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                artifact_id,
                run.get("id"),
                step_id,
                str(step.get("artifact_type") or "step_output"),
                str(step.get("title") or step.get("key") or "Artifact"),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def _create_approval_step(self, run: Dict[str, Any], step: Dict[str, Any], step_index: int, user_data: Dict[str, Any]) -> None:
        step_id = self._insert_step(run, step, step_index, "waiting_approval", {}, {"approval": "pending"})
        approval_id = str(uuid.uuid4())
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        self.cursor.execute(
            """
            INSERT INTO agent_approvals (
                id, run_id, step_id, status, approval_type, title, payload_json, requested_by_user_id
            )
            VALUES (%s, %s, %s, 'pending', %s, %s, %s::jsonb, %s)
            """,
            (
                approval_id,
                run.get("id"),
                step_id,
                str(step.get("approval_type") or step.get("key") or "manual"),
                str(step.get("title") or "Approval required"),
                json.dumps(payload, ensure_ascii=False),
                user_id,
            ),
        )
        self.cursor.execute(
            "UPDATE agent_runs SET status = 'waiting_approval', updated_at = NOW() WHERE id = %s",
            (run.get("id"),),
        )

    def _execute_capability_step(
        self,
        run: Dict[str, Any],
        version: Dict[str, Any],
        step: Dict[str, Any],
        step_index: int,
        user_data: Dict[str, Any],
    ) -> bool:
        capability = str(step.get("capability") or "").strip()
        allowlist = parse_json_field(version.get("capability_allowlist_json"), [])
        if not isinstance(allowlist, list):
            allowlist = []
        if capability not in allowlist:
            step_id = self._insert_step(run, step, step_index, "failed", {}, {"error": "capability_not_allowlisted"})
            self._fail_run(str(run.get("id")), f"capability not allowlisted: {capability}", step_id)
            return False
        if self._capability_requires_approval(capability, step) and not self._has_prior_approval(str(run.get("id"))):
            step_id = self._insert_step(run, step, step_index, "blocked", {}, {"error": "approval_required"})
            self._fail_run(str(run.get("id")), f"approval required before capability: {capability}", step_id)
            return False

        step_id = self._insert_step(run, step, step_index, "running", {}, {})
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        envelope = {
            "tenant_id": str(run.get("business_id") or ""),
            "actor": {
                "type": "user",
                "user_id": str(user_data.get("user_id") or user_data.get("id") or ""),
                "is_superadmin": bool(user_data.get("is_superadmin")),
            },
            "trace_id": f"agent-run:{run.get('id')}:{step.get('key')}",
            "idempotency_key": f"agent-run:{run.get('id')}:{step.get('key')}",
            "capability": capability,
            "payload": payload,
            "approval": {"source": "agent_blueprint", "run_id": run.get("id")},
            "billing": {"source": "agent_blueprint"},
        }
        orchestrator_result = self.orchestrator.execute(envelope, user_data, allow_execute_when_approved=True)
        if not orchestrator_result.get("success"):
            validation_error = str(orchestrator_result.get("error") or "orchestrator rejected capability")
            self.cursor.execute(
                """
                UPDATE agent_run_steps
                SET status = 'failed',
                    output_json = %s::jsonb,
                    error_text = %s,
                    completed_at = NOW()
                WHERE id = %s
                """,
                (
                    json.dumps(
                        {
                            "capability": capability,
                            "orchestrator_status": orchestrator_result.get("status"),
                            "orchestrator_error": validation_error,
                        },
                        ensure_ascii=False,
                    ),
                    validation_error,
                    step_id,
                ),
            )
            self._fail_run(str(run.get("id")), validation_error, step_id)
            return False
        self.cursor.execute(
            """
            UPDATE agent_run_steps
            SET status = 'completed',
                output_json = %s::jsonb,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                json.dumps({"capability": capability, "orchestrator": orchestrator_result}, ensure_ascii=False),
                step_id,
            ),
        )
        return True

    def _insert_step(
        self,
        run: Dict[str, Any],
        step: Dict[str, Any],
        step_index: int,
        status: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
    ) -> str:
        step_id = str(uuid.uuid4())
        self.cursor.execute(
            """
            INSERT INTO agent_run_steps (
                id, run_id, step_index, step_key, step_type, status, input_json, output_json, completed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, CASE WHEN %s IN ('completed', 'failed', 'blocked') THEN NOW() ELSE NULL END)
            """,
            (
                step_id,
                run.get("id"),
                step_index,
                str(step.get("key") or f"step_{step_index + 1}"),
                str(step.get("type") or "artifact"),
                status,
                json.dumps(input_payload or {}, ensure_ascii=False),
                json.dumps(output_payload or {}, ensure_ascii=False),
                status,
            ),
        )
        return step_id

    def _fail_run(self, run_id: str, error_text: str, step_id: Optional[str] = None) -> None:
        self.cursor.execute(
            """
            UPDATE agent_runs
            SET status = 'failed',
                error_text = %s,
                completed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (error_text, run_id),
        )

    def load_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = self._load_run_header(run_id)
        if not run:
            return None
        self.cursor.execute(
            """
            SELECT *
            FROM agent_run_steps
            WHERE run_id = %s
            ORDER BY step_index ASC
            """,
            (run_id,),
        )
        steps = [self._normalize_json_row(dict(row)) for row in (self.cursor.fetchall() or [])]
        self.cursor.execute(
            """
            SELECT *
            FROM agent_artifacts
            WHERE run_id = %s
            ORDER BY created_at ASC
            """,
            (run_id,),
        )
        artifacts = [self._normalize_json_row(dict(row)) for row in (self.cursor.fetchall() or [])]
        self.cursor.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE run_id = %s
            ORDER BY requested_at ASC
            """,
            (run_id,),
        )
        approvals = [self._normalize_json_row(dict(row)) for row in (self.cursor.fetchall() or [])]
        return {**self._normalize_json_row(run), "steps": steps, "artifacts": artifacts, "approvals": approvals}

    def _load_run_header(self, run_id: str) -> Optional[Dict[str, Any]]:
        self.cursor.execute("SELECT * FROM agent_runs WHERE id = %s", (run_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def _load_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        self.cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id = %s", (version_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def _load_blueprint(self, blueprint_id: str) -> Optional[Dict[str, Any]]:
        self.cursor.execute("SELECT * FROM agent_blueprints WHERE id = %s", (blueprint_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def _load_approval(self, run_id: str, approval_id: str) -> Optional[Dict[str, Any]]:
        self.cursor.execute("SELECT * FROM agent_approvals WHERE id = %s AND run_id = %s", (approval_id, run_id))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def _completed_step_indexes(self, run_id: str) -> set[int]:
        self.cursor.execute(
            """
            SELECT step_index
            FROM agent_run_steps
            WHERE run_id = %s AND status IN ('completed', 'rejected')
            """,
            (run_id,),
        )
        return {int(row.get("step_index")) for row in (self.cursor.fetchall() or [])}

    def _has_prior_approval(self, run_id: str) -> bool:
        self.cursor.execute(
            "SELECT 1 FROM agent_approvals WHERE run_id = %s AND status = 'approved' LIMIT 1",
            (run_id,),
        )
        return bool(self.cursor.fetchone())

    def _capability_requires_approval(self, capability: str, step: Dict[str, Any]) -> bool:
        if bool(step.get("requires_approval")):
            return True
        lowered = capability.lower()
        return any(word in lowered for word in DANGEROUS_CAPABILITY_WORDS)

    def _build_run_output(self, run_id: str) -> Dict[str, Any]:
        self.cursor.execute("SELECT COUNT(*) AS count FROM agent_artifacts WHERE run_id = %s", (run_id,))
        artifact_row = self.cursor.fetchone() or {}
        self.cursor.execute("SELECT COUNT(*) AS count FROM agent_approvals WHERE run_id = %s", (run_id,))
        approval_row = self.cursor.fetchone() or {}
        return {
            "artifact_count": int(artifact_row.get("count") or 0),
            "approval_count": int(approval_row.get("count") or 0),
        }

    def _normalize_json_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(row)
        for key in list(result.keys()):
            if key.endswith("_json"):
                result[key] = parse_json_field(result.get(key), {} if key != "steps_json" else [])
        return result
