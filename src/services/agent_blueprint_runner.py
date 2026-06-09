import json
import uuid
from typing import Any, Dict, List, Optional

from core.action_orchestrator import ActionOrchestrator
from services.agent_blueprint_workspace import build_generic_artifact_payload


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
        generic_payload = build_generic_artifact_payload(self.cursor, run, step, base_payload)
        if generic_payload is not None:
            return generic_payload
        return dict(base_payload)

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
        step_payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        run_input = parse_json_field(run.get("input_json"), {})
        if not isinstance(run_input, dict):
            run_input = {}
        payload = {**run_input, **step_payload}
        if capability == "outreach.send_batch" and not payload.get("draft_ids"):
            payload["draft_ids"] = self._latest_artifact_item_ids(str(run.get("id") or ""), "message_drafts", "id")
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
            "## Recovery Actions",
        ]
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
        delivery_status = self._build_delivery_status(artifacts, action_observations)
        recovery_actions = self._build_recovery_actions(run, step_errors + action_errors, delivery_status, action_ids)

        return {
            "schema": "agent_run_observability_v1",
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
            "delivery_status": delivery_status,
            "cost_tokens": cost_tokens,
            "errors": step_errors + action_errors,
            "recovery_actions": recovery_actions,
            "support_export": {
                "endpoint": f"/api/agent-runs/{run.get('id')}/support-export",
                "formats": ["json", "markdown"],
                "source": "agent_run_detail",
            },
        }

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
