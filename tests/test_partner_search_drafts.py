from services import partner_search_drafts as drafts


TASK = {
    "id": "search-1",
    "business_id": "edbd961a-273f-4f15-836e-33aacc0aa0e3",
    "payload_json": {"mode": "find_only", "language": "en"},
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
