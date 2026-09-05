from datetime import datetime, timezone

import pytest
from flask import Flask

from services.outreach_draft_review import draft_review_digest


@pytest.fixture
def draft():
    return {"id": "draft-1", "lead_id": "lead-1", "channel": "email", "status": "draft",
            "generated_text": "Предложение", "edited_text": None, "approved_text": None,
            "updated_at": datetime(2026, 9, 5, tzinfo=timezone.utc),
            "email": "review@example.test", "selected_channel": "email", "learning_note_json": {}}


@pytest.mark.parametrize("field,new_value", [("edited_text", "Другое предложение"),
    ("email", "another@example.test"), ("channel", "telegram"), ("selected_channel", "manual"),
    ("lead_id", "lead-2"), ("updated_at", datetime(2026, 9, 6, tzinfo=timezone.utc))])
def test_any_reviewed_target_or_revision_change_invalidates_digest(draft, field, new_value):
    assert draft_review_digest(draft) != draft_review_digest({**draft, field: new_value})


def test_approve_stale_review_rolls_back_before_mutation(monkeypatch, draft):
    from api import admin_prospecting
    outreach_routes = admin_prospecting
    statements = []
    rolled_back = []

    class Connection:
        def cursor(self):
            return self

        def execute(self, query, params=None):
            statements.append(query)

        def fetchone(self):
            return {**draft, "email": "changed@example.test"}

        def rollback(self):
            rolled_back.append(True)

        def close(self):
            pass

    monkeypatch.setattr(outreach_routes, "get_db_connection", Connection)
    monkeypatch.setattr(outreach_routes, "_require_auth", lambda: ({"user_id": "u-1"}, None), raising=False)
    monkeypatch.setattr(outreach_routes, "_ensure_partnership_columns", lambda _conn: None, raising=False)
    monkeypatch.setattr(outreach_routes, "ensure_ai_learning_events_table", lambda _conn: None, raising=False)
    monkeypatch.setattr(outreach_routes, "_resolve_business_for_user", lambda *_args: "b-1", raising=False)
    app = Flask(__name__)
    with app.test_request_context(json={"business_id": "b-1", "approved_text": draft["generated_text"],
                                       "expected_review_digest": draft_review_digest(draft)}, method="POST"):
        response, status = outreach_routes.partnership_approve_draft("draft-1")
    assert status == 409
    assert response.get_json()["code"] == "draft_review_stale"
    assert rolled_back == [True]
    assert "FOR UPDATE OF d, l" in statements[0]
    assert not any("UPDATE outreachmessagedrafts" in statement for statement in statements)


@pytest.mark.parametrize("digest", [None, "", "forged"])
def test_approve_without_valid_review_rejects_before_database(monkeypatch, digest):
    from api import admin_prospecting
    outreach_routes = admin_prospecting
    monkeypatch.setattr(outreach_routes, "_require_auth", lambda: ({"user_id":"u-1"}, None), raising=False)
    monkeypatch.setattr(outreach_routes, "get_db_connection", lambda: pytest.fail("Unreviewed request must not open DB"))
    app = Flask(__name__)
    with app.test_request_context(method="POST",json={"business_id":"b-1","approved_text":"Text","expected_review_digest":digest}):
        response, status = outreach_routes.partnership_approve_draft("draft-1")
    assert status == 400
    assert response.get_json()["code"] == "draft_review_required"
