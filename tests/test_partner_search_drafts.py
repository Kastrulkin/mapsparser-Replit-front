from services import partner_search_drafts as drafts


TASK = {
    "id": "search-1",
    "business_id": "edbd961a-273f-4f15-836e-33aacc0aa0e3",
    "payload_json": {"mode": "find_only", "language": "en", "offer": "Pre-booked airport transfers for travel agencies."},
    "result_json": {"lead_ids": ["lead-1", "lead-2", "lead-1"]},
}


class Cursor:
    def __init__(self):
        self.rows = []
        self.row = None

    def execute(self, query, params=None):
        normalized = " ".join(query.split()).lower()
        if "from operator_async_jobs" in normalized and "kind='outreach_continue'" in normalized:
            self.row = TASK
        elif "from prospectingleads lead" in normalized:
            self.rows = [
                {"id": "lead-1", "name": "Agency One", "status": "new", "pipeline_status": "in_progress", "workstream_id": "ws-1"},
                {"id": "lead-2", "name": "Agency Two", "status": "new", "pipeline_status": "unprocessed", "workstream_id": "ws-2"},
            ]
        else:
            raise AssertionError(normalized)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


def test_preview_uses_shortlist_and_deduplicates(monkeypatch):
    monkeypatch.setattr(drafts, "actor_can_write", lambda *args: True)
    result = drafts.operator_task(Cursor(), business_id=TASK["business_id"], user_id="user-1",
                                  arguments={"operation": "preview", "task_id": "search-1"})
    assert result["eligible_count"] == 1
    assert result["scope"] == "shortlist"
    assert result["preview_ready"] is True
    assert "Отправки не будет" in result["chat_response"]


def test_all_new_requires_count_correction_without_creating_job(monkeypatch):
    monkeypatch.setattr(drafts, "actor_can_write", lambda *args: True)
    result = drafts.operator_task(Cursor(), business_id=TASK["business_id"], user_id="user-1",
                                  arguments={"operation": "preview", "task_id": "search-1",
                                             "scope": "all_new", "count": 3})
    assert result["status"] == "clarification_required"
    assert result["eligible_count"] == 2
    assert result["blocked_reasons"] == ["count_mismatch"]


def test_start_rejects_stale_selection(monkeypatch):
    monkeypatch.setattr(drafts, "actor_can_write", lambda *args: True)
    result = drafts.operator_task(Cursor(), business_id=TASK["business_id"], user_id="user-1",
                                  arguments={"operation": "start", "task_id": "search-1",
                                             "revision": "old"})
    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["stale_review"]


def test_duplicate_company_from_two_leads_is_only_one_draft_target():
    class DuplicateCursor(Cursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            if "from prospectingleads lead" in " ".join(query.split()).lower():
                self.rows[0]["website"] = "https://agency.example/"
                self.rows[1]["website"] = "https://www.agency.example/tours"

    candidates = drafts._candidates(DuplicateCursor(), TASK, "all_new")
    assert [row["id"] for row in candidates] == ["lead-1"]


def test_empty_shortlist_asks_whether_to_draft_all_unverified(monkeypatch):
    monkeypatch.setattr(drafts, "actor_can_write", lambda *args: True)

    class UnselectedCursor(Cursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            if "from prospectingleads lead" in " ".join(query.split()).lower():
                for row in self.rows:
                    row["pipeline_status"] = "unprocessed"

    result = drafts.operator_task(UnselectedCursor(), business_id=TASK["business_id"], user_id="user-1",
                                  arguments={"operation": "preview", "task_id": "search-1", "count": 2})
    assert result["status"] == "clarification_required"
    assert result["scope"] == "all_new"
    assert result["eligible_count"] == 2
    assert result["preview_ready"] is True
    assert "без дублей" in result["chat_response"]


def test_preparation_contract_requires_server_job_and_membership():
    class PreparationCursor:
        def execute(self, query, params):
            assert "job.status='running'" in query
            assert "search.business_id=job.business_id" in query
            assert "search.result_json->'lead_ids'" in query
            assert params == ("draft-job", drafts.KIND, "ws-1")
        def fetchone(self):
            return {"payload_json": {"revision": "approved", "offer": "Reviewed offer"}}
    assert drafts.load_preparation_contract(PreparationCursor(), "draft-job", "ws-1")["offer"] == "Reviewed offer"


def test_preparation_contract_rejects_missing_reviewed_offer():
    class PreparationCursor:
        def execute(self, query, params): pass
        def fetchone(self): return {"payload_json": {"revision": "approved"}}
    assert drafts.load_preparation_contract(PreparationCursor(), "draft-job", "ws-1") is None


def test_missing_offer_is_a_question_not_an_invented_promise(monkeypatch):
    monkeypatch.setattr(drafts, "actor_can_write", lambda *args: True)
    monkeypatch.setitem(TASK, "payload_json", {"mode": "find_only", "language": "en"})
    result = drafts.operator_task(Cursor(), business_id=TASK["business_id"], user_id="user-1",
        arguments={"operation": "preview", "task_id": "search-1"})
    assert result["status"] == "clarification_required"
    assert result["blocked_reasons"] == ["offer_required"]


def test_canonical_preview_rejects_inactive_preparation_before_generation(monkeypatch):
    from services import outreach_campaign_service as campaigns
    monkeypatch.setattr(campaigns, "_load_context", lambda *args: {"continuation_managed": True})
    monkeypatch.setattr(campaigns, "_apply_sender_mode", lambda value, *args: value)
    monkeypatch.setattr(drafts, "load_preparation_contract", lambda *args: None)
    preview = campaigns.build_preview(None, "workstream", preparation_job_id="stopped-job", generate_ai=True)
    assert preview["touches"] == []
    assert preview["reason_code"] == "draft_preparation_not_authorized"


def test_campaign_projection_is_scoped_stable_and_keeps_quality_review():
    class ProjectionCursor:
        def __init__(self):
            self.calls = []
        def execute(self, sql, params):
            self.calls.append((sql, params))
        def fetchone(self):
            return {'lead_id':'lead-1','workstream_id':'ws-1','touch_id':'touch-1',
                    'version':2,'generated_text':'Canonical copy','subject':'Subject',
                    'quality_gate_json':{'passed':False},'message_brief_json':{}}
    cursor = ProjectionCursor()
    a = drafts.project_campaign_draft(cursor, task_id='search-1',campaign_id='campaign-1',
                                     business_id='business-1',user_id='user-1')
    b = drafts.project_campaign_draft(cursor, task_id='search-1',campaign_id='campaign-1',
                                     business_id='business-1',user_id='user-1')
    assert a == b
    assert not a['quality_passed']
    assert 'c.business_id=%s' in cursor.calls[0][0]
    assert "j.result_json->'lead_ids'" in cursor.calls[0][0]
    assert 'ON CONFLICT (id) DO NOTHING' in cursor.calls[1][0]
    metadata = cursor.calls[1][1][5].adapted
    assert metadata['manual_review_required'] is True
    assert metadata['campaign_touch_id'] == 'touch-1'
    assert cursor.calls[1][1][3:5] == ('Canonical copy','Canonical copy')


def test_campaign_projection_rejects_unrelated_group():
    import pytest
    class Missing:
        def execute(self, *args): pass
        def fetchone(self): return None
    with pytest.raises(ValueError,match='campaign_outside_search_group'):
        drafts.project_campaign_draft(Missing(),task_id='g',campaign_id='c',business_id='b',user_id='u')
