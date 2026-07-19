import json
from datetime import datetime, timezone
from pathlib import Path


class FakeCursor:
    def __init__(self):
        self.tables = {
            "agent_blueprints": {},
            "agent_blueprint_versions": {},
            "agent_runs": {},
            "agent_run_steps": {},
            "agent_artifacts": {},
            "agent_approvals": {},
            "prospectingleads": {},
            "outreachmessagedrafts": {},
            "agent_sheet_operation_requests": {},
            "agent_communication_requests": {},
            "reviewreplydrafts": {},
            "agent_review_publish_requests": {},
            "agent_service_optimization_requests": {},
            "finance_import_batches": {},
            "finance_entries": {},
            "agent_action_ledger": {},
            "agent_integrations": {},
        }
        self.last_result = None
        self.last_results = []
        self.ledger_entries = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select to_regclass"):
            table_name = params[0]
            self.last_result = {"table_name": table_name if table_name in self.tables else None}
            return None
        if normalized_query.startswith("create table if not exists"):
            return None
        if normalized_query.startswith("create unique index if not exists"):
            return None
        if normalized_query.startswith("create index if not exists"):
            return None
        if normalized_query.startswith("update agent_approvals a set status = 'superseded'"):
            blueprint_id = params[0]
            for approval in self.tables["agent_approvals"].values():
                run = self.tables["agent_runs"].get(approval.get("run_id"))
                if run and run.get("blueprint_id") == blueprint_id and approval.get("status") == "pending":
                    approval["status"] = "superseded"
                    approval["decision_reason"] = "Superseded by a newer agent run"
            return None
        if normalized_query.startswith("update agent_runs set status = 'superseded'"):
            blueprint_id = params[0]
            self.last_results = []
            for run in self.tables["agent_runs"].values():
                if run.get("blueprint_id") != blueprint_id or run.get("status") != "waiting_approval":
                    continue
                has_pending = any(
                    approval.get("run_id") == run.get("id") and approval.get("status") == "pending"
                    for approval in self.tables["agent_approvals"].values()
                )
                if not has_pending:
                    run["status"] = "superseded"
                    self.last_results.append({
                        "id": run.get("id"),
                        "business_id": run.get("business_id"),
                        "created_by_user_id": run.get("created_by_user_id"),
                        "billing_reservation_id": run.get("billing_reservation_id"),
                    })
            return None
        if "from agent_sheet_operation_requests" in normalized_query:
            business_id = params[0]
            request_ids = set(params[1])
            action_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["agent_sheet_operation_requests"].values()
                if row.get("business_id") == business_id and (row.get("id") in request_ids or row.get("action_id") in action_ids)
            ]
            return None
        if "from agent_communication_requests" in normalized_query:
            business_id = params[0]
            request_ids = set(params[1])
            action_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["agent_communication_requests"].values()
                if row.get("business_id") == business_id and (row.get("id") in request_ids or row.get("action_id") in action_ids)
            ]
            return None
        if "from reviewreplydrafts" in normalized_query:
            business_id = params[0]
            draft_ids = set(params[1])
            review_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["reviewreplydrafts"].values()
                if row.get("business_id") == business_id and (row.get("id") in draft_ids or row.get("review_id") in review_ids)
            ]
            return None
        if "from agent_review_publish_requests" in normalized_query:
            business_id = params[0]
            draft_id = params[1]
            review_id = params[2]
            self.last_results = [
                row
                for row in self.tables["agent_review_publish_requests"].values()
                if row.get("business_id") == business_id and (row.get("draft_id") == draft_id or row.get("review_id") == review_id)
            ]
            return None
        if "from agent_service_optimization_requests" in normalized_query:
            business_id = params[0]
            request_ids = set(params[1])
            action_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["agent_service_optimization_requests"].values()
                if row.get("business_id") == business_id and (row.get("id") in request_ids or row.get("action_id") in action_ids)
            ]
            return None
        if "from finance_import_batches" in normalized_query:
            business_id = params[0]
            batch_ids = set(params[1])
            file_hashes = set(params[2])
            self.last_results = [
                row
                for row in self.tables["finance_import_batches"].values()
                if row.get("business_id") == business_id and (row.get("id") in batch_ids or row.get("file_hash") in file_hashes)
            ]
            return None
        if "from finance_entries" in normalized_query and "duplicate_key" in normalized_query:
            business_id = params[0]
            duplicate_key = params[1]
            self.last_result = next(
                (
                    row
                    for row in self.tables["finance_entries"].values()
                    if row.get("business_id") == business_id and row.get("duplicate_key") == duplicate_key
                ),
                None,
            )
            return None
        if normalized_query.startswith("select steps_json from agent_blueprint_versions where id"):
            version = self.tables["agent_blueprint_versions"].get(params[0])
            self.last_result = {"steps_json": version.get("steps_json", [])} if version else None
            return None
        if normalized_query.startswith("select * from agent_blueprint_versions where id"):
            self.last_result = self.tables["agent_blueprint_versions"].get(params[0])
            return None
        if normalized_query.startswith("select * from agent_blueprint_versions where blueprint_id"):
            blueprint_id = params[0]
            versions = [
                version
                for version in self.tables["agent_blueprint_versions"].values()
                if version.get("blueprint_id") == blueprint_id
            ]
            versions = sorted(versions, key=lambda item: item.get("version_number") or 0, reverse=True)
            self.last_result = versions[0] if versions else None
            return None
        if normalized_query.startswith("select * from agent_blueprints where id"):
            self.last_result = self.tables["agent_blueprints"].get(params[0])
            return None
        if "from agent_integrations" in normalized_query:
            business_id = params[0]
            integration_ids = []
            if "id = any" in normalized_query and len(params) > 1:
                integration_ids = list(params[1] or [])
            rows = [
                row
                for row in self.tables["agent_integrations"].values()
                if row.get("business_id") == business_id
                and (not integration_ids or row.get("id") in integration_ids)
            ]
            rows = sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            self.last_results = rows[:100]
            return None
        if normalized_query.startswith("insert into agent_runs"):
            self.tables["agent_runs"][params[0]] = {
                "id": params[0],
                "blueprint_id": params[1],
                "blueprint_version_id": params[2],
                "business_id": params[3],
                "status": params[4],
                "input_json": json.loads(params[5]),
                "output_json": json.loads(params[6]),
                "created_by_user_id": params[7],
            }
            return None
        if normalized_query.startswith("select * from agent_runs where id"):
            self.last_result = self.tables["agent_runs"].get(params[0])
            return None
        if normalized_query.startswith("select id, status, input_json, output_json, error_text"):
            blueprint_id = params[0]
            version_id = params[1]
            self.last_results = [
                run
                for run in self.tables["agent_runs"].values()
                if run.get("blueprint_id") == blueprint_id and run.get("blueprint_version_id") == version_id
            ]
            return None
        if normalized_query.startswith("select step_index from agent_run_steps"):
            run_id = params[0]
            self.last_results = [
                {"step_index": step["step_index"]}
                for step in self.tables["agent_run_steps"].values()
                if step["run_id"] == run_id and step["status"] in {"completed", "rejected"}
            ]
            return None
        if normalized_query.startswith("insert into agent_run_steps"):
            self.tables["agent_run_steps"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_index": params[2],
                "step_key": params[3],
                "step_type": params[4],
                "status": params[5],
                "input_json": json.loads(params[6]),
                "output_json": json.loads(params[7]),
            }
            return None
        if normalized_query.startswith("insert into agent_artifacts"):
            self.tables["agent_artifacts"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_id": params[2],
                "artifact_type": params[3],
                "title": params[4],
                "payload_json": json.loads(params[5]),
            }
            return None
        if normalized_query.startswith("insert into agent_approvals"):
            self.tables["agent_approvals"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_id": params[2],
                "status": "pending",
                "approval_type": params[3],
                "title": params[4],
                "payload_json": json.loads(params[5]),
                "requested_by_user_id": params[6],
            }
            return None
        if normalized_query.startswith("update agent_runs set status = 'waiting_approval'"):
            self.tables["agent_runs"][params[0]]["status"] = "waiting_approval"
            return None
        if normalized_query.startswith("update agent_runs set status = 'failed'"):
            self.tables["agent_runs"][params[1]]["status"] = "failed"
            self.tables["agent_runs"][params[1]]["error_text"] = params[0]
            return None
        if normalized_query.startswith("update agent_run_steps set status = 'failed'"):
            self.tables["agent_run_steps"][params[2]]["status"] = "failed"
            self.tables["agent_run_steps"][params[2]]["output_json"] = json.loads(params[0])
            self.tables["agent_run_steps"][params[2]]["error_text"] = params[1]
            return None
        if normalized_query.startswith("update agent_run_steps set status = 'blocked'"):
            self.tables["agent_run_steps"][params[2]]["status"] = "blocked"
            self.tables["agent_run_steps"][params[2]]["output_json"] = json.loads(params[0])
            self.tables["agent_run_steps"][params[2]]["error_text"] = params[1]
            return None
        if normalized_query.startswith("update agent_run_steps set output_json"):
            self.tables["agent_run_steps"][params[1]]["output_json"] = json.loads(params[0])
            return None
        if normalized_query.startswith("select step_key, output_json from agent_run_steps"):
            run_id = params[0]
            self.last_results = [
                {
                    "step_key": step["step_key"],
                    "output_json": step["output_json"],
                }
                for step in sorted(
                    self.tables["agent_run_steps"].values(),
                    key=lambda item: item["step_index"],
                )
                if step["run_id"] == run_id and step["status"] == "completed"
            ]
            return None
        if normalized_query.startswith("select * from agent_run_steps"):
            run_id = params[0]
            self.last_results = sorted(
                [step for step in self.tables["agent_run_steps"].values() if step["run_id"] == run_id],
                key=lambda item: item["step_index"],
            )
            return None
        if normalized_query.startswith("select output_json from agent_run_steps"):
            run_id = params[0]
            step_key = params[1]
            matches = [
                step
                for step in self.tables["agent_run_steps"].values()
                if step["run_id"] == run_id and step["step_key"] == step_key and step["status"] == "completed"
            ]
            matches = sorted(matches, key=lambda item: item["step_index"], reverse=True)
            self.last_result = {"output_json": matches[0]["output_json"]} if matches else None
            return None
        if normalized_query.startswith("select * from agent_artifacts"):
            run_id = params[0]
            self.last_results = [item for item in self.tables["agent_artifacts"].values() if item["run_id"] == run_id]
            return None
        if normalized_query.startswith("select * from agent_approvals where id"):
            approval_id = params[0]
            run_id = params[1]
            approval = self.tables["agent_approvals"].get(approval_id)
            self.last_result = approval if approval and approval["run_id"] == run_id else None
            return None
        if normalized_query.startswith("select * from agent_approvals"):
            run_id = params[0]
            self.last_results = [item for item in self.tables["agent_approvals"].values() if item["run_id"] == run_id]
            return None
        if normalized_query.startswith("select payload_json from agent_artifacts"):
            run_id = params[0]
            artifact_type = params[1]
            matches = [
                item
                for item in self.tables["agent_artifacts"].values()
                if item["run_id"] == run_id and item["artifact_type"] == artifact_type
            ]
            self.last_result = {"payload_json": matches[-1]["payload_json"]} if matches else None
            return None
        if normalized_query.startswith("insert into finance_import_batches"):
            self.tables["finance_import_batches"][params[0]] = {
                "id": params[0],
                "business_id": params[1],
                "source_type": "agent",
                "status": "processing",
                "file_name": params[2],
                "file_hash": params[3],
                "rows_total": params[4],
                "rows_imported": 0,
                "rows_skipped": 0,
                "rows_failed": 0,
                "mapping_json": json.loads(params[5]),
                "error_log": json.loads(params[6]),
            }
            return None
        if normalized_query.startswith("insert into finance_entries"):
            self.tables["finance_entries"][params[0]] = {
                "id": params[0],
                "business_id": params[1],
                "date": params[2],
                "type": params[3],
                "category": params[4],
                "amount": params[5],
                "source": "agent",
                "comment": params[6],
                "import_batch_id": params[7],
                "external_id": params[8],
                "duplicate_key": params[9],
            }
            return None
        if normalized_query.startswith("update finance_import_batches"):
            batch = self.tables["finance_import_batches"].get(params[5])
            if batch and batch.get("business_id") == params[6]:
                batch["status"] = params[0]
                batch["rows_imported"] = params[1]
                batch["rows_skipped"] = params[2]
                batch["rows_failed"] = params[3]
                batch["error_log"] = json.loads(params[4])
            return None
        if normalized_query.startswith("insert into agent_action_ledger"):
            metadata = json.loads(params[14])
            entry = {
                "id": params[0],
                "action_type": params[3],
                "capability": params[4],
                "risk_level": params[6],
                "output_summary": json.loads(params[8]),
                "status": params[10],
                "reason_code": params[11],
                "metadata": metadata,
            }
            self.ledger_entries.append(entry)
            self.tables["agent_action_ledger"][params[0]] = entry
            return None
        if normalized_query.startswith("select 1 from agent_approvals"):
            run_id = params[0]
            approval_type = params[1] if len(params) > 1 else None
            matches = [
                item
                for item in self.tables["agent_approvals"].values()
                if item["run_id"] == run_id
                and item["status"] == "approved"
                and (approval_type is None or item["approval_type"] == approval_type)
            ]
            self.last_result = {"?column?": 1} if matches else None
            return None
        if normalized_query.startswith("select id, name, city, category, source"):
            business_id = params[0]
            lead_ids = params[1] if len(params) > 2 and isinstance(params[1], list) else []
            rows = []
            for lead in self.tables["prospectingleads"].values():
                if lead.get("business_id") != business_id:
                    continue
                if lead_ids and lead.get("id") not in lead_ids:
                    continue
                rows.append(lead)
            self.last_results = rows
            return None
        if normalized_query.startswith("select id, name, city, email"):
            business_id = params[0]
            lead_ids = params[1] if len(params) > 2 else []
            rows = []
            for lead in self.tables["prospectingleads"].values():
                if lead.get("business_id") != business_id:
                    continue
                if lead_ids and lead.get("id") not in lead_ids:
                    continue
                rows.append(lead)
            self.last_results = rows
            return None
        if normalized_query.startswith("update prospectingleads set status = case"):
            business_id = params[3]
            lead_ids = params[4]
            for lead_id in lead_ids:
                lead = self.tables["prospectingleads"].get(lead_id)
                if lead and lead.get("business_id") == business_id and lead.get("status") not in {
                    "channel_selected",
                    "draft_ready",
                    "queued_for_send",
                    "sent",
                    "delivered",
                }:
                    lead["status"] = params[0]
                    lead["pipeline_status"] = params[1]
                    lead["last_manual_action_by"] = params[2]
            return None
        if normalized_query.startswith("select d.id"):
            business_id = params[0]
            draft_ids = params[1] if len(params) > 2 else []
            rows = []
            for draft in self.tables["outreachmessagedrafts"].values():
                lead = self.tables["prospectingleads"].get(draft.get("lead_id"))
                if not lead or lead.get("business_id") != business_id:
                    continue
                if draft_ids and draft.get("id") not in draft_ids:
                    continue
                rows.append(
                    {
                        **draft,
                        "lead_name": lead.get("name"),
                    }
                )
            self.last_results = rows
            return None
        if normalized_query.startswith("select id, name, category"):
            business_id = params[0]
            lead_ids = set(params[1])
            limit = params[2]
            rows = []
            for lead in self.tables["prospectingleads"].values():
                if lead.get("business_id") != business_id or lead.get("id") not in lead_ids:
                    continue
                has_draft = any(
                    draft.get("lead_id") == lead.get("id") and draft.get("status") in {"generated", "edited", "approved"}
                    for draft in self.tables["outreachmessagedrafts"].values()
                )
                if not has_draft:
                    rows.append(lead)
            self.last_results = rows[:limit]
            return None
        if normalized_query.startswith("insert into outreachmessagedrafts"):
            self.tables["outreachmessagedrafts"][params[0]] = {
                "id": params[0],
                "lead_id": params[1],
                "channel": params[2],
                "angle_type": params[3],
                "tone": params[4],
                "status": params[5],
                "generated_text": params[6],
                "edited_text": params[7],
                "learning_note_json": json.loads(params[8]),
                "created_by": params[9],
                "approved_text": None,
            }
            return None
        if normalized_query.startswith("update prospectingleads set status = %s, selected_channel"):
            lead = self.tables["prospectingleads"].get(params[3])
            if lead and lead.get("business_id") == params[4]:
                lead["status"] = params[0]
                lead["selected_channel"] = params[1]
                lead["pipeline_status"] = params[2]
            return None
        if normalized_query.startswith("update outreachmessagedrafts set status = %s"):
            draft_ids = params[2]
            business_id = params[3]
            for draft_id in draft_ids:
                draft = self.tables["outreachmessagedrafts"].get(draft_id)
                lead = self.tables["prospectingleads"].get((draft or {}).get("lead_id"))
                if draft and lead and lead.get("business_id") == business_id:
                    draft["status"] = params[0]
                    draft["approved_by"] = params[1]
                    draft["approved_text"] = draft.get("edited_text") or draft.get("generated_text")
                    draft["edited_text"] = draft.get("edited_text") or draft.get("generated_text")
            return None
        if normalized_query.startswith("update prospectingleads set status = %s, pipeline_status"):
            business_id = params[2]
            draft_ids = set(params[3])
            lead_ids = {
                draft.get("lead_id")
                for draft in self.tables["outreachmessagedrafts"].values()
                if draft.get("id") in draft_ids
            }
            for lead_id in lead_ids:
                lead = self.tables["prospectingleads"].get(lead_id)
                if lead and lead.get("business_id") == business_id:
                    lead["status"] = params[0]
                    lead["pipeline_status"] = params[1]
            return None
        if normalized_query.startswith("update agent_approvals set status = 'approved'"):
            approval = self.tables["agent_approvals"].get(params[2])
            if approval and approval["run_id"] == params[3]:
                approval["status"] = "approved"
                approval["decided_by_user_id"] = params[0]
                approval["decision_reason"] = params[1]
            return None
        if normalized_query.startswith("update agent_run_steps set status = 'completed'"):
            step = self.tables["agent_run_steps"].get(params[1])
            if step:
                step["status"] = "completed"
                step["output_json"] = json.loads(params[0])
            return None
        if normalized_query.startswith("update agent_runs set status = 'running'"):
            self.tables["agent_runs"][params[0]]["status"] = "running"
            return None
        if normalized_query.startswith("update agent_runs set status = 'completed'"):
            self.tables["agent_runs"][params[1]]["status"] = "completed"
            self.tables["agent_runs"][params[1]]["output_json"] = json.loads(params[0])
            self.tables["agent_runs"][params[1]]["error_text"] = None
            self.tables["agent_runs"][params[1]]["next_attempt_at"] = None
            return None
        if normalized_query.startswith("update agent_blueprints") and "set metadata_json" in normalized_query:
            blueprint = self.tables["agent_blueprints"].get(params[1])
            if blueprint:
                blueprint["metadata_json"] = json.loads(params[0])
            return None
        if normalized_query.startswith("update agent_blueprints") and "set status = 'active'" in normalized_query:
            blueprint = self.tables["agent_blueprints"].get(params[0])
            if blueprint and blueprint.get("status") != "archived":
                blueprint["status"] = "active"
            return None
        if normalized_query.startswith("select count(*) as count from agent_artifacts"):
            run_id = params[0]
            self.last_result = {"count": len([item for item in self.tables["agent_artifacts"].values() if item["run_id"] == run_id])}
            return None
        if normalized_query.startswith("select count(*) as count from agent_approvals"):
            run_id = params[0]
            self.last_result = {"count": len([item for item in self.tables["agent_approvals"].values() if item["run_id"] == run_id])}
            return None
        raise AssertionError(f"Unhandled SQL in fake cursor: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results


class FakeDatahubCursor:
    def __init__(self):
        self.last_results = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        if "from businesses" in normalized_query:
            self.last_results = [{"id": "biz1", "name": "Local Test", "business_type": "beauty", "city": "Moscow", "address": "Street"}]
            return None
        if "from userservices" in normalized_query:
            self.last_results = [
                {"id": "svc1", "name": "Haircut", "price": 1000, "description": "Cut"},
                {"id": "svc2", "name": "Color", "price": 3000, "description": "Color"},
            ]
            return None
        if "from externalbusinessreviews" in normalized_query:
            self.last_results = [{"id": "rev1", "author_name": "Anna", "rating": 5, "text": "Great"}]
            return None
        if "from prospectingleads" in normalized_query:
            self.last_results = []
            return None
        if "from outreachmessagedrafts" in normalized_query:
            self.last_results = [{"id": "draft1", "channel": "email", "status": "generated", "generated_text": "Hello"}]
            return None
        raise AssertionError(f"Unhandled Datahub SQL: {query}")

    def fetchall(self):
        return self.last_results


class FakeCapabilityDatabase:
    def __init__(self):
        self.cursor_instance = FakeCapabilityCursor()
        self.conn = self
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeCapabilityCursor:
    def __init__(self):
        self.last_result = None
        self.last_results = []
        self.description = []
        self.inserted = {}

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if (
            normalized_query.startswith("create table")
            or normalized_query.startswith("create index")
            or normalized_query.startswith("create unique index")
            or normalized_query.startswith("alter table")
        ):
            return None
        if normalized_query.startswith("select to_regclass"):
            table_name = str(params[0])
            self.description = [("to_regclass",)]
            self.last_result = (table_name if table_name in {"bookings", "externalbusinessreviews", "userservices"} else None,)
            return None
        if "from information_schema.columns" in normalized_query:
            table_name = str(params[0])
            column_map = {
                "userservices": [
                    "id",
                    "business_id",
                    "name",
                    "description",
                    "category",
                    "price",
                    "is_active",
                    "updated_at",
                    "created_at",
                    "optimized_name",
                    "optimized_description",
                ],
            }
            self.description = [("column_name",)]
            self.last_results = [(column,) for column in column_map.get(table_name, [])]
            return None
        if "from bookings" in normalized_query:
            columns = [
                "id",
                "business_id",
                "client_phone",
                "client_name",
                "service_id",
                "service_name",
                "booking_date",
                "booking_time",
                "status",
                "notes",
                "created_at",
                "updated_at",
            ]
            self.description = [(column,) for column in columns]
            self.last_results = [
                (
                    "booking-1",
                    "biz1",
                    "+79990000000",
                    "Анна",
                    "svc1",
                    "Стрижка",
                    "2026-06-10",
                    "12:00",
                    "confirmed",
                    "",
                    None,
                    None,
                )
            ]
            return None
        if normalized_query.startswith("insert into agent_communication_requests"):
            self.inserted["agent_communication_requests"] = {
                "id": params[0],
                "action_id": params[1],
                "business_id": params[2],
                "user_id": params[3],
                "capability": params[4],
                "message_type": params[5],
                "channel": params[6],
                "recipient_count": params[7],
                "recipients_json": json.loads(params[8]),
                "message_template": params[9],
                "limits_json": json.loads(params[10]),
                "consent_json": json.loads(params[11]),
            }
            self.description = [("id",)]
            self.last_result = (params[0],)
            return None
        if "from externalbusinessreviews" in normalized_query:
            columns = [
                "id",
                "business_id",
                "source",
                "external_review_id",
                "rating",
                "author_name",
                "text",
                "response_text",
                "response_at",
            ]
            self.description = [(column,) for column in columns]
            self.last_result = ("rev1", "biz1", "yandex", "ext-rev1", 5, "Anna", "Great", None, None)
            return None
        if normalized_query.startswith("insert into reviewreplydrafts"):
            self.inserted["reviewreplydrafts"] = {
                "id": params[0],
                "business_id": params[1],
                "review_id": params[2],
                "user_id": params[3],
                "source": params[4],
                "rating": params[5],
                "author_name": params[6],
                "review_text": params[7],
                "generated_text": params[8],
                "status": "publish_requested",
            }
            self.description = [("id",)]
            self.last_result = (params[0],)
            return None
        if "from userservices" in normalized_query:
            columns = [
                "id",
                "business_id",
                "name",
                "description",
                "category",
                "price",
                "optimized_name",
                "optimized_description",
            ]
            self.description = [(column,) for column in columns]
            self.last_results = [
                ("svc1", "biz1", "Стрижка", "Классическая стрижка", "Парикмахерские услуги", 1500, "", "")
            ]
            return None
        if normalized_query.startswith("insert into agent_service_optimization_requests"):
            self.inserted["agent_service_optimization_requests"] = {
                "id": params[0],
                "action_id": params[1],
                "business_id": params[2],
                "user_id": params[3],
                "status": "draft_ready",
                "service_count": params[4],
                "suggestions_json": json.loads(params[5]),
                "diff_json": json.loads(params[6]),
                "apply_state": "not_applied",
            }
            self.description = [("id",)]
            self.last_result = (params[0],)
            return None
        if normalized_query.startswith("insert into agent_sheet_operation_requests"):
            self.inserted["agent_sheet_operation_requests"] = {
                "id": params[0],
                "action_id": params[1],
                "business_id": params[2],
                "user_id": params[3],
                "integration_id": params[4],
                "spreadsheet_id": params[5],
                "sheet_name": params[6],
                "operation": "append_row",
                "status": "request_created",
                "approval_state": "pending_human",
                "apply_state": "not_applied",
                "row_values_json": json.loads(params[7]),
                "mapping_json": json.loads(params[8]),
                "source_event_json": json.loads(params[9]),
                "limits_json": json.loads(params[10]),
                "provider_write_performed": False,
            }
            self.description = [("id",)]
            self.last_result = (params[0],)
            return None
        raise AssertionError(f"Unhandled capability SQL: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results


class FakeApprovedDomainExecutorCursor:
    def __init__(self):
        self.tables = {
            "agent_sheet_operation_requests": {},
            "agent_communication_requests": {},
            "reviewreplydrafts": {},
            "agent_review_publish_requests": {},
            "agent_service_optimization_requests": {},
            "agent_communication_delivery_journal": {},
            "agent_action_ledger": {},
            "userservices": {},
            "finance_import_batches": {},
            "finance_entries": {},
        }
        self.last_result = None
        self.last_results = []
        self.ledger_entries = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select to_regclass"):
            table_name = str(params[0])
            self.last_result = (table_name if table_name in self.tables else None,)
            return None
        if "from information_schema.columns" in normalized_query:
            table_name = str(params[0])
            columns = {
                "userservices": ["id", "business_id", "optimized_name", "optimized_description", "updated_at"],
            }.get(table_name, [])
            self.last_results = [(column,) for column in columns]
            return None
        if normalized_query.startswith("select id, action_id, status, approval_state"):
            business_id = params[0]
            request_ids = set(params[1])
            action_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["agent_sheet_operation_requests"].values()
                if row.get("business_id") == business_id and (row.get("id") in request_ids or row.get("action_id") in action_ids)
            ]
            return None
        if "from agent_communication_requests" in normalized_query:
            business_id = params[0]
            request_ids = set(params[1])
            action_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["agent_communication_requests"].values()
                if row.get("business_id") == business_id and (row.get("id") in request_ids or row.get("action_id") in action_ids)
            ]
            return None
        if "from reviewreplydrafts" in normalized_query:
            business_id = params[0]
            draft_ids = set(params[1])
            review_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["reviewreplydrafts"].values()
                if row.get("business_id") == business_id and (row.get("id") in draft_ids or row.get("review_id") in review_ids)
            ]
            return None
        if "from agent_review_publish_requests" in normalized_query:
            business_id = params[0]
            draft_id = params[1]
            review_id = params[2]
            self.last_results = [
                row
                for row in self.tables["agent_review_publish_requests"].values()
                if row.get("business_id") == business_id and (row.get("draft_id") == draft_id or row.get("review_id") == review_id)
            ]
            return None
        if "from agent_service_optimization_requests" in normalized_query:
            business_id = params[0]
            request_ids = set(params[1])
            action_ids = set(params[2])
            self.last_results = [
                row
                for row in self.tables["agent_service_optimization_requests"].values()
                if row.get("business_id") == business_id and (row.get("id") in request_ids or row.get("action_id") in action_ids)
            ]
            return None
        if "from finance_entries" in normalized_query and "duplicate_key" in normalized_query:
            business_id = params[0]
            duplicate_key = params[1]
            self.last_result = next(
                (
                    row
                    for row in self.tables["finance_entries"].values()
                    if row.get("business_id") == business_id and row.get("duplicate_key") == duplicate_key
                ),
                None,
            )
            return None
        if normalized_query.startswith("update agent_sheet_operation_requests"):
            request = self.tables["agent_sheet_operation_requests"].get(params[0])
            if request and request.get("business_id") == params[1] and request.get("provider_write_performed") is False:
                request["status"] = "approved_for_execution"
                request["approval_state"] = "approved"
                request["apply_state"] = "provider_request_queued"
            return None
        if normalized_query.startswith("update userservices"):
            service = self.tables["userservices"].get(params[2])
            if service and service.get("business_id") == params[3]:
                if params[0]:
                    service["optimized_name"] = params[0]
                if params[1]:
                    service["optimized_description"] = params[1]
            return None
        if normalized_query.startswith("insert into agent_communication_delivery_journal"):
            row = {
                "id": params[0],
                "request_id": params[1],
                "action_id": params[2],
                "business_id": params[3],
                "run_id": params[4],
                "user_id": params[5],
                "recipient_key": params[6],
                "channel": params[7],
                "message_template": params[8],
                "status": params[9],
                "delivery_state": params[10],
                "consent_json": json.loads(params[11]),
                "limits_json": json.loads(params[12]),
                "router_handoff_json": json.loads(params[13]),
                "provider_write_performed": False,
            }
            self.tables["agent_communication_delivery_journal"][params[0]] = row
            return None
        if normalized_query.startswith("update agent_communication_requests"):
            request = self.tables["agent_communication_requests"].get(params[1])
            if request and request.get("business_id") == params[2] and request.get("delivery_state") != "dispatched":
                request["status"] = "approved_for_dispatch"
                request["delivery_state"] = params[0]
            return None
        if normalized_query.startswith("update reviewreplydrafts"):
            draft = self.tables["reviewreplydrafts"].get(params[0])
            if draft and draft.get("business_id") == params[1]:
                draft["status"] = "approved_for_publish"
            return None
        if normalized_query.startswith("insert into agent_review_publish_requests"):
            row = {
                "id": params[0],
                "draft_id": params[1],
                "review_id": params[2],
                "business_id": params[3],
                "run_id": params[4],
                "user_id": params[5],
                "source": params[6],
                "reply_text": params[7],
                "status": "provider_publish_requested",
                "publish_state": "provider_request_queued",
                "provider_request_json": json.loads(params[8]),
                "audit_json": json.loads(params[9]),
                "provider_write_performed": False,
            }
            self.tables["agent_review_publish_requests"][params[0]] = row
            return None
        if normalized_query.startswith("update agent_service_optimization_requests"):
            request = self.tables["agent_service_optimization_requests"].get(params[2])
            if request and request.get("business_id") == params[3] and request.get("apply_state") != "applied":
                request["status"] = params[0]
                request["apply_state"] = params[1]
            return None
        if normalized_query.startswith("insert into finance_import_batches"):
            self.tables["finance_import_batches"][params[0]] = {
                "id": params[0],
                "business_id": params[1],
                "source_type": "agent",
                "status": "processing",
                "file_name": params[2],
                "file_hash": params[3],
                "rows_total": params[4],
                "rows_imported": 0,
                "rows_skipped": 0,
                "rows_failed": 0,
                "mapping_json": json.loads(params[5]),
                "error_log": json.loads(params[6]),
            }
            return None
        if normalized_query.startswith("insert into finance_entries"):
            self.tables["finance_entries"][params[0]] = {
                "id": params[0],
                "business_id": params[1],
                "date": params[2],
                "type": params[3],
                "category": params[4],
                "amount": params[5],
                "source": "agent",
                "comment": params[6],
                "import_batch_id": params[7],
                "external_id": params[8],
                "duplicate_key": params[9],
            }
            return None
        if normalized_query.startswith("update finance_import_batches"):
            batch = self.tables["finance_import_batches"].get(params[5])
            if batch and batch.get("business_id") == params[6]:
                batch["status"] = params[0]
                batch["rows_imported"] = params[1]
                batch["rows_skipped"] = params[2]
                batch["rows_failed"] = params[3]
                batch["error_log"] = json.loads(params[4])
            return None
        if (
            normalized_query.startswith("create table")
            or normalized_query.startswith("create index")
            or normalized_query.startswith("create unique index")
        ):
            return None
        if normalized_query.startswith("insert into agent_action_ledger"):
            metadata = json.loads(params[14])
            entry = {
                "id": params[0],
                "action_type": params[3],
                "capability": params[4],
                "risk_level": params[6],
                "output_summary": json.loads(params[8]),
                "status": params[10],
                "reason_code": params[11],
                "metadata": metadata,
            }
            self.ledger_entries.append(entry)
            self.tables["agent_action_ledger"][params[0]] = entry
            return None
        raise AssertionError(f"Unhandled approved executor SQL: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results


class FakeSheetProviderExecutorCursor:
    def __init__(self):
        self.tables = {
            "agent_sheet_operation_requests": {},
            "agent_action_ledger": {},
        }
        self.last_result = None
        self.last_results = []
        self.ledger_entries = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select id, action_id, business_id"):
            business_id = params[0]
            limit = params[1]
            rows = [
                row
                for row in self.tables["agent_sheet_operation_requests"].values()
                if row.get("business_id") == business_id
                and row.get("status") == "approved_for_execution"
                and row.get("approval_state") == "approved"
                and row.get("apply_state") == "provider_request_queued"
                and row.get("provider_write_performed") is False
            ]
            self.last_results = rows[:limit]
            return None
        if "from agent_integrations" in normalized_query:
            self.last_result = None
            return None
        if normalized_query.startswith("update agent_sheet_operation_requests"):
            request = self.tables["agent_sheet_operation_requests"].get(params[4])
            if request and request.get("business_id") == params[5] and request.get("apply_state") == "provider_request_queued":
                request["status"] = params[0]
                request["apply_state"] = params[1]
                request["provider_write_performed"] = params[2]
                request["error_text"] = params[3] or None
            return None
        if (
            normalized_query.startswith("create table")
            or normalized_query.startswith("create index")
            or normalized_query.startswith("create unique index")
        ):
            return None
        if normalized_query.startswith("insert into agent_action_ledger"):
            entry = {
                "id": params[0],
                "action_type": params[3],
                "capability": params[4],
                "risk_level": params[6],
                "input_summary": json.loads(params[7]),
                "output_summary": json.loads(params[8]),
                "status": params[10],
                "reason_code": params[11],
                "metadata": json.loads(params[14]),
            }
            self.ledger_entries.append(entry)
            self.tables["agent_action_ledger"][params[0]] = entry
            return None
        raise AssertionError(f"Unhandled sheet provider SQL: {query}")

    def fetchall(self):
        return self.last_results

    def fetchone(self):
        return self.last_result


class FakeGoogleSheetsIntegrationCursor:
    def __init__(self):
        self.agent_integrations = {}
        self.external_accounts = {}
        self.last_result = None
        self.last_results = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if "from agent_integrations" in normalized_query:
            business_id = params[1] if "where id = %s" in normalized_query else params[0]
            integration_id = params[0] if "where id = %s" in normalized_query else ""
            rows = [
                row
                for row in self.agent_integrations.values()
                if row.get("business_id") == business_id
                and row.get("provider") == "google_sheets"
                and row.get("status") == "active"
                and (not integration_id or row.get("id") == integration_id)
            ]
            self.last_result = rows[0] if rows else None
            return None
        if "from information_schema.columns" in normalized_query:
            self.last_results = [{"column_name": "auth_data_encrypted"}]
            return None
        if "from externalbusinessaccounts" in normalized_query:
            if "select id, business_id, source, display_name" in normalized_query:
                if "where id = %s" in normalized_query:
                    account = self.external_accounts.get(params[0])
                    self.last_result = (
                        account
                        if account and account.get("business_id") == params[1] and account.get("is_active") is True
                        else None
                    )
                    return None
                business_id = params[0]
                rows = [
                    account
                    for account in self.external_accounts.values()
                    if account.get("business_id") == business_id
                    and account.get("is_active") is True
                    and account.get("source") in {"google_sheets", "google_business"}
                ]
                self.last_result = rows[0] if rows else None
                self.last_results = rows
                return None
            auth_ref = params[0]
            business_id = params[1]
            account = self.external_accounts.get(auth_ref)
            self.last_result = (
                account
                if account and account.get("business_id") == business_id and account.get("is_active") is True
                else None
            )
            return None
        raise AssertionError(f"Unhandled Google Sheets integration SQL: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results


class FakeTelegramTriggerCursor:
    def __init__(self):
        self.last_result = None
        self.last_results = []
        self.trigger_events = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("create table") or normalized_query.startswith("create index"):
            return None
        if normalized_query.startswith("insert into agent_trigger_events"):
            is_scheduler_event = len(params) == 4
            self.trigger_events.append(
                {
                    "id": params[0],
                    "business_id": params[1],
                    "source": "scheduler" if is_scheduler_event else "telegram",
                    "event_type": params[2] if is_scheduler_event else "telegram.message.received",
                    "status": "received",
                    "payload_json": json.loads(params[3] if is_scheduler_event else params[2]),
                    "reason_code": None,
                }
            )
            return None
        if "from agent_blueprints" in normalized_query:
            self.last_results = []
            return None
        if normalized_query.startswith("update agent_trigger_events set status = 'ignored'"):
            for item in self.trigger_events:
                if item["id"] == params[1]:
                    item["status"] = "ignored"
                    item["reason_code"] = params[0]
            return None
        raise AssertionError(f"Unhandled trigger SQL: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results


class FakeActiveTelegramTriggerCursor(FakeCursor):
    def __init__(self):
        super().__init__()
        self.trigger_events = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("create table") or normalized_query.startswith("create index"):
            return None
        if normalized_query.startswith("insert into agent_trigger_events"):
            is_single_blueprint_scheduler_event = len(params) == 5
            is_scheduler_event = len(params) == 4 or is_single_blueprint_scheduler_event
            self.trigger_events.append(
                {
                    "id": params[0],
                    "business_id": params[1],
                    "source": "scheduler" if is_scheduler_event else "telegram",
                    "event_type": params[3] if is_single_blueprint_scheduler_event else params[2] if is_scheduler_event else "telegram.message.received",
                    "status": "received",
                    "payload_json": json.loads(params[4] if is_single_blueprint_scheduler_event else params[3] if is_scheduler_event else params[2]),
                    "reason_code": None,
                    "blueprint_id": params[2] if is_single_blueprint_scheduler_event else None,
                    "run_id": None,
                }
            )
            return None
        if normalized_query.startswith("select id from agent_trigger_events"):
            blueprint_id = params[0]
            event_type = params[1]
            self.last_result = next(
                (
                    item
                    for item in self.trigger_events
                    if item.get("blueprint_id") == blueprint_id
                    and item.get("source") == "scheduler"
                    and item.get("event_type") == event_type
                    and item.get("payload_json", {}).get("schedule_date") == params[2]
                    and item.get("payload_json", {}).get("schedule_time") == params[3]
                    and (
                        item.get("status") == "run_started"
                        or (
                            item.get("status") == "failed"
                            and item.get("reason_code") != "AGENT_RUN_ALREADY_IN_PROGRESS"
                        )
                    )
                ),
                None,
            )
            return None
        if normalized_query.startswith("select * from agent_blueprints where status = 'active'"):
            limit = int(params[0])
            self.last_results = [
                row
                for row in self.tables["agent_blueprints"].values()
                if row.get("status") == "active"
                and row.get("metadata_json", {}).get("execution_mode") == "scheduled"
            ][:limit]
            return None
        if normalized_query.startswith("select id, business_id, metadata_json from agent_blueprints"):
            limit = int(params[0])
            self.last_results = [
                row
                for row in self.tables["agent_blueprints"].values()
                if row.get("status") == "active"
                and row.get("metadata_json", {}).get("execution_mode") == "scheduled"
            ][:limit]
            return None
        if "from agent_blueprints" in normalized_query and "status = 'active'" in normalized_query:
            business_id = params[0]
            self.last_results = [
                row
                for row in self.tables["agent_blueprints"].values()
                if row.get("business_id") == business_id
                and row.get("status") == "active"
            ]
            return None
        if normalized_query.startswith("select * from agent_blueprint_versions where blueprint_id"):
            blueprint_id = params[0]
            rows = [
                row
                for row in self.tables["agent_blueprint_versions"].values()
                if row.get("blueprint_id") == blueprint_id
            ]
            rows.sort(key=lambda item: int(item.get("version_number") or 0), reverse=True)
            self.last_result = rows[0] if rows else None
            return None
        if normalized_query.startswith("update agent_trigger_events set blueprint_id"):
            for item in self.trigger_events:
                if item["id"] == params[2]:
                    item["blueprint_id"] = params[0]
                    item["run_id"] = params[1]
                    item["status"] = "run_started"
            return None
        if normalized_query.startswith("update agent_trigger_events set status = 'ignored'"):
            for item in self.trigger_events:
                if item["id"] == params[1]:
                    item["status"] = "ignored"
                    item["reason_code"] = params[0]
            return None
        if normalized_query.startswith("update agent_trigger_events set run_id"):
            for item in self.trigger_events:
                if item["id"] == params[3]:
                    item["run_id"] = params[0]
                    item["status"] = params[1]
                    item["reason_code"] = params[2]
            return None
        return super().execute(query, params)


class CountingOrchestrator:
    def __init__(self):
        self.calls = 0
        self.last_envelope = None

    def execute(self, envelope, user_data, *, allow_execute_when_approved=False):
        self.calls += 1
        self.last_envelope = envelope
        return {
            "success": True,
            "status": "completed",
            "result": {
                "status": "queued_for_dispatch",
                "dispatch_state": "queued_not_dispatched",
                "external_dispatch_performed": False,
            },
        }


class FakeUpload:
    def __init__(self, filename, mimetype, data):
        self.filename = filename
        self.mimetype = mimetype
        self._data = data

    def read(self):
        return self._data


class FakeOutreachConnection:
    def __init__(self, draft_rows):
        self.cursor_instance = FakeOutreachCursor(draft_rows)
        self.inserted = self.cursor_instance.inserted
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeOutreachCursor:
    def __init__(self, draft_rows):
        self.draft_rows = draft_rows
        self.last_result = None
        self.last_results = []
        self.inserted = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select count(*) as cnt"):
            self.last_result = {"cnt": 0}
            return None
        if normalized_query.startswith("select d.id"):
            self.last_results = self.draft_rows
            return None
        if normalized_query.startswith("insert into outreachsendbatches"):
            self.inserted.append(
                {
                    "kind": "batch",
                    "id": params[0],
                    "daily_limit": params[1],
                    "status": params[2],
                    "created_by": params[3],
                    "approved_by": params[4],
                }
            )
            return None
        if normalized_query.startswith("insert into outreachsendqueue"):
            self.inserted.append(
                {
                    "kind": "queue",
                    "id": params[0],
                    "batch_id": params[1],
                    "lead_id": params[2],
                    "draft_id": params[3],
                    "channel": params[4],
                    "delivery_status": params[5],
                }
            )
            return None
        if normalized_query.startswith("update prospectingleads"):
            self.inserted.append(
                {
                    "kind": "lead_update",
                    "status": params[0],
                    "pipeline_status": params[1],
                    "lead_id": params[2],
                    "business_id": params[3],
                }
            )
            return None
        raise AssertionError(f"Unhandled SQL in fake outreach cursor: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results
