import json
import uuid
from typing import Any, Dict, List, Optional

from core.action_orchestrator import ActionOrchestrator
from core.channel_router import dispatch_with_routing, load_business_channel_context
from services.agent_domain_request_executors import execute_approved_domain_requests
from services.agent_blueprint_workspace import build_generic_artifact_payload
from services.agent_integration_preflight import build_agent_integration_preflight


RUNNING_STATUSES = {"running", "waiting_approval"}
DANGEROUS_CAPABILITY_WORDS = ("send", "publish", "payment", "delete", "destructive", "mass")
SHORTLIST_APPROVED = "shortlist_approved"
SELECTED_FOR_OUTREACH = "selected_for_outreach"
CHANNEL_SELECTED = "channel_selected"
DRAFT_GENERATED = "generated"
DRAFT_APPROVED = "approved"
DRAFT_READY = "draft_ready"
PIPELINE_IN_PROGRESS = "in_progress"
SUPPORTED_BLUEPRINT_CHANNELS = ("telegram", "whatsapp", "email", "manual")


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
            "payload": {"status": "pending", "scope": "supervised_outreach"},
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
            "required_approval_type": "drafts",
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
        metadata = parse_json_field(blueprint.get("metadata_json"), {})
        metadata = metadata if isinstance(metadata, dict) else {}
        preflight = build_agent_integration_preflight(
            self.cursor,
            business_id=str(blueprint.get("business_id") or ""),
            metadata=metadata,
            input_payload=input_payload or {},
        )
        if not preflight.get("ready"):
            return {
                "success": False,
                "error": "agent_integration_preflight_blocked",
                "code": "AGENT_INTEGRATIONS_REQUIRED",
                "preflight": preflight,
            }

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
        self._create_openclaw_preview_observations(run_id, input_payload or {})
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
        approval_type = str(approval.get("approval_type") or "").strip()
        if approval_type == "shortlist":
            self._apply_shortlist_approval(run_id, user_id)
        if approval_type == "drafts":
            self._apply_drafts_approval(run_id, user_id)
        self.cursor.execute(
            "UPDATE agent_runs SET status = 'running', updated_at = NOW() WHERE id = %s",
            (run_id,),
        )
        self._commit_cursor_connection()
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
        payload = self._build_artifact_payload(run, step)
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
                json.dumps(payload, ensure_ascii=False, default=str),
            ),
        )

    def _build_artifact_payload(self, run: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        base_payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        artifact_type = str(step.get("artifact_type") or "").strip()
        if artifact_type == "lead_source_plan":
            return self._build_lead_source_payload(run, base_payload)
        if artifact_type == "lead_shortlist":
            return self._build_lead_shortlist_payload(run, base_payload)
        if artifact_type == "message_drafts":
            return self._build_message_drafts_payload(run, base_payload)
        if artifact_type == "outreach_outcomes":
            return self._build_outreach_outcomes_payload(run, base_payload)
        if artifact_type == "finance_import_preview":
            return self._build_finance_import_preview_payload(run, base_payload)
        if artifact_type == "localos_finance_outcome":
            return self._build_localos_finance_outcome_payload(run, base_payload)
        generic_payload = build_generic_artifact_payload(self.cursor, run, step, base_payload)
        if generic_payload is not None:
            return generic_payload
        return dict(base_payload)

    def _create_openclaw_preview_observations(self, run_id: str, input_payload: Dict[str, Any]) -> None:
        if not self._is_safe_preview_input(input_payload):
            return
        route_plan = input_payload.get("openclaw_preview_routes") if isinstance(input_payload.get("openclaw_preview_routes"), list) else []
        action_plan = input_payload.get("openclaw_action_plan") if isinstance(input_payload.get("openclaw_action_plan"), list) else []
        handler_contracts = input_payload.get("connector_action_handlers") if isinstance(input_payload.get("connector_action_handlers"), list) else []
        openclaw_handlers = [
            item
            for item in handler_contracts
            if isinstance(item, dict) and str(item.get("handler") or "") == "openclaw_policy_boundary"
        ]
        openclaw_actions = [
            item
            for item in action_plan
            if isinstance(item, dict)
            and (
                str(item.get("provider") or "") == "openclaw"
                or str(item.get("provider_action_ref") or "").startswith("openclaw.")
            )
        ]
        if not route_plan and not openclaw_handlers and not openclaw_actions:
            return
        run = self._load_run_header(run_id)
        if not run:
            return
        step = {
            "key": "openclaw_preview_observations",
            "type": "connector_preview",
            "title": "OpenClaw preview observations",
        }
        step_id = self._insert_step(
            run,
            step,
            -1,
            "completed",
            {
                "preview_mode": True,
                "external_side_effects_allowed": False,
            },
            {
                "schema": "localos_openclaw_preview_observations_v1",
                "status": "dry_run_ready",
                "route_count": len(route_plan),
                "action_count": len(openclaw_actions),
                "external_actions_executed": False,
            },
        )
        artifact_id = str(uuid.uuid4())
        payload = {
            "schema": "localos_openclaw_preview_observations_v1",
            "status": "dry_run_ready",
            "execution_boundary": "openclaw_inside_localos_policy",
            "safe_preview": True,
            "external_actions_executed": False,
            "external_side_effects_allowed": False,
            "approval_required_for_external_actions": True,
            "route_plan": [item for item in route_plan if isinstance(item, dict)][:12],
            "handler_contracts": openclaw_handlers[:12],
            "action_plan": openclaw_actions[:12],
            "observations": [
                {
                    "binding_key": str(item.get("binding_key") or item.get("step_key") or ""),
                    "capability": str(item.get("capability") or ""),
                    "provider_action_ref": str(item.get("provider_action_ref") or ""),
                    "status": "preview_only",
                    "external_action_executed": False,
                    "next_step": "approval_required_before_execution",
                }
                for item in (route_plan or openclaw_actions)
                if isinstance(item, dict)
            ][:12],
        }
        self.cursor.execute(
            """
            INSERT INTO agent_artifacts (id, run_id, step_id, artifact_type, title, payload_json)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                artifact_id,
                run_id,
                step_id,
                "openclaw_preview_observations",
                "OpenClaw preview observations",
                json.dumps(payload, ensure_ascii=False, default=str),
            ),
        )

    def _is_safe_preview_input(self, input_payload: Dict[str, Any]) -> bool:
        return bool(input_payload.get("preview_mode")) and input_payload.get("external_side_effects_allowed") is False

    def _run_input(self, run: Dict[str, Any]) -> Dict[str, Any]:
        parsed = parse_json_field(run.get("input_json"), {})
        return parsed if isinstance(parsed, dict) else {}

    def _build_lead_source_payload(self, run: Dict[str, Any], base_payload: Dict[str, Any]) -> Dict[str, Any]:
        run_input = self._run_input(run)
        lead_ids = self._normalized_string_list(run_input.get("lead_ids"))
        statuses = self._normalized_string_list(run_input.get("statuses"))
        intent = str(run_input.get("intent") or "client_outreach").strip()
        source = str(run_input.get("source") or "").strip()
        city = str(run_input.get("city") or run_input.get("geo") or "").strip()
        category = str(run_input.get("category") or run_input.get("industry") or "").strip()
        limit = self._safe_limit(run_input.get("limit"), 30)
        query = """
            SELECT id, name, city, category, source, status,
                   selected_channel, intent, pipeline_status, updated_at, created_at
            FROM prospectingleads
            WHERE business_id = %s
        """
        params: List[Any] = [str(run.get("business_id") or "")]
        if lead_ids:
            query += " AND id = ANY(%s)"
            params.append(lead_ids)
        else:
            if intent:
                query += " AND COALESCE(intent, 'client_outreach') = %s"
                params.append(intent)
            if source:
                query += " AND source = %s"
                params.append(source)
            if city:
                query += " AND city ILIKE %s"
                params.append(f"%{city}%")
            if category:
                query += " AND category ILIKE %s"
                params.append(f"%{category}%")
            if statuses:
                query += " AND status = ANY(%s)"
                params.append(statuses)
            else:
                query += """
                  AND (
                    status IN ('new', 'qualified', 'shortlist_approved', 'selected_for_outreach', 'channel_selected')
                    OR pipeline_status IN ('unprocessed', 'in_progress', 'qualified')
                  )
                """
        query += " ORDER BY updated_at DESC NULLS LAST, created_at DESC LIMIT %s"
        params.append(limit)
        try:
            self.cursor.execute(query, tuple(params))
            rows = [dict(row) for row in (self.cursor.fetchall() or [])]
        except Exception:
            rows = []
        status_counts: Dict[str, int] = {}
        for row in rows:
            status_key = str(row.get("status") or "unknown").strip() or "unknown"
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
        return {
            **base_payload,
            "status": "hydrated" if rows else "empty",
            "source": "prospectingleads",
            "count": len(rows),
            "status_counts": status_counts,
            "filters": {
                "lead_ids": lead_ids,
                "statuses": statuses,
                "intent": intent,
                "source": source,
                "city": city,
                "category": category,
                "limit": limit,
            },
            "items": rows,
        }

    def _build_lead_shortlist_payload(self, run: Dict[str, Any], base_payload: Dict[str, Any]) -> Dict[str, Any]:
        run_input = self._run_input(run)
        lead_ids = self._normalized_string_list(run_input.get("lead_ids"))
        source_lead_ids = self._latest_artifact_item_ids(str(run.get("id") or ""), "lead_source_plan", "id")
        limit = self._safe_limit(run_input.get("limit"), 30)
        query = """
            SELECT id, name, city, email, telegram_url, whatsapp_url, status, selected_channel, pipeline_status
            FROM prospectingleads
            WHERE business_id = %s
        """
        params: List[Any] = [str(run.get("business_id") or "")]
        if lead_ids:
            query += " AND id = ANY(%s)"
            params.append(lead_ids)
        elif source_lead_ids:
            query += " AND id = ANY(%s)"
            params.append(source_lead_ids)
        else:
            query += """
              AND (
                status IN ('selected_for_outreach', 'channel_selected', 'qualified', 'queued_for_send')
                OR pipeline_status IN ('in_progress', 'qualified')
              )
            """
        query += " ORDER BY updated_at DESC, created_at DESC LIMIT %s"
        params.append(limit)
        try:
            self.cursor.execute(query, tuple(params))
            rows = [dict(row) for row in (self.cursor.fetchall() or [])]
        except Exception:
            rows = []
        return {
            **base_payload,
            "status": "hydrated" if rows else base_payload.get("status", "draft"),
            "source": "prospectingleads",
            "source_artifact": "lead_source_plan" if source_lead_ids and not lead_ids else "",
            "count": len(rows),
            "items": rows,
        }

    def _build_message_drafts_payload(self, run: Dict[str, Any], base_payload: Dict[str, Any]) -> Dict[str, Any]:
        run_input = self._run_input(run)
        draft_ids = self._normalized_string_list(run_input.get("draft_ids"))
        limit = self._safe_limit(run_input.get("limit"), 30)
        rows = self._load_message_draft_rows(run, draft_ids, limit)
        if not rows and not draft_ids and self._has_required_approval(str(run.get("id") or ""), {"required_approval_type": "shortlist"}):
            self._create_message_drafts_for_approved_shortlist(run, limit)
            rows = self._load_message_draft_rows(run, draft_ids, limit)
        return {
            **base_payload,
            "status": "hydrated" if rows else base_payload.get("status", "draft"),
            "source": "outreachmessagedrafts",
            "count": len(rows),
            "items": rows,
        }

    def _load_message_draft_rows(self, run: Dict[str, Any], draft_ids: List[str], limit: int) -> List[Dict[str, Any]]:
        query = """
            SELECT d.id, d.lead_id, d.channel, d.status, d.generated_text, d.approved_text, l.name AS lead_name
            FROM outreachmessagedrafts d
            JOIN prospectingleads l ON l.id = d.lead_id
            WHERE l.business_id = %s
        """
        params: List[Any] = [str(run.get("business_id") or "")]
        if draft_ids:
            query += " AND d.id = ANY(%s)"
            params.append(draft_ids)
        else:
            query += " AND d.status IN ('generated', 'edited', 'approved')"
        query += " ORDER BY d.updated_at DESC, d.created_at DESC LIMIT %s"
        params.append(limit)
        try:
            self.cursor.execute(query, tuple(params))
            return [dict(row) for row in (self.cursor.fetchall() or [])]
        except Exception:
            return []

    def _create_message_drafts_for_approved_shortlist(self, run: Dict[str, Any], limit: int) -> None:
        lead_ids = self._latest_artifact_item_ids(str(run.get("id") or ""), "lead_shortlist", "id")
        if not lead_ids:
            return
        try:
            self.cursor.execute(
                """
                SELECT id, name, category, city, rating, reviews_count, website, phone,
                       email, telegram_url, whatsapp_url, selected_channel, status
                FROM prospectingleads
                WHERE business_id = %s
                  AND id = ANY(%s)
                  AND NOT EXISTS (
                        SELECT 1
                        FROM outreachmessagedrafts d
                        WHERE d.lead_id = prospectingleads.id
                          AND d.status IN ('generated', 'edited', 'approved')
                  )
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                (str(run.get("business_id") or ""), lead_ids, limit),
            )
            leads = [dict(row) for row in (self.cursor.fetchall() or [])]
        except Exception:
            return

        actor_id = str(run.get("created_by_user_id") or "")
        for lead in leads:
            channel = self._select_blueprint_channel(lead)
            if not channel:
                continue
            draft_id = str(uuid.uuid4())
            draft_text = self._render_blueprint_outreach_draft(lead, channel)
            self.cursor.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, channel, angle_type, tone, status,
                    generated_text, edited_text, learning_note_json, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                )
                """,
                (
                    draft_id,
                    lead.get("id"),
                    channel,
                    "maps_growth",
                    "professional",
                    DRAFT_GENERATED,
                    draft_text,
                    draft_text,
                    json.dumps(
                        {
                            "source": "agent_blueprint_local",
                            "prompt_key": "supervised_outreach.blueprint.local_v1",
                            "run_id": run.get("id"),
                        },
                        ensure_ascii=False,
                    ),
                    actor_id or None,
                ),
            )
            self.cursor.execute(
                """
                UPDATE prospectingleads
                SET status = %s,
                    selected_channel = %s,
                    pipeline_status = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND business_id = %s
                """,
                (CHANNEL_SELECTED, channel, PIPELINE_IN_PROGRESS, lead.get("id"), str(run.get("business_id") or "")),
            )

    def _select_blueprint_channel(self, lead: Dict[str, Any]) -> str:
        selected = str(lead.get("selected_channel") or "").strip().lower()
        candidates = [selected] if selected else []
        candidates.extend(channel for channel in SUPPORTED_BLUEPRINT_CHANNELS if channel not in candidates)
        for channel in candidates:
            if self._lead_has_channel_contact(lead, channel):
                return channel
        return ""

    def _lead_has_channel_contact(self, lead: Dict[str, Any], channel: str) -> bool:
        if channel == "manual":
            return True
        if channel == "telegram":
            return bool(str(lead.get("telegram_url") or "").strip())
        if channel == "whatsapp":
            return bool(str(lead.get("whatsapp_url") or "").strip())
        if channel == "email":
            return bool(str(lead.get("email") or "").strip())
        return False

    def _render_blueprint_outreach_draft(self, lead: Dict[str, Any], channel: str) -> str:
        company_name = str(lead.get("name") or "вашей компании").strip()
        category = str(lead.get("category") or "локального бизнеса").strip()
        city = str(lead.get("city") or "").strip()
        location = f" в {city}" if city else ""
        if channel == "email":
            return (
                f"Здравствуйте! Мы посмотрели карточку {company_name} в картах. "
                f"Видим вас в категории «{category}»{location}. "
                "Можем прислать короткий разбор: что мешает получать больше обращений и какие правки дадут быстрый эффект."
            )
        return (
            f"Здравствуйте. Посмотрели карточку {company_name}: видим вас в категории «{category}»{location}. "
            "Если актуально, пришлю короткий разбор с конкретными точками роста."
        )

    def _build_outreach_outcomes_payload(self, run: Dict[str, Any], base_payload: Dict[str, Any]) -> Dict[str, Any]:
        run_input = self._run_input(run)
        draft_ids = self._normalized_string_list(run_input.get("draft_ids"))
        if not draft_ids:
            draft_ids = self._latest_artifact_item_ids(str(run.get("id") or ""), "message_drafts", "id")
        if not draft_ids:
            return {**base_payload, "source": "outreachsendqueue", "count": 0, "items": []}
        try:
            self.cursor.execute(
                """
                SELECT q.id, q.batch_id, q.lead_id, q.draft_id, q.channel, q.delivery_status, q.sent_at,
                       q.provider_message_id, q.error_text, l.name AS lead_name
                FROM outreachsendqueue q
                JOIN prospectingleads l ON l.id = q.lead_id
                WHERE q.draft_id = ANY(%s)
                  AND l.business_id = %s
                ORDER BY q.created_at DESC
                LIMIT 50
                """,
                (draft_ids, str(run.get("business_id") or "")),
            )
            rows = [dict(row) for row in (self.cursor.fetchall() or [])]
        except Exception:
            rows = []
        return {
            **base_payload,
            "status": "hydrated" if rows else base_payload.get("status", "pending"),
            "source": "outreachsendqueue",
            "count": len(rows),
            "queued_count": len([row for row in rows if str(row.get("delivery_status") or "") == "queued"]),
            "dispatch_state": "queued_not_dispatched" if rows else "not_queued",
            "external_dispatch_performed": False,
            "operator_note": "Queue rows are LocalOS handoff records. External dispatcher is a separate contour.",
            "items": rows,
        }

    def _build_finance_import_preview_payload(self, run: Dict[str, Any], base_payload: Dict[str, Any]) -> Dict[str, Any]:
        source_step = str(base_payload.get("source_step") or "read_google_sheets").strip()
        source_result = self._step_output_result(str(run.get("id") or ""), source_step)
        rows = source_result.get("rows") if isinstance(source_result.get("rows"), list) else []
        count = int(source_result.get("count") or len(rows))
        return {
            **base_payload,
            "status": "ready_for_review" if rows else "waiting_for_source_rows",
            "source_step": source_step,
            "rows_read": count,
            "sample_rows": rows[:5],
            "normalizer": base_payload.get("normalizer") or "core.finance_imports.normalize_finance_import_rows",
            "localos_write_performed": False,
            "side_effects_performed": False,
        }

    def _build_localos_finance_outcome_payload(self, run: Dict[str, Any], base_payload: Dict[str, Any]) -> Dict[str, Any]:
        run_id = str(run.get("id") or "")
        source_step = str(base_payload.get("source_step") or "read_google_sheets").strip()
        request_step = str(base_payload.get("request_step") or "request_localos_finance").strip()
        source_result = self._step_output_result(run_id, source_step)
        request_output = self._latest_completed_step_output(run_id, request_step)
        orchestrator = request_output.get("orchestrator") if isinstance(request_output.get("orchestrator"), dict) else {}
        capability_result = orchestrator.get("result") if isinstance(orchestrator.get("result"), dict) else {}
        approved_executor = request_output.get("approved_executor") if isinstance(request_output.get("approved_executor"), dict) else {}
        executor_items = approved_executor.get("items") if isinstance(approved_executor.get("items"), list) else []
        rows = source_result.get("rows") if isinstance(source_result.get("rows"), list) else []
        proposals = capability_result.get("finance_entry_proposals") if isinstance(capability_result.get("finance_entry_proposals"), list) else []
        review_rows = capability_result.get("rows_requiring_review") if isinstance(capability_result.get("rows_requiring_review"), list) else []
        errors = capability_result.get("errors") if isinstance(capability_result.get("errors"), list) else []
        rows_imported = 0
        rows_failed = 0
        rows_skipped = 0
        for item in executor_items:
            if not isinstance(item, dict):
                continue
            rows_imported += int(item.get("rows_imported") or 0)
            rows_failed += int(item.get("rows_failed") or 0)
            rows_skipped += int(item.get("rows_skipped") or 0)
        localos_write_performed = bool(approved_executor.get("localos_writes_performed")) or rows_imported > 0
        apply_state = "applied" if localos_write_performed else str(capability_result.get("apply_state") or base_payload.get("apply_state") or "not_applied")
        return {
            **base_payload,
            "status": "applied" if localos_write_performed else str(capability_result.get("status") or base_payload.get("status") or "request_created"),
            "source_step": source_step,
            "request_step": request_step,
            "request_id": capability_result.get("request_id") or "",
            "action_id": orchestrator.get("action_id") or "",
            "rows_read": int(source_result.get("count") or len(rows)),
            "proposal_count": int(capability_result.get("proposal_count") or len(proposals)),
            "review_count": int(capability_result.get("review_count") or len(review_rows)),
            "error_count": int(capability_result.get("error_count") or len(errors)),
            "rows_imported": rows_imported,
            "rows_skipped": rows_skipped,
            "rows_failed": rows_failed,
            "rows_requiring_review": review_rows[:20],
            "errors": errors[:20],
            "apply_state": apply_state,
            "approval_state": capability_result.get("approval_state") or "pending_human",
            "localos_write_performed": localos_write_performed,
            "provider_write_performed": False,
            "side_effects_performed": localos_write_performed,
            "recovery": {
                "idempotency": "rerun uses finance duplicate_key checks before inserting rows",
                "unresolved_rows": "rows with validation errors or review reasons remain pending for human decision",
                "support_export": f"/api/agent-runs/{run_id}/support-export",
            },
            "executor_items": executor_items[:10],
        }

    def _safe_limit(self, value: Any, default: int) -> int:
        try:
            parsed = int(value or default)
        except Exception:
            parsed = default
        return max(1, min(parsed, 100))

    def _normalized_string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            candidate = str(item or "").strip()
            if candidate:
                result.append(candidate)
        return list(dict.fromkeys(result))

    def _create_approval_step(self, run: Dict[str, Any], step: Dict[str, Any], step_index: int, user_data: Dict[str, Any]) -> None:
        step_id = self._insert_step(run, step, step_index, "waiting_approval", {}, {"approval": "pending"})
        approval_id = str(uuid.uuid4())
        user_id = str(user_data.get("user_id") or user_data.get("id") or "")
        payload = self._build_approval_payload(run, step)
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
        if self._capability_requires_approval(capability, step) and not self._has_required_approval(str(run.get("id")), step):
            required_type = str(step.get("required_approval_type") or "").strip()
            error_text = f"approval required before capability: {capability}"
            if required_type:
                error_text = f"approval required before capability: {capability} ({required_type})"
            step_id = self._insert_step(run, step, step_index, "blocked", {}, {"error": "approval_required", "required_approval_type": required_type})
            self._fail_run(str(run.get("id")), error_text, step_id)
            return False

        step_id = self._insert_step(run, step, step_index, "running", {}, {})
        payload = self._build_capability_payload(run, step)
        if capability == "outreach.send_batch" and not payload.get("draft_ids"):
            payload["draft_ids"] = self._latest_artifact_item_ids(str(run.get("id") or ""), "message_drafts", "id")
        if self._is_maton_delivery_step(run, capability):
            return self._execute_maton_delivery_step(run, step, step_id, capability, payload)
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
        capability_result = orchestrator_result.get("result") if isinstance(orchestrator_result.get("result"), dict) else {}
        if capability_result.get("status") == "blocked":
            reason_code = str(capability_result.get("reason_code") or "CAPABILITY_BLOCKED")
            self.cursor.execute(
                """
                UPDATE agent_run_steps
                SET status = 'blocked',
                    output_json = %s::jsonb,
                    error_text = %s,
                    completed_at = NOW()
                WHERE id = %s
                """,
                (
                    json.dumps({"capability": capability, "orchestrator": orchestrator_result}, ensure_ascii=False),
                    reason_code,
                    step_id,
                ),
            )
            self._fail_run(str(run.get("id")), reason_code, step_id)
            return False
        approved_executor = execute_approved_domain_requests(
            self.cursor,
            run=run,
            step=step,
            orchestrator_result=orchestrator_result,
            user_data=user_data,
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
                json.dumps(
                    {
                        "capability": capability,
                        "orchestrator": orchestrator_result,
                        "approved_executor": approved_executor,
                    },
                    ensure_ascii=False,
                ),
                step_id,
            ),
        )
        return True

    def _is_maton_delivery_step(self, run: Dict[str, Any], capability: str) -> bool:
        if capability not in {"communications.send", "communications.send_reminder", "communications.send_offer"}:
            return False
        return bool(self._maton_delivery_contract(run))

    def _maton_delivery_contract(self, run: Dict[str, Any]) -> Dict[str, Any]:
        blueprint = self._load_blueprint(str(run.get("blueprint_id") or ""))
        metadata = parse_json_field((blueprint or {}).get("metadata_json"), {})
        if not isinstance(metadata, dict):
            return {}
        handlers = metadata.get("connector_action_handlers") if isinstance(metadata.get("connector_action_handlers"), dict) else {}
        routes = metadata.get("agent_binding_provider_routes") if isinstance(metadata.get("agent_binding_provider_routes"), dict) else {}
        for binding_key, handler in handlers.items():
            if not isinstance(handler, dict):
                continue
            if str(handler.get("handler") or "") != "maton_external_account_bridge":
                continue
            route = routes.get(binding_key) if isinstance(routes.get(binding_key), dict) else {}
            return {
                **handler,
                "binding_key": str(binding_key or handler.get("binding_key") or ""),
                "route": route,
                "external_account_id": str(handler.get("external_account_id") or route.get("external_account_id") or ""),
            }
        return {}

    def _execute_maton_delivery_step(
        self,
        run: Dict[str, Any],
        step: Dict[str, Any],
        step_id: str,
        capability: str,
        payload: Dict[str, Any],
    ) -> bool:
        contract = self._maton_delivery_contract(run)
        message = self._maton_delivery_message(payload)
        run_input = self._run_input(run)
        safe_preview = self._is_safe_preview_input(run_input) or self._is_safe_preview_input(payload)
        dispatch_requested = (
            str(payload.get("dispatch_mode") or "").strip() == "send_after_approval"
            and payload.get("external_side_effects_allowed") is True
            and not safe_preview
        )
        if not message:
            self._complete_maton_delivery_step(
                run,
                step,
                step_id,
                capability,
                payload,
                contract,
                {
                    "status": "blocked",
                    "delivery_state": "message_missing",
                    "external_dispatch_performed": False,
                    "error": "message is empty",
                },
            )
            return True
        router_result: Dict[str, Any] = {}
        delivery_state = "draft_ready"
        status = "draft_created"
        external_dispatch_performed = False
        if dispatch_requested:
            ctx = load_business_channel_context(self.cursor, str(run.get("business_id") or ""))
            router_result = dispatch_with_routing(
                ctx,
                message,
                preferred_provider="maton",
                force_channel_id="maton_bridge",
            )
            external_dispatch_performed = bool(router_result.get("success"))
            delivery_state = "sent" if external_dispatch_performed else "dispatch_failed"
            status = "sent" if external_dispatch_performed else "dispatch_failed"
        elif safe_preview:
            delivery_state = "preview_draft_only"
            status = "preview_draft_created"
        else:
            delivery_state = "queued_after_approval"
            status = "request_created"
        self._complete_maton_delivery_step(
            run,
            step,
            step_id,
            capability,
            payload,
            contract,
            {
                "status": status,
                "delivery_state": delivery_state,
                "message": message,
                "external_dispatch_performed": external_dispatch_performed,
                "router_result": router_result,
            },
        )
        return True

    def _maton_delivery_message(self, payload: Dict[str, Any]) -> str:
        for key in ("message", "text", "draft_text", "post_text", "message_template"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        source_payload = payload.get("source_step_payload") if isinstance(payload.get("source_step_payload"), dict) else {}
        for key in ("message", "text", "draft_text", "post_text", "summary"):
            value = source_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _complete_maton_delivery_step(
        self,
        run: Dict[str, Any],
        step: Dict[str, Any],
        step_id: str,
        capability: str,
        payload: Dict[str, Any],
        contract: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        artifact_payload = {
            "schema": "localos_maton_delivery_request_v1",
            "status": str(result.get("status") or "request_created"),
            "capability": capability,
            "provider": "maton",
            "handler": "maton_external_account_bridge",
            "binding_key": str(contract.get("binding_key") or ""),
            "external_account_id": str(contract.get("external_account_id") or ""),
            "approval_required": True,
            "delivery_state": str(result.get("delivery_state") or ""),
            "message": str(result.get("message") or ""),
            "recipient": self._maton_delivery_recipient(payload),
            "external_dispatch_performed": bool(result.get("external_dispatch_performed")),
            "router_result": result.get("router_result") if isinstance(result.get("router_result"), dict) else {},
            "policy": {
                "approval_owner": "LocalOS",
                "execution_boundary": "maton_bridge_inside_localos_policy",
                "external_side_effects_allowed": payload.get("external_side_effects_allowed") is True,
                "dispatch_mode": str(payload.get("dispatch_mode") or "draft_or_request"),
            },
        }
        artifact_id = str(uuid.uuid4())
        self.cursor.execute(
            """
            INSERT INTO agent_artifacts (id, run_id, step_id, artifact_type, title, payload_json)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                artifact_id,
                run.get("id"),
                step_id,
                "maton_delivery_request",
                str(step.get("title") or "Maton delivery request"),
                json.dumps(artifact_payload, ensure_ascii=False, default=str),
            ),
        )
        output_payload = {
            "capability": capability,
            "provider": "maton",
            "handler": "maton_external_account_bridge",
            "result": artifact_payload,
        }
        if result.get("error"):
            output_payload["error"] = str(result.get("error") or "")
        self.cursor.execute(
            """
            UPDATE agent_run_steps
            SET status = 'completed',
                output_json = %s::jsonb,
                completed_at = NOW()
            WHERE id = %s
            """,
            (json.dumps(output_payload, ensure_ascii=False, default=str), step_id),
        )

    def _maton_delivery_recipient(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        recipients = payload.get("recipients") if isinstance(payload.get("recipients"), list) else []
        first = recipients[0] if recipients and isinstance(recipients[0], dict) else {}
        target = (
            str(payload.get("recipient") or "").strip()
            or str(payload.get("target") or "").strip()
            or str(payload.get("telegram_target") or "").strip()
            or str(first.get("recipient_key") or first.get("phone") or first.get("telegram") or "").strip()
        )
        return {
            "target": target or "business_owner_or_maton_auto_route",
            "channel": str(payload.get("channel") or first.get("channel") or "maton").strip() or "maton",
        }

    def _build_capability_payload(self, run: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        step_payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        run_input = parse_json_field(run.get("input_json"), {})
        if not isinstance(run_input, dict):
            run_input = {}
        payload = {**run_input, **step_payload}
        self._apply_step_output_references(str(run.get("id") or ""), payload)
        return payload

    def _apply_step_output_references(self, run_id: str, payload: Dict[str, Any]) -> None:
        input_mappings = payload.get("input_mappings")
        if isinstance(input_mappings, list):
            for mapping in input_mappings:
                if not isinstance(mapping, dict):
                    continue
                source_step = str(mapping.get("from_step") or "").strip()
                target = str(mapping.get("target") or "").strip()
                path = str(mapping.get("path") or "").strip()
                if not source_step or not target:
                    continue
                if self._payload_has_target(payload, target):
                    continue
                value = self._step_output_value(run_id, source_step, path)
                if value is not None:
                    self._set_payload_target(payload, target, value)
        rows_from_step = str(payload.get("rows_from_step") or "").strip()
        if rows_from_step and not payload.get("rows"):
            rows = self._step_output_list(run_id, rows_from_step, "rows")
            if rows:
                payload["rows"] = rows
        payload_from_step = str(payload.get("payload_from_step") or "").strip()
        if payload_from_step:
            result = self._step_output_result(run_id, payload_from_step)
            if result:
                payload["source_step_payload"] = result
        payload.pop("input_mappings", None)
        payload.pop("rows_from_step", None)
        payload.pop("payload_from_step", None)

    def _payload_has_target(self, payload: Dict[str, Any], target: str) -> bool:
        current = payload
        parts = [part for part in target.split(".") if part]
        if not parts:
            return False
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                return False
            current = next_value
        return parts[-1] in current and current.get(parts[-1]) not in (None, "", [])

    def _set_payload_target(self, payload: Dict[str, Any], target: str, value: Any) -> None:
        current = payload
        parts = [part for part in target.split(".") if part]
        if not parts:
            return
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                current[part] = next_value
            current = next_value
        current[parts[-1]] = value

    def _step_output_list(self, run_id: str, step_key: str, field: str) -> List[Dict[str, Any]]:
        result = self._step_output_result(run_id, step_key)
        items = result.get(field)
        if not isinstance(items, list):
            return []
        rows = []
        for item in items:
            if isinstance(item, dict):
                rows.append(dict(item))
        return rows

    def _step_output_result(self, run_id: str, step_key: str) -> Dict[str, Any]:
        output = self._latest_completed_step_output(run_id, step_key)
        orchestrator = output.get("orchestrator") if isinstance(output.get("orchestrator"), dict) else {}
        result = orchestrator.get("result") if isinstance(orchestrator.get("result"), dict) else {}
        if result:
            return result
        direct_result = output.get("result") if isinstance(output.get("result"), dict) else {}
        if direct_result:
            return direct_result
        return output

    def _step_output_value(self, run_id: str, step_key: str, path: str) -> Any:
        output = self._latest_completed_step_output(run_id, step_key)
        if not output:
            return None
        if not path:
            return self._step_output_result(run_id, step_key)
        current: Any = output
        for part in [item for item in path.split(".") if item]:
            if isinstance(current, dict):
                current = current.get(part)
                continue
            if isinstance(current, list):
                try:
                    current = current[int(part)]
                    continue
                except Exception:
                    return None
            return None
        return current

    def _latest_completed_step_output(self, run_id: str, step_key: str) -> Dict[str, Any]:
        self.cursor.execute(
            """
            SELECT output_json
            FROM agent_run_steps
            WHERE run_id = %s
              AND step_key = %s
              AND status = 'completed'
            ORDER BY step_index DESC
            LIMIT 1
            """,
            (run_id, step_key),
        )
        row = self.cursor.fetchone()
        if not row:
            return {}
        value = row.get("output_json") if isinstance(row, dict) else row[0]
        parsed = parse_json_field(value, {})
        return parsed if isinstance(parsed, dict) else {}

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

    def load_run(self, run_id: str, user_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
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
        normalized_run = self._normalize_json_row(run)
        observability = self._build_run_observability(normalized_run, steps, artifacts, approvals, user_data or {})
        return {**normalized_run, "steps": steps, "artifacts": artifacts, "approvals": approvals, "observability": observability}

    def build_run_support_export(self, run_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        run = self.load_run(run_id, user_data)
        if not run:
            return {"success": False, "error": "run_not_found"}
        observability = run.get("observability") if isinstance(run.get("observability"), dict) else {}
        return {
            "success": True,
            "run_id": run_id,
            "blueprint_id": run.get("blueprint_id"),
            "business_id": run.get("business_id"),
            "support_export": {
                "format": "agent_run_observability_v1",
                "run": {
                    "id": run.get("id"),
                    "status": run.get("status"),
                    "started_at": run.get("started_at"),
                    "completed_at": run.get("completed_at"),
                    "error_text": run.get("error_text"),
                },
                "observability": observability,
                "steps": run.get("steps") or [],
                "artifacts": run.get("artifacts") or [],
                "approvals": run.get("approvals") or [],
            },
        }

    def render_run_support_export_markdown(self, run_id: str, user_data: Dict[str, Any]) -> str:
        result = self.build_run_support_export(run_id, user_data)
        if not result.get("success"):
            return "# Agent Run Support Export\n\n- run not found\n"
        bundle = result.get("support_export") if isinstance(result.get("support_export"), dict) else {}
        run = bundle.get("run") if isinstance(bundle.get("run"), dict) else {}
        observability = bundle.get("observability") if isinstance(bundle.get("observability"), dict) else {}
        cost_tokens = observability.get("cost_tokens") if isinstance(observability.get("cost_tokens"), dict) else {}
        lines = [
            "# Agent Run Support Export",
            "",
            f"- run_id: `{run.get('id')}`",
            f"- blueprint_id: `{result.get('blueprint_id')}`",
            f"- business_id: `{result.get('business_id')}`",
            f"- status: `{run.get('status')}`",
            f"- errors: `{len(observability.get('errors') or [])}`",
            f"- action_ids: `{', '.join(observability.get('action_ids') or []) or 'none'}`",
            f"- settled_tokens: `{cost_tokens.get('settled_tokens') or 0}`",
            f"- total_cost: `{cost_tokens.get('total_cost') or 0}`",
            "",
            "## Billing",
        ]
        billing = observability.get("billing_ledger") if isinstance(observability.get("billing_ledger"), dict) else {}
        for item in billing.get("actions") or []:
            lines.append(
                f"- `{item.get('action_id') or 'no-action'}` {item.get('capability') or 'capability'}: "
                f"reserve/settle/release "
                f"`{item.get('reserved_tokens') or 0}/{item.get('settled_tokens') or 0}/{item.get('released_tokens') or 0}`, "
                f"inflight `{item.get('inflight_reserved_tokens') or 0}`"
            )
        if not billing.get("actions"):
            lines.append("- none")
        lines.extend(
            [
                "",
                "## Recovery Actions",
            ]
        )
        for item in observability.get("recovery_actions") or []:
            lines.append(f"- `{item.get('code')}` {item.get('label')}")
        if not observability.get("recovery_actions"):
            lines.append("- none")
        lines.append("")
        lines.append("## Delivery")
        delivery = observability.get("delivery_status") if isinstance(observability.get("delivery_status"), dict) else {}
        lines.append(f"- state: `{delivery.get('state') or 'unknown'}`")
        lines.append(f"- attempts: `{delivery.get('attempts_total') or 0}`")
        lines.append("")
        return "\n".join(lines)

    def _build_run_observability(
        self,
        run: Dict[str, Any],
        steps: List[Dict[str, Any]],
        artifacts: List[Dict[str, Any]],
        approvals: List[Dict[str, Any]],
        user_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        action_ids = self._extract_action_ids(steps)
        action_observations = []
        for action_id in action_ids:
            action_observations.append(self._load_action_observability(action_id, user_data))

        step_errors = [
            {
                "source": "agent_step",
                "step_id": step.get("id"),
                "step_key": step.get("step_key"),
                "status": step.get("status"),
                "error_text": step.get("error_text"),
            }
            for step in steps
            if step.get("error_text") or str(step.get("status") or "") in {"failed", "blocked", "rejected"}
        ]
        action_errors = []
        for observation in action_observations:
            if observation.get("error"):
                action_errors.append({"source": "openclaw_action", "action_id": observation.get("action_id"), "error_text": observation.get("error")})
            for item in observation.get("errors") or []:
                action_errors.append(item)

        cost_tokens = self._aggregate_cost_tokens(action_observations)
        billing_ledger = self._build_billing_ledger(action_observations)
        delivery_status = self._build_delivery_status(artifacts, action_observations)
        domain_requests = self._load_domain_request_observability(run, steps, action_ids)
        integration_preflight = self._build_run_integration_preflight(run)
        recovery_actions = self._build_recovery_actions(run, step_errors + action_errors, delivery_status, action_ids)
        preview_summary = self._build_preview_summary(run, steps, artifacts, approvals, domain_requests, integration_preflight)

        return {
            "schema": "agent_run_observability_v1",
            "preview_summary": preview_summary,
            "run_history": {
                "run_id": run.get("id"),
                "blueprint_id": run.get("blueprint_id"),
                "business_id": run.get("business_id"),
                "status": run.get("status"),
                "started_at": run.get("started_at"),
                "completed_at": run.get("completed_at"),
            },
            "step_history": {
                "count": len(steps),
                "completed": len([step for step in steps if str(step.get("status") or "") == "completed"]),
                "failed": len([step for step in steps if str(step.get("status") or "") in {"failed", "blocked", "rejected"}]),
                "items": steps,
            },
            "artifacts": {"count": len(artifacts), "items": artifacts},
            "approvals": {
                "count": len(approvals),
                "pending": len([item for item in approvals if str(item.get("status") or "") == "pending"]),
                "items": approvals,
            },
            "action_ids": action_ids,
            "action_ledger": {
                "count": len(action_observations),
                "items": action_observations,
            },
            "domain_requests": {
                "count": len(domain_requests),
                "pending": len(
                    [
                        item
                        for item in domain_requests
                        if str(item.get("approval_state") or item.get("apply_state") or item.get("status") or "")
                        in {
                            "pending",
                            "pending_human",
                            "not_applied",
                            "publish_requested",
                            "request_created",
                            "provider_request_queued",
                        }
                    ]
                ),
                "items": domain_requests,
            },
            "integration_preflight": integration_preflight,
            "delivery_status": delivery_status,
            "cost_tokens": cost_tokens,
            "billing_ledger": billing_ledger,
            "errors": step_errors + action_errors,
            "recovery_actions": recovery_actions,
            "support_export": {
                "endpoint": f"/api/agent-runs/{run.get('id')}/support-export",
                "formats": ["json", "markdown"],
                "source": "agent_run_detail",
            },
        }

    def _build_preview_summary(
        self,
        run: Dict[str, Any],
        steps: List[Dict[str, Any]],
        artifacts: List[Dict[str, Any]],
        approvals: List[Dict[str, Any]],
        domain_requests: List[Dict[str, Any]],
        integration_preflight: Dict[str, Any],
    ) -> Dict[str, Any]:
        run_input = self._run_input(run)
        preview_context = run_input.get("preview_context") if isinstance(run_input.get("preview_context"), dict) else {}
        safe_preview = bool(run_input.get("preview_mode")) and run_input.get("external_side_effects_allowed") is False
        completed_steps = [
            str(step.get("step_key") or step.get("key") or step.get("step_type") or "")
            for step in steps
            if str(step.get("status") or "") == "completed"
        ]
        blocked_steps = [
            {
                "key": str(step.get("step_key") or step.get("key") or ""),
                "status": str(step.get("status") or ""),
                "reason": str(step.get("error_text") or ""),
            }
            for step in steps
            if str(step.get("status") or "") in {"blocked", "failed", "rejected"}
        ]
        artifact_cards = []
        for artifact in artifacts:
            payload = artifact.get("payload_json") if isinstance(artifact.get("payload_json"), dict) else {}
            artifact_cards.append(
                {
                    "type": str(artifact.get("artifact_type") or ""),
                    "title": str(artifact.get("title") or artifact.get("artifact_type") or ""),
                    "summary": self._artifact_summary(payload),
                }
            )
        pending_approvals = [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("approval_type") or ""),
                "approval_type": str(item.get("approval_type") or ""),
                "status": str(item.get("status") or ""),
            }
            for item in approvals
            if str(item.get("status") or "") == "pending"
        ]
        waiting_actions = []
        for item in domain_requests:
            state = str(item.get("approval_state") or item.get("apply_state") or item.get("status") or "")
            if state in {"pending", "pending_human", "not_applied", "publish_requested", "request_created", "provider_request_queued"}:
                waiting_actions.append(
                    {
                        "kind": str(item.get("kind") or ""),
                        "state": state,
                        "why": str(item.get("why_waiting") or ""),
                        "provider_write_performed": bool(item.get("provider_write_performed")),
                    }
                )
        openclaw_action_plan = self._preview_summary_openclaw_action_plan(run_input.get("openclaw_action_plan"))
        policy_envelope = self._preview_summary_policy_envelope(run_input.get("policy_envelope"), safe_preview)
        approval_gate = {
            "pending_approvals_count": len(pending_approvals),
            "waiting_actions_count": len(waiting_actions),
            "external_actions_performed": self._external_actions_performed(domain_requests),
            "reason": "LocalOS approval gate останавливает внешние записи и отправки до решения человека.",
        }
        next_step = self._preview_next_step(run, integration_preflight, pending_approvals, waiting_actions)
        return {
            "schema": "localos_agent_preview_summary_v1",
            "is_preview": bool(run_input.get("preview_mode")),
            "safe_preview": safe_preview,
            "headline": self._preview_summary_headline(run, safe_preview, integration_preflight, pending_approvals, waiting_actions),
            "understood_task": str(preview_context.get("understood_task") or run_input.get("goal") or ""),
            "data_sources": self._preview_summary_list(preview_context.get("data_sources") or run_input.get("required_connectors") or []),
            "manual_control": str(preview_context.get("manual_control") or "Перед внешним действием нужен approval."),
            "completed_steps": [item for item in completed_steps if item],
            "blocked_steps": blocked_steps,
            "artifacts": artifact_cards[:6],
            "pending_approvals": pending_approvals,
            "waiting_actions": waiting_actions[:6],
            "preflight_ready": bool(integration_preflight.get("ready")),
            "openclaw_action_plan": openclaw_action_plan,
            "openclaw_action_count": len(openclaw_action_plan),
            "policy_envelope": policy_envelope,
            "approval_gate": approval_gate,
            "external_side_effects_allowed": bool(run_input.get("external_side_effects_allowed")),
            "external_actions_performed": approval_gate["external_actions_performed"],
            "activation_hint": self._preview_activation_hint(run, integration_preflight, pending_approvals, waiting_actions),
            "next_step": next_step,
            "next_step_label": self._preview_next_step_label(next_step),
            "next_step_description": self._preview_next_step_description(next_step),
        }

    def _preview_summary_openclaw_action_plan(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if not isinstance(item, dict):
                continue
            result.append(
                {
                    "step_key": str(item.get("step_key") or item.get("key") or ""),
                    "title": str(item.get("title") or item.get("step_key") or item.get("capability") or "OpenClaw action"),
                    "capability": str(item.get("capability") or ""),
                    "provider": str(item.get("provider") or ""),
                    "provider_action_ref": str(item.get("provider_action_ref") or item.get("provider_action") or ""),
                    "provider_policy": str(item.get("provider_policy") or "localos_envelope"),
                    "risk_class": str(item.get("risk_class") or ""),
                    "approval_class": str(item.get("approval_class") or ""),
                    "requires_approval": bool(item.get("requires_approval")),
                }
            )
            if len(result) >= 12:
                break
        return result

    def _preview_summary_policy_envelope(self, value: Any, safe_preview: bool) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {
                "execution_boundary": "openclaw_action_orchestrator",
                "external_side_effects_allowed_in_preview": False,
                "approval_owner": "LocalOS",
                "billing_owner": "LocalOS",
                "audit_owner": "LocalOS",
                "safe_preview": safe_preview,
            }
        return {
            "execution_boundary": str(value.get("execution_boundary") or "openclaw_action_orchestrator"),
            "external_side_effects_allowed_in_preview": bool(value.get("external_side_effects_allowed_in_preview")) is True,
            "approval_owner": str(value.get("approval_owner") or "LocalOS"),
            "billing_owner": str(value.get("billing_owner") or "LocalOS"),
            "audit_owner": str(value.get("audit_owner") or "LocalOS"),
            "cost_owner": str(value.get("cost_owner") or value.get("billing_owner") or "LocalOS"),
            "safe_preview": safe_preview,
        }

    def _artifact_summary(self, payload: Dict[str, Any]) -> str:
        for key in ["summary", "body", "message", "title", "result"]:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:240]
            if isinstance(value, dict):
                nested = value.get("summary") or value.get("body") or value.get("message") or value.get("title")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()[:240]
        items = payload.get("items")
        if isinstance(items, list) and items:
            return f"Подготовлено элементов: {len(items)}"
        return "Artifact сохранён для проверки."

    def _preview_summary_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    label = str(item.get("title") or item.get("provider") or item.get("key") or "").strip()
                else:
                    label = str(item or "").strip()
                if label and label not in result:
                    result.append(label)
            return result[:8]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _external_actions_performed(self, domain_requests: List[Dict[str, Any]]) -> bool:
        for item in domain_requests:
            if item.get("provider_write_performed") is True:
                return True
            if item.get("external_dispatch_performed") is True:
                return True
        return False

    def _preview_summary_headline(
        self,
        run: Dict[str, Any],
        safe_preview: bool,
        integration_preflight: Dict[str, Any],
        pending_approvals: List[Dict[str, Any]],
        waiting_actions: List[Dict[str, Any]],
    ) -> str:
        if not integration_preflight.get("ready"):
            return "Preview не готов: сначала подключите обязательные сервисы."
        if str(run.get("status") or "") in {"failed", "blocked"}:
            return "Preview остановился на ошибке. Проверьте блокеры ниже."
        if safe_preview and (pending_approvals or waiting_actions):
            return "Preview показал результат и места, где агент остановится на approval."
        if safe_preview:
            return "Safe preview выполнен без внешних действий."
        return "Запуск выполнен. Проверьте действия и approvals."

    def _preview_next_step(
        self,
        run: Dict[str, Any],
        integration_preflight: Dict[str, Any],
        pending_approvals: List[Dict[str, Any]],
        waiting_actions: List[Dict[str, Any]],
    ) -> str:
        if not integration_preflight.get("ready"):
            return "connect_required_integrations"
        if str(run.get("status") or "") in {"failed", "blocked", "rejected"}:
            return "fix_preview_error"
        if pending_approvals or waiting_actions:
            return "review_approvals"
        if str(run.get("status") or "") in {"completed", "waiting_approval"}:
            return "check_activation_gate"
        return "review_preview"

    def _preview_next_step_label(self, next_step: str) -> str:
        labels = {
            "connect_required_integrations": "Подключить сервисы",
            "fix_preview_error": "Исправить логику",
            "review_approvals": "Проверить approval",
            "check_activation_gate": "Проверить активацию",
            "review_preview": "Проверить preview",
        }
        return labels.get(next_step, "Проверить preview")

    def _preview_next_step_description(self, next_step: str) -> str:
        descriptions = {
            "connect_required_integrations": "Сначала подключите обязательные источники и каналы, затем повторите preview.",
            "fix_preview_error": "Preview нашёл ошибку или блокер. Исправьте compiled workflow перед активацией.",
            "review_approvals": "Preview подготовил внешнее действие, но реальные отправки и записи останутся за approval gate.",
            "check_activation_gate": "Preview прошёл безопасно. Если gate активации зелёный, версию можно включать.",
            "review_preview": "Проверьте результат preview и запустите повторно, если нужно уточнить данные.",
        }
        return descriptions.get(next_step, "Проверьте результат preview и следующий шаг агента.")

    def _preview_activation_hint(
        self,
        run: Dict[str, Any],
        integration_preflight: Dict[str, Any],
        pending_approvals: List[Dict[str, Any]],
        waiting_actions: List[Dict[str, Any]],
    ) -> str:
        if not integration_preflight.get("ready"):
            return "Активация закрыта: не пройден preflight подключений."
        if str(run.get("status") or "") in {"failed", "blocked"}:
            return "Активация закрыта: preview завершился ошибкой или блокером."
        if pending_approvals or waiting_actions:
            return "Агент можно активировать после проверки preview: реальные внешние действия всё равно остановятся на approval."
        return "Preview готов. Если activation gate зелёный, версию можно активировать."

    def _build_run_integration_preflight(self, run: Dict[str, Any]) -> Dict[str, Any]:
        blueprint = self._load_blueprint(str(run.get("blueprint_id") or ""))
        metadata = parse_json_field((blueprint or {}).get("metadata_json"), {})
        metadata = metadata if isinstance(metadata, dict) else {}
        return build_agent_integration_preflight(
            self.cursor,
            business_id=str(run.get("business_id") or ""),
            metadata=metadata,
            input_payload=self._run_input(run),
        )

    def _load_domain_request_observability(
        self,
        run: Dict[str, Any],
        steps: List[Dict[str, Any]],
        action_ids: List[str],
    ) -> List[Dict[str, Any]]:
        refs = self._extract_domain_request_refs(steps, action_ids)
        business_id = str(run.get("business_id") or "").strip()
        if not business_id:
            return []
        items = []
        items.extend(self._load_sheet_operation_requests(business_id, refs))
        items.extend(self._load_communication_requests(business_id, refs))
        items.extend(self._load_review_publish_requests(business_id, refs))
        items.extend(self._load_service_optimization_requests(business_id, refs))
        items.extend(self._load_finance_import_requests(business_id, refs))
        return items[:50]

    def _extract_domain_request_refs(self, steps: List[Dict[str, Any]], action_ids: List[str]) -> Dict[str, List[str]]:
        refs = {
            "action_ids": list(action_ids),
            "request_ids": [],
            "draft_ids": [],
            "review_ids": [],
            "batch_ids": [],
        }
        for step in steps:
            output = step.get("output_json") if isinstance(step.get("output_json"), dict) else {}
            orchestrator = output.get("orchestrator") if isinstance(output.get("orchestrator"), dict) else {}
            nested_result = orchestrator.get("result") if isinstance(orchestrator.get("result"), dict) else {}
            candidates = {
                "request_ids": [output.get("request_id"), nested_result.get("request_id")],
                "draft_ids": [output.get("draft_id"), nested_result.get("draft_id")],
                "review_ids": [output.get("review_id"), nested_result.get("review_id")],
                "action_ids": [output.get("action_id"), orchestrator.get("action_id"), nested_result.get("action_id")],
                "batch_ids": [],
            }
            approved_executor = output.get("approved_executor") if isinstance(output.get("approved_executor"), dict) else {}
            executor_items = approved_executor.get("items") if isinstance(approved_executor.get("items"), list) else []
            for item in executor_items:
                if isinstance(item, dict):
                    candidates["batch_ids"].append(item.get("batch_id"))
            for key, values in candidates.items():
                for value in values:
                    text = str(value or "").strip()
                    if text and text not in refs[key]:
                        refs[key].append(text)
        return refs

    def _load_sheet_operation_requests(self, business_id: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        rows = self._select_domain_request_rows(
            "agent_sheet_operation_requests",
            """
            SELECT id, action_id, integration_id, spreadsheet_id, sheet_name, operation,
                   status, approval_state, apply_state, row_values_json, mapping_json,
                   limits_json, provider_write_performed, error_text, created_at
            FROM agent_sheet_operation_requests
            WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
            bool(refs.get("request_ids") or refs.get("action_ids")),
        )
        result = []
        for row in rows:
            approval_state = str(row.get("approval_state") or "").strip()
            apply_state = str(row.get("apply_state") or "").strip()
            waiting_reason = "External spreadsheet write requires human approval before provider write."
            if approval_state == "approved":
                waiting_reason = "Human approved; controlled Google Sheets provider request is queued. No spreadsheet write has run yet."
            if apply_state in {"provider_unavailable", "provider_failed"}:
                waiting_reason = "Human approved; Google Sheets provider executor needs attention before external write can complete."
            if apply_state == "applied":
                waiting_reason = "Google Sheets provider executor applied the approved request."
            provider_handoff = {
                "provider_executor": "manual_controlled_google_sheets_append",
                "handoff_state": apply_state or row.get("apply_state"),
                "operation": row.get("operation") or "append_row",
                "integration_id": row.get("integration_id"),
                "spreadsheet_id": row.get("spreadsheet_id"),
                "sheet_name": row.get("sheet_name"),
                "provider_write_performed": bool(row.get("provider_write_performed")),
                "error": row.get("error_text"),
            }
            result.append(
                {
                    "kind": "sheet_operation_request",
                    "id": row.get("id"),
                    "action_id": row.get("action_id"),
                    "title": "Google Sheets update request",
                    "summary": f"{row.get('operation') or 'append_row'} -> {row.get('sheet_name') or row.get('spreadsheet_id') or 'sheet'}",
                    "status": row.get("status"),
                    "approval_state": approval_state or row.get("approval_state"),
                    "apply_state": apply_state or row.get("apply_state"),
                    "why_waiting": waiting_reason,
                    "row_values": parse_json_field(row.get("row_values_json"), []),
                    "mapping": parse_json_field(row.get("mapping_json"), {}),
                    "limits": parse_json_field(row.get("limits_json"), {}),
                    "provider_handoff": provider_handoff,
                    "error": row.get("error_text"),
                    "provider_write_performed": bool(row.get("provider_write_performed")),
                    "created_at": row.get("created_at"),
                }
            )
        return result

    def _load_finance_import_requests(self, business_id: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        rows = self._select_domain_request_rows(
            "finance_import_batches",
            """
            SELECT id, business_id, source_type, status, file_name, file_hash, rows_total,
                   rows_imported, rows_skipped, rows_failed, mapping_json, error_log,
                   created_at, completed_at
            FROM finance_import_batches
            WHERE business_id = %s AND (
                id = ANY(%s) OR file_hash = ANY(%s)
            )
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id, refs.get("batch_ids") or [], (refs.get("request_ids") or []) + (refs.get("action_ids") or [])),
            bool(refs.get("batch_ids") or refs.get("request_ids") or refs.get("action_ids")),
        )
        result = []
        for row in rows:
            imported = int(row.get("rows_imported") or 0)
            skipped = int(row.get("rows_skipped") or 0)
            failed = int(row.get("rows_failed") or 0)
            total = int(row.get("rows_total") or 0)
            status = str(row.get("status") or "").strip()
            if status == "completed":
                waiting_reason = "Approved finance import was applied to LocalOS Finance."
            elif status == "completed_with_errors":
                waiting_reason = "Approved finance import was partially applied; review failed rows."
            else:
                waiting_reason = "Finance import is waiting for approved apply completion."
            result.append(
                {
                    "kind": "finance_transaction_request",
                    "id": row.get("file_hash") or row.get("id"),
                    "batch_id": row.get("id"),
                    "title": "Finance transaction import",
                    "summary": f"{imported}/{total} finance rows imported · {skipped} skipped · {failed} failed",
                    "status": status or row.get("status"),
                    "approval_state": "approved" if status.startswith("completed") else "pending_human",
                    "apply_state": "applied" if imported else "not_applied",
                    "why_waiting": waiting_reason,
                    "rows_total": total,
                    "rows_imported": imported,
                    "rows_skipped": skipped,
                    "rows_failed": failed,
                    "mapping": parse_json_field(row.get("mapping_json"), {}),
                    "errors": parse_json_field(row.get("error_log"), []),
                    "localos_write_performed": imported > 0,
                    "provider_write_performed": False,
                    "created_at": row.get("created_at"),
                    "completed_at": row.get("completed_at"),
                }
            )
        return result

    def _load_communication_requests(self, business_id: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        rows = self._select_domain_request_rows(
            "agent_communication_requests",
            """
            SELECT id, action_id, business_id, capability, message_type, status, channel, recipient_count,
                   recipients_json, limits_json, consent_json, delivery_state, created_at
            FROM agent_communication_requests
            WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
            bool(refs.get("request_ids") or refs.get("action_ids")),
        )
        result = []
        for row in rows:
            recipient_count = int(row.get("recipient_count") or 0)
            channel = str(row.get("channel") or "channel").strip()
            status = str(row.get("status") or "").strip()
            approval_state = "approved" if status.startswith("approved_") else "pending_human"
            waiting_reason = "External customer message requires approval, consent validation, and send limits."
            if approval_state == "approved":
                waiting_reason = "Human approved; waiting for controlled channel dispatch. No external send has run yet."
            delivery_journal = self._load_communication_delivery_journal(
                str(row.get("id") or ""),
                str(row.get("action_id") or ""),
                str(row.get("business_id") or ""),
            )
            result.append(
                {
                    "kind": "communication_request",
                    "id": row.get("id"),
                    "action_id": row.get("action_id"),
                    "title": "Communication send request",
                    "summary": f"{row.get('message_type') or row.get('capability') or 'message'} -> {channel} · {recipient_count} recipients",
                    "status": status or row.get("status"),
                    "approval_state": approval_state,
                    "delivery_state": row.get("delivery_state"),
                    "why_waiting": waiting_reason,
                    "recipients": parse_json_field(row.get("recipients_json"), [])[:10],
                    "recipient_count": recipient_count,
                    "limits": parse_json_field(row.get("limits_json"), {}),
                    "consent": parse_json_field(row.get("consent_json"), {}),
                    "delivery_journal": {
                        "count": len(delivery_journal),
                        "queued": len([item for item in delivery_journal if str(item.get("delivery_state") or "") == "queued_for_dispatch"]),
                        "blocked": len([item for item in delivery_journal if str(item.get("delivery_state") or "").startswith("blocked")]),
                        "items": delivery_journal[:10],
                    },
                    "provider_write_performed": False,
                    "created_at": row.get("created_at"),
                }
            )
        return result

    def _load_communication_delivery_journal(self, request_id: str, action_id: str, business_id: str) -> List[Dict[str, Any]]:
        rows = self._select_domain_request_rows(
            "agent_communication_delivery_journal",
            """
            SELECT id, request_id, action_id, recipient_key, channel, status,
                   delivery_state, consent_json, limits_json, router_handoff_json,
                   provider_write_performed, created_at
            FROM agent_communication_delivery_journal
            WHERE business_id = %s AND (request_id = %s OR action_id = %s)
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id, request_id, action_id),
            bool((request_id or action_id) and business_id),
        )
        result = []
        for row in rows:
            result.append(
                {
                    "id": row.get("id"),
                    "recipient_key": row.get("recipient_key"),
                    "channel": row.get("channel"),
                    "status": row.get("status"),
                    "delivery_state": row.get("delivery_state"),
                    "consent": parse_json_field(row.get("consent_json"), {}),
                    "limits": parse_json_field(row.get("limits_json"), {}),
                    "router_handoff": parse_json_field(row.get("router_handoff_json"), {}),
                    "provider_write_performed": bool(row.get("provider_write_performed")),
                    "created_at": row.get("created_at"),
                }
            )
        return result

    def _load_review_publish_requests(self, business_id: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        ids = refs.get("draft_ids") or refs.get("request_ids") or []
        review_ids = refs.get("review_ids") or []
        rows = self._select_domain_request_rows(
            "reviewreplydrafts",
            """
            SELECT id, review_id, status, source, rating, author_name,
                   generated_text, edited_text, tone, created_at
            FROM reviewreplydrafts
            WHERE business_id = %s AND (id = ANY(%s) OR review_id = ANY(%s))
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id, ids, review_ids),
            bool(ids or review_ids),
        )
        result = []
        for row in rows:
            status = str(row.get("status") or "").strip()
            approval_state = "approved" if status.startswith("approved_") else "pending_human"
            waiting_reason = "Publishing a reply on behalf of the business requires approval."
            if approval_state == "approved":
                waiting_reason = "Human approved; waiting for controlled provider publish executor."
            publish_requests = self._load_review_provider_publish_requests(
                str(row.get("id") or ""),
                str(row.get("review_id") or ""),
                business_id,
            )
            if publish_requests:
                waiting_reason = "Human approved; controlled provider publish request is queued. No provider write has run yet."
            result.append(
                {
                    "kind": "review_publish_request",
                    "id": row.get("id"),
                    "review_id": row.get("review_id"),
                    "title": "Review reply publish request",
                    "summary": f"{row.get('source') or 'review'} · {row.get('rating') or '-'} stars · {row.get('author_name') or 'author'}",
                    "status": status or row.get("status"),
                    "approval_state": approval_state,
                    "why_waiting": waiting_reason,
                    "draft_text": row.get("edited_text") or row.get("generated_text"),
                    "tone": row.get("tone"),
                    "publish_requests": {
                        "count": len(publish_requests),
                        "queued": len(
                            [
                                item
                                for item in publish_requests
                                if str(item.get("publish_state") or "") == "provider_request_queued"
                            ]
                        ),
                        "items": publish_requests[:10],
                    },
                    "provider_write_performed": False,
                    "created_at": row.get("created_at"),
                }
            )
        return result

    def _load_review_provider_publish_requests(self, draft_id: str, review_id: str, business_id: str) -> List[Dict[str, Any]]:
        rows = self._select_domain_request_rows(
            "agent_review_publish_requests",
            """
            SELECT id, draft_id, review_id, source, status, publish_state,
                   provider_request_json, audit_json, provider_write_performed,
                   error_text, created_at
            FROM agent_review_publish_requests
            WHERE business_id = %s AND (draft_id = %s OR review_id = %s)
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id, draft_id, review_id),
            bool((draft_id or review_id) and business_id),
        )
        result = []
        for row in rows:
            result.append(
                {
                    "id": row.get("id"),
                    "draft_id": row.get("draft_id"),
                    "review_id": row.get("review_id"),
                    "source": row.get("source"),
                    "status": row.get("status"),
                    "publish_state": row.get("publish_state"),
                    "provider_request": parse_json_field(row.get("provider_request_json"), {}),
                    "audit": parse_json_field(row.get("audit_json"), {}),
                    "provider_write_performed": bool(row.get("provider_write_performed")),
                    "error": row.get("error_text"),
                    "created_at": row.get("created_at"),
                }
            )
        return result

    def _load_service_optimization_requests(self, business_id: str, refs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        rows = self._select_domain_request_rows(
            "agent_service_optimization_requests",
            """
            SELECT id, action_id, status, service_count, suggestions_json, diff_json,
                   apply_state, created_at
            FROM agent_service_optimization_requests
            WHERE business_id = %s AND (id = ANY(%s) OR action_id = ANY(%s))
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id, refs.get("request_ids") or [], refs.get("action_ids") or []),
            bool(refs.get("request_ids") or refs.get("action_ids")),
        )
        result = []
        for row in rows:
            status = str(row.get("status") or "").strip()
            apply_state = str(row.get("apply_state") or "").strip()
            approval_state = "approved" if status.startswith("approved_") or apply_state == "apply_ready" else "pending_human"
            waiting_reason = "Service catalog changes require review before applying to business data."
            if approval_state == "approved":
                waiting_reason = "Human approved; visual diff is ready for the controlled apply executor."
            result.append(
                {
                    "kind": "service_optimization_request",
                    "id": row.get("id"),
                    "action_id": row.get("action_id"),
                    "title": "Service optimization request",
                    "summary": f"{row.get('service_count') or 0} services prepared",
                    "status": status or row.get("status"),
                    "approval_state": approval_state,
                    "apply_state": apply_state or row.get("apply_state"),
                    "why_waiting": waiting_reason,
                    "suggestions": parse_json_field(row.get("suggestions_json"), []),
                    "visual_diff": parse_json_field(row.get("diff_json"), []),
                    "provider_write_performed": False,
                    "created_at": row.get("created_at"),
                }
            )
        return result

    def _select_domain_request_rows(self, table_name: str, query: str, params: Any, has_refs: bool) -> List[Dict[str, Any]]:
        if not has_refs or not self._domain_request_table_exists(table_name):
            return []
        try:
            self.cursor.execute(query, params)
            return [dict(row) for row in (self.cursor.fetchall() or [])]
        except Exception:
            return []

    def _domain_request_table_exists(self, table_name: str) -> bool:
        try:
            self.cursor.execute("SELECT to_regclass(%s) AS table_name", (table_name,))
            row = self.cursor.fetchone()
        except Exception:
            return False
        if not row:
            return False
        if isinstance(row, dict):
            return bool(row.get("table_name") or row.get("to_regclass"))
        return bool(row[0])

    def _load_action_observability(self, action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        if not user_data:
            return {
                "action_id": action_id,
                "status": "linked",
                "support_package_loaded": False,
                "error": "user_context_required_for_openclaw_observability",
            }
        support = self.orchestrator.get_action_support_package(action_id, user_data, limit=100, full=False)
        if not support.get("success"):
            return {
                "action_id": action_id,
                "status": "unavailable",
                "support_package_loaded": False,
                "error": support.get("error") or "support_package_unavailable",
            }
        billing = support.get("billing") if isinstance(support.get("billing"), dict) else {}
        timeline = support.get("timeline") if isinstance(support.get("timeline"), dict) else {}
        events = timeline.get("events") if isinstance(timeline.get("events"), list) else []
        return {
            "action_id": action_id,
            "capability": support.get("capability"),
            "status": support.get("status"),
            "trace_id": support.get("trace_id"),
            "delivery_stats": support.get("delivery_stats") if isinstance(support.get("delivery_stats"), dict) else {},
            "billing_summary": billing.get("summary") if isinstance(billing.get("summary"), dict) else {},
            "billing_entries": billing.get("entries") if isinstance(billing.get("entries"), list) else [],
            "timeline": {
                "count": len(events),
                "events": events,
            },
            "errors": self._extract_timeline_errors(action_id, events),
            "support_package_loaded": True,
        }

    def _extract_action_ids(self, steps: List[Dict[str, Any]]) -> List[str]:
        result = []
        for step in steps:
            output = step.get("output_json") if isinstance(step.get("output_json"), dict) else {}
            candidates = [
                output.get("action_id"),
            ]
            orchestrator = output.get("orchestrator") if isinstance(output.get("orchestrator"), dict) else {}
            candidates.extend([orchestrator.get("action_id")])
            nested_result = orchestrator.get("result") if isinstance(orchestrator.get("result"), dict) else {}
            candidates.append(nested_result.get("action_id"))
            for candidate in candidates:
                action_id = str(candidate or "").strip()
                if action_id and action_id not in result:
                    result.append(action_id)
        return result

    def _aggregate_cost_tokens(self, action_observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        reserved_tokens = 0
        settled_tokens = 0
        released_tokens = 0
        total_cost = 0.0
        for observation in action_observations:
            summary = observation.get("billing_summary") if isinstance(observation.get("billing_summary"), dict) else {}
            reserved_tokens += int(summary.get("reserved_tokens") or 0)
            settled_tokens += int(summary.get("settled_tokens") or 0)
            released_tokens += int(summary.get("released_tokens") or 0)
            total_cost += float(summary.get("total_cost") or 0.0)
        return {
            "reserved_tokens": reserved_tokens,
            "settled_tokens": settled_tokens,
            "released_tokens": released_tokens,
            "inflight_reserved_tokens": max(reserved_tokens - settled_tokens - released_tokens, 0),
            "total_cost": round(total_cost, 6),
        }

    def _build_billing_ledger(self, action_observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        action_items = []
        entries = []
        for observation in action_observations:
            summary = observation.get("billing_summary") if isinstance(observation.get("billing_summary"), dict) else {}
            action_entries = observation.get("billing_entries") if isinstance(observation.get("billing_entries"), list) else []
            action_id = str(observation.get("action_id") or "").strip()
            capability = str(observation.get("capability") or "").strip()
            action_items.append(
                {
                    "action_id": action_id,
                    "capability": capability,
                    "status": observation.get("status"),
                    "reserved_tokens": int(summary.get("reserved_tokens") or 0),
                    "settled_tokens": int(summary.get("settled_tokens") or 0),
                    "released_tokens": int(summary.get("released_tokens") or 0),
                    "inflight_reserved_tokens": int(summary.get("inflight_reserved_tokens") or 0),
                    "total_cost": float(summary.get("total_cost") or 0.0),
                    "entry_count": len(action_entries),
                }
            )
            for entry in action_entries:
                if not isinstance(entry, dict):
                    continue
                entries.append(
                    {
                        "action_id": action_id,
                        "capability": capability,
                        "entry_type": entry.get("entry_type"),
                        "tokens_in": int(entry.get("tokens_in") or 0),
                        "tokens_out": int(entry.get("tokens_out") or 0),
                        "cost": float(entry.get("cost") or 0.0),
                        "tariff_id": entry.get("tariff_id"),
                        "month_key": entry.get("month_key"),
                        "created_at": entry.get("created_at"),
                    }
                )
        totals = self._aggregate_cost_tokens(action_observations)
        return {
            "summary": totals,
            "actions": action_items,
            "entries": entries[:100],
        }

    def _build_delivery_status(self, artifacts: List[Dict[str, Any]], action_observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        queued_count = 0
        dispatch_states = []
        for artifact in artifacts:
            payload = artifact.get("payload_json") if isinstance(artifact.get("payload_json"), dict) else {}
            queued_count += int(payload.get("queued_count") or payload.get("queue_count") or 0)
            state = str(payload.get("dispatch_state") or "").strip()
            if state:
                dispatch_states.append(state)
        attempts_total = 0
        attempts_failed = 0
        attempts_success = 0
        last_error = ""
        for observation in action_observations:
            stats = observation.get("delivery_stats") if isinstance(observation.get("delivery_stats"), dict) else {}
            attempts_total += int(stats.get("attempts_total") or 0)
            attempts_success += int(stats.get("attempts_success") or 0)
            attempts_failed += int(stats.get("attempts_failed") or 0)
            if stats.get("last_error"):
                last_error = str(stats.get("last_error") or "")
        state = "not_applicable"
        if queued_count > 0:
            state = "queued"
        if attempts_total > 0 and attempts_failed == 0:
            state = "delivered"
        if attempts_failed > 0:
            state = "delivery_attention"
        return {
            "state": state,
            "queued_count": queued_count,
            "dispatch_states": dispatch_states,
            "attempts_total": attempts_total,
            "attempts_success": attempts_success,
            "attempts_failed": attempts_failed,
            "last_error": last_error or None,
            "external_dispatch_performed": attempts_total > 0,
        }

    def _extract_timeline_errors(self, action_id: str, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        errors = []
        for event in events:
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            status = str(event.get("status") or "").lower()
            event_type = str(event.get("event_type") or "").lower()
            error_text = str(details.get("error_text") or details.get("error") or "").strip()
            if status in {"failed", "retry", "dlq"} or event_type in {"failed", "error"} or error_text:
                errors.append(
                    {
                        "source": str(event.get("source") or "openclaw_timeline"),
                        "action_id": action_id,
                        "event_type": event.get("event_type"),
                        "status": event.get("status"),
                        "error_text": error_text,
                    }
                )
        return errors

    def _build_recovery_actions(
        self,
        run: Dict[str, Any],
        errors: List[Dict[str, Any]],
        delivery_status: Dict[str, Any],
        action_ids: List[str],
    ) -> List[Dict[str, Any]]:
        actions = []
        if errors:
            actions.append(
                {
                    "code": "review_agent_run_errors",
                    "label": "Review failed agent steps and OpenClaw timeline events.",
                    "target": f"/api/agent-runs/{run.get('id')}/support-export",
                }
            )
        if str(delivery_status.get("state") or "") == "delivery_attention":
            actions.append(
                {
                    "code": "replay_or_inspect_callback_outbox",
                    "label": "Inspect callback delivery attempts and replay DLQ/retry items from the support boundary.",
                    "target": "/api/capabilities/callbacks/outbox/replay",
                }
            )
        if action_ids:
            actions.append(
                {
                    "code": "export_openclaw_support_bundle",
                    "label": "Export the linked OpenClaw support bundle from this agent run.",
                    "target": f"/api/agent-runs/{run.get('id')}/support-export?format=markdown",
                }
            )
        if str(run.get("status") or "") in {"failed", "rejected"}:
            actions.append(
                {
                    "code": "create_fixed_agent_version",
                    "label": "Use run feedback to create a corrected blueprint version.",
                    "target": f"/api/agent-runs/{run.get('id')}/feedback",
                }
            )
        return actions

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

    def _has_required_approval(self, run_id: str, step: Dict[str, Any]) -> bool:
        required_type = str(step.get("required_approval_type") or "").strip()
        if not required_type:
            return self._has_prior_approval(run_id)
        self.cursor.execute(
            """
            SELECT 1
            FROM agent_approvals
            WHERE run_id = %s
              AND status = 'approved'
              AND approval_type = %s
            LIMIT 1
            """,
            (run_id, required_type),
        )
        return bool(self.cursor.fetchone())

    def _capability_requires_approval(self, capability: str, step: Dict[str, Any]) -> bool:
        if bool(step.get("requires_approval")):
            return True
        lowered = capability.lower()
        return any(word in lowered for word in DANGEROUS_CAPABILITY_WORDS)

    def _build_approval_payload(self, run: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        approval_type = str(step.get("approval_type") or step.get("key") or "").strip()
        artifact_type = ""
        if approval_type == "shortlist":
            artifact_type = "lead_shortlist"
        if approval_type == "drafts":
            artifact_type = "message_drafts"
        if approval_type == "final_output":
            artifact_type = "agent_output_draft"
        if not artifact_type:
            return dict(payload)
        artifact_payload = self._latest_artifact_payload(str(run.get("id") or ""), artifact_type)
        if not artifact_payload:
            return dict(payload)
        return {
            **payload,
            "artifact_type": artifact_type,
            "artifact": artifact_payload,
            "count": artifact_payload.get("count", 0),
            "items": artifact_payload.get("items", []),
        }

    def _latest_artifact_payload(self, run_id: str, artifact_type: str) -> Dict[str, Any]:
        self.cursor.execute(
            """
            SELECT payload_json
            FROM agent_artifacts
            WHERE run_id = %s
              AND artifact_type = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (run_id, artifact_type),
        )
        row = self.cursor.fetchone()
        if not row:
            return {}
        payload = row.get("payload_json") if isinstance(row, dict) else row[0]
        parsed = parse_json_field(payload, {})
        return parsed if isinstance(parsed, dict) else {}

    def _latest_artifact_item_ids(self, run_id: str, artifact_type: str, id_key: str) -> List[str]:
        payload = self._latest_artifact_payload(run_id, artifact_type)
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get(id_key) or "").strip()
            if item_id:
                result.append(item_id)
        return list(dict.fromkeys(result))

    def _apply_shortlist_approval(self, run_id: str, user_id: str) -> None:
        run = self._load_run_header(run_id)
        if not run:
            return
        lead_ids = self._latest_artifact_item_ids(run_id, "lead_shortlist", "id")
        if not lead_ids:
            return
        self.cursor.execute(
            """
            UPDATE prospectingleads
            SET status = CASE
                    WHEN status IN ('channel_selected', 'draft_ready', 'queued_for_send', 'sent', 'delivered') THEN status
                    ELSE %s
                END,
                pipeline_status = %s,
                last_manual_action_at = NOW(),
                last_manual_action_by = %s,
                updated_at = NOW()
            WHERE business_id = %s
              AND id = ANY(%s)
            """,
            (SELECTED_FOR_OUTREACH, PIPELINE_IN_PROGRESS, user_id or None, str(run.get("business_id") or ""), lead_ids),
        )

    def _apply_drafts_approval(self, run_id: str, user_id: str) -> None:
        run = self._load_run_header(run_id)
        if not run:
            return
        draft_ids = self._latest_artifact_item_ids(run_id, "message_drafts", "id")
        if not draft_ids:
            return
        self.cursor.execute(
            """
            UPDATE outreachmessagedrafts
            SET status = %s,
                approved_text = COALESCE(NULLIF(edited_text, ''), generated_text),
                edited_text = COALESCE(NULLIF(edited_text, ''), generated_text),
                approved_by = %s,
                updated_at = NOW()
            WHERE id = ANY(%s)
              AND lead_id IN (
                    SELECT id
                    FROM prospectingleads
                    WHERE business_id = %s
              )
            """,
            (DRAFT_APPROVED, user_id or None, draft_ids, str(run.get("business_id") or "")),
        )
        self.cursor.execute(
            """
            UPDATE prospectingleads
            SET status = %s,
                pipeline_status = %s,
                updated_at = NOW()
            WHERE business_id = %s
              AND id IN (
                    SELECT lead_id
                    FROM outreachmessagedrafts
                    WHERE id = ANY(%s)
              )
            """,
            (DRAFT_READY, PIPELINE_IN_PROGRESS, str(run.get("business_id") or ""), draft_ids),
        )

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

    def _commit_cursor_connection(self) -> None:
        connection = getattr(self.cursor, "connection", None)
        commit = getattr(connection, "commit", None)
        if callable(commit):
            commit()
