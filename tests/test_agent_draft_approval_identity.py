import pytest

from tests.agent_blueprint_fakes import FakeCursor


class DraftProjectionCursor(FakeCursor):
    """Keep the draft loader honest: rows contain only columns selected by SQL."""

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        if normalized_query.startswith("select d.id, d.lead_id") and "from outreachmessagedrafts d" in normalized_query:
            params = params or ()
            business_id = params[0]
            draft_ids = params[1] if "d.id = any(%s)" in normalized_query else []
            rows = []
            for draft in self.tables["outreachmessagedrafts"].values():
                lead = self.tables["prospectingleads"].get(draft.get("lead_id"))
                if not lead or lead.get("business_id") != business_id:
                    continue
                if draft_ids and draft.get("id") not in draft_ids:
                    continue
                row = {
                    "id": draft.get("id"),
                    "lead_id": draft.get("lead_id"),
                    "channel": draft.get("channel"),
                    "status": draft.get("status"),
                    "generated_text": draft.get("generated_text"),
                    "approved_text": draft.get("approved_text"),
                    "lead_name": lead.get("name"),
                }
                if "d.edited_text" in normalized_query:
                    row["edited_text"] = draft.get("edited_text")
                for key in ("email", "telegram_url", "whatsapp_url"):
                    if f"l.{key}" in normalized_query:
                        row[key] = lead.get(key)
                rows.append(row)
            self.last_results = rows
            return None
        return super().execute(query, params)


def _approval_fixture(*, current_text="Snapshot A"):
    from services.agent_blueprint_runner import AgentBlueprintRunner

    cursor = DraftProjectionCursor()
    run = {
        "id": "run-1",
        "blueprint_id": "blueprint-1",
        "blueprint_version_id": "version-1",
        "business_id": "business-1",
        "status": "waiting_approval",
        "input_json": {"draft_ids": ["draft-1"]},
        "output_json": {},
        "created_by_user_id": "owner-1",
    }
    cursor.tables["agent_runs"][run["id"]] = run
    cursor.tables["prospectingleads"]["lead-1"] = {
        "id": "lead-1",
        "business_id": "business-1",
        "name": "Contact A",
        "email": "owner@example.invalid",
        "status": "channel_selected",
    }
    cursor.tables["outreachmessagedrafts"]["draft-1"] = {
        "id": "draft-1",
        "lead_id": "lead-1",
        "channel": "email",
        "status": "generated",
        "generated_text": "Generated A",
        "edited_text": current_text,
        "approved_text": None,
    }
    runner = AgentBlueprintRunner(cursor)
    advance_calls = []

    def record_advance(*args):
        advance_calls.append(args)
        return {"success": True}

    runner._advance_run = record_advance
    runner.load_run = lambda run_id, user_data=None: {"id": run_id}
    return cursor, run, runner, advance_calls


def _snapshot_drafts_approval(cursor, run, runner, approval_id="approval-1"):
    artifact_payload = runner._build_message_drafts_payload(run, {"status": "draft"})
    cursor.tables["agent_artifacts"]["artifact-1"] = {
        "id": "artifact-1",
        "run_id": run["id"],
        "step_id": "draft-step",
        "artifact_type": "message_drafts",
        "title": "Draft snapshot",
        "payload_json": artifact_payload,
    }
    approval_payload = runner._build_approval_payload(run, {"approval_type": "drafts"})
    cursor.tables["agent_approvals"][approval_id] = {
        "id": approval_id,
        "run_id": run["id"],
        "step_id": "approval-step",
        "status": "pending",
        "approval_type": "drafts",
        "title": "Approve drafted outreach",
        "payload_json": approval_payload,
        "requested_by_user_id": "owner-1",
    }
    cursor.tables["agent_run_steps"]["approval-step"] = {
        "id": "approval-step",
        "run_id": run["id"],
        "step_index": 4,
        "step_key": "approve_drafts",
        "step_type": "approval",
        "status": "waiting_approval",
        "input_json": {},
        "output_json": {},
    }
    return approval_payload


def test_drafts_approval_rejects_text_edited_after_the_review_snapshot():
    cursor, run, runner, advance_calls = _approval_fixture(current_text="")
    approval_payload = _snapshot_drafts_approval(cursor, run, runner)

    assert approval_payload["items"][0]["generated_text"] == "Generated A"
    cursor.tables["outreachmessagedrafts"]["draft-1"]["edited_text"] = "Edited B after review"

    result = runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})

    assert result == {"success": False, "error": "approval_payload_stale"}
    assert cursor.tables["agent_approvals"]["approval-1"]["status"] == "pending"
    assert cursor.tables["agent_run_steps"]["approval-step"]["status"] == "waiting_approval"
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["status"] == "generated"
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["approved_text"] is None
    assert advance_calls == []


def test_drafts_approval_uses_the_same_edited_text_that_was_reviewed():
    cursor, run, runner, advance_calls = _approval_fixture(current_text="Edited before review")
    approval_payload = _snapshot_drafts_approval(cursor, run, runner)

    assert approval_payload["items"][0]["edited_text"] == "Edited before review"
    result = runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})

    assert result["success"] is True
    assert cursor.tables["agent_approvals"]["approval-1"]["status"] == "approved"
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["approved_text"] == "Edited before review"
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["status"] == "approved"
    assert advance_calls


@pytest.mark.parametrize(("table", "row_id", "key", "value"), [
    ("outreachmessagedrafts", "draft-1", "channel", "telegram"),
    ("outreachmessagedrafts", "draft-1", "lead_id", "lead-2"),
    ("outreachmessagedrafts", "draft-1", "status", "rejected"),
    ("prospectingleads", "lead-1", "email", "different@example.invalid"),
    ("prospectingleads", "lead-1", "business_id", "business-2"),
])
def test_snapshot_rejects_changed_recipient_scope_or_status(table, row_id, key, value):
    cursor, run, runner, advance_calls = _approval_fixture()
    _snapshot_drafts_approval(cursor, run, runner)
    cursor.tables["prospectingleads"]["lead-2"] = {**cursor.tables["prospectingleads"]["lead-1"], "id": "lead-2"}
    cursor.tables[table][row_id][key] = value

    result = runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})

    assert result == {"success": False, "error": "approval_payload_stale"}
    assert cursor.tables["agent_approvals"]["approval-1"]["status"] == "pending"
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["approved_text"] is None
    assert advance_calls == []


@pytest.mark.parametrize("corruption", ["duplicate", "empty", "wrong_count", "wrong_tenant", "missing_version", "missing_text", "missing_recipient", "missing_row"])
def test_malformed_or_missing_snapshot_is_denied_before_decision(corruption):
    cursor, run, runner, advance_calls = _approval_fixture()
    payload = _snapshot_drafts_approval(cursor, run, runner)
    if corruption == "duplicate":
        payload["items"].append(dict(payload["items"][0]))
        payload["count"] = 2
    elif corruption == "empty":
        payload["items"] = []
        payload["count"] = 0
    elif corruption == "wrong_count":
        payload["count"] = 2
    elif corruption == "wrong_tenant":
        payload["business_id"] = "other-business"
    elif corruption == "missing_version":
        payload.pop("snapshot_version")
    elif corruption == "missing_text":
        payload["items"][0].pop("review_text")
    elif corruption == "missing_recipient":
        payload["items"][0].pop("review_recipient")
    else:
        cursor.tables["outreachmessagedrafts"].clear()

    assert runner.approve(run["id"], "approval-1", {"user_id": "admin-1"}) == {"success": False, "error": "approval_payload_stale"}
    assert cursor.tables["agent_approvals"]["approval-1"]["status"] == "pending"
    assert cursor.tables["agent_run_steps"]["approval-step"]["status"] == "waiting_approval"
    assert advance_calls == []


def test_draft_snapshot_loader_failure_does_not_record_approval(monkeypatch):
    cursor, run, runner, advance_calls = _approval_fixture()
    _snapshot_drafts_approval(cursor, run, runner)
    original_execute = cursor.execute

    def execute_with_lock_failure(query, params=None):
        if "FOR UPDATE OF d, l" in query:
            raise RuntimeError("synthetic lock failure")
        return original_execute(query, params)

    monkeypatch.setattr(cursor, "execute", execute_with_lock_failure)
    with pytest.raises(RuntimeError, match="synthetic lock failure"):
        runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})
    assert cursor.tables["agent_approvals"]["approval-1"]["status"] == "pending"
    assert advance_calls == []


def test_drafts_approval_of_an_unchanged_review_snapshot_succeeds():
    cursor, run, runner, advance_calls = _approval_fixture()
    _snapshot_drafts_approval(cursor, run, runner)

    result = runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})

    assert result["success"] is True
    assert cursor.tables["agent_approvals"]["approval-1"]["status"] == "approved"
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["approved_text"] == "Snapshot A"
    assert advance_calls


def test_drafts_approval_without_an_immutable_review_snapshot_is_denied():
    cursor, run, runner, advance_calls = _approval_fixture()
    cursor.tables["agent_approvals"]["approval-1"] = {
        "id": "approval-1",
        "run_id": run["id"],
        "step_id": "approval-step",
        "status": "pending",
        "approval_type": "drafts",
        "title": "Legacy approval without a snapshot",
        "payload_json": {},
        "requested_by_user_id": "owner-1",
    }
    cursor.tables["agent_run_steps"]["approval-step"] = {
        "id": "approval-step",
        "run_id": run["id"],
        "step_index": 4,
        "step_key": "approve_drafts",
        "step_type": "approval",
        "status": "waiting_approval",
        "input_json": {},
        "output_json": {},
    }

    result = runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})

    assert result["success"] is False
    assert cursor.tables["agent_approvals"]["approval-1"]["status"] == "pending"
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["status"] == "generated"
    assert advance_calls == []


def test_drafts_approval_is_bound_to_its_original_artifact_not_a_newer_one():
    cursor, run, runner, advance_calls = _approval_fixture()
    _snapshot_drafts_approval(cursor, run, runner)
    cursor.tables["agent_artifacts"]["artifact-2"] = {
        "id": "artifact-2",
        "run_id": run["id"],
        "step_id": "draft-step-later",
        "artifact_type": "message_drafts",
        "title": "Later draft artifact",
        "payload_json": {
            "status": "hydrated",
            "count": 1,
            "items": [{"id": "draft-2", "edited_text": "Unreviewed B"}],
        },
    }
    cursor.tables["outreachmessagedrafts"]["draft-2"] = {
        "id": "draft-2",
        "lead_id": "lead-1",
        "channel": "email",
        "status": "generated",
        "generated_text": "Generated B",
        "edited_text": "Unreviewed B",
        "approved_text": None,
    }

    result = runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})

    assert result["success"] is True
    assert cursor.tables["outreachmessagedrafts"]["draft-1"]["status"] == "approved"
    assert cursor.tables["outreachmessagedrafts"]["draft-2"]["status"] == "generated"
    assert advance_calls


@pytest.mark.parametrize("mutation", ["none", "text", "recipient", "legacy", "approved_text"])
def test_capability_admission_uses_reviewed_ids_and_rechecks_the_snapshot(mutation):
    cursor, run, runner, _ = _approval_fixture()
    _snapshot_drafts_approval(cursor, run, runner)
    assert runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})["success"]
    cursor.tables["agent_artifacts"]["artifact-later"] = {
        "id": "artifact-later", "run_id": run["id"], "artifact_type": "message_drafts",
        "payload_json": {"items": [{"id": "unreviewed-draft"}]},
    }
    if mutation == "text":
        cursor.tables["outreachmessagedrafts"]["draft-1"]["edited_text"] = "Later unreviewed text"
    elif mutation == "recipient":
        cursor.tables["prospectingleads"]["lead-1"]["email"] = "changed@example.invalid"
    elif mutation == "legacy":
        cursor.tables["agent_approvals"]["approval-1"]["payload_json"] = {}
    elif mutation == "approved_text":
        cursor.tables["outreachmessagedrafts"]["draft-1"]["approved_text"] = "Different approved text"

    calls = []

    class BoundaryReached(Exception):
        pass

    class RecordingOrchestrator:
        def execute(self, envelope, user_data, **kwargs):
            calls.append((envelope, kwargs))
            raise BoundaryReached()

    runner.orchestrator = RecordingOrchestrator()
    step = {
        "key": "send_limited_batch", "type": "capability", "capability": "outreach.send_batch",
        "requires_approval": True, "required_approval_type": "drafts",
        "payload": {"draft_ids": ["unreviewed-draft"], "daily_limit": 10},
    }
    version = {"capability_allowlist_json": ["outreach.send_batch"]}
    if mutation == "none":
        with pytest.raises(BoundaryReached):
            runner._execute_capability_step(run, version, step, 5, {"user_id": "admin-1"})
        assert calls[0][0]["payload"]["draft_ids"] == ["draft-1"]
        assert calls[0][1]["allow_execute_when_approved"] is True
    else:
        assert runner._execute_capability_step(run, version, step, 5, {"user_id": "admin-1"}) is False
        assert calls == []
        assert any(item.get("output_json", {}).get("error") == "approval_payload_stale" for item in cursor.tables["agent_run_steps"].values())


def test_explicit_fresh_review_can_reapprove_an_existing_approved_draft():
    cursor, run, runner, advance_calls = _approval_fixture()
    draft = cursor.tables["outreachmessagedrafts"]["draft-1"]
    draft["status"] = "approved"
    draft["approved_text"] = "Earlier approved text"
    payload = _snapshot_drafts_approval(cursor, run, runner)
    assert payload["items"][0]["review_text"] == "Snapshot A"

    assert runner.approve(run["id"], "approval-1", {"user_id": "admin-1"})["success"]
    assert draft["approved_text"] == "Snapshot A"
    assert cursor.tables["agent_approvals"]["approval-1"]["decided_by_user_id"] == "admin-1"
    assert advance_calls
