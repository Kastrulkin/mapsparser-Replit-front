import pytest
from services import outreach_draft_review as review


def test_review_digest_changes_with_native_recipient():
    draft = {"id": "d", "email": "legacy@example.test", "canonical_review": {"recipient": "first@example.test"}}
    before = review.draft_review_digest(draft)
    draft["canonical_review"]["recipient"] = "second@example.test"
    assert review.draft_review_digest(draft) != before


def test_batch_changed_after_review_never_queues(monkeypatch):
    monkeypatch.setattr("services.outreach_safety_service.load_partnership_repeat_contact_guard", lambda *args, **kwargs: {"blocked": False})
    monkeypatch.setattr(review, "canonical_review", lambda *args: {"hash": "changed"})
    class Cursor:
        def execute(self, *args): raise AssertionError("must not mutate a stale review")
    row = {"lead_id": "lead", "generated_text": "Body", "approved_text": "Body", "learning_note_json": {"reviewed_campaign_hash": "approved"}}
    assert review.approve_reviewed_campaigns(Cursor(), "batch", [row], "user") is not None


def test_native_batch_reuses_one_campaign_and_never_calls_a_provider(monkeypatch):
    from services import outreach_campaign_service as campaigns
    monkeypatch.setattr("services.outreach_safety_service.load_partnership_repeat_contact_guard", lambda *args, **kwargs: {"blocked": False})
    monkeypatch.setattr(review, "canonical_review", lambda *args: {"hash": "approved"})
    approvals = []
    monkeypatch.setattr(campaigns, "approve_campaign", lambda cursor, campaign_id, **kwargs: approvals.append((campaign_id, kwargs)))
    class Cursor:
        def execute(self, sql, params):
            assert "DELETE FROM outreachsendqueue" in sql
            assert params == (["queue"],)
    row = {"lead_id": "lead", "id": "queue", "campaign_id": "campaign", "generated_text": "Body", "approved_text": "Body",
           "learning_note_json": {"reviewed_campaign_hash": "approved"}}
    assert review.approve_reviewed_campaigns(Cursor(), "batch", [row], "user") is None
    assert approvals == [("campaign", {"user_id": "user", "reviewed_batch_id": "batch"})]


def test_answer_received_before_confirmation_stops_queueing(monkeypatch):
    monkeypatch.setattr("services.outreach_safety_service.load_partnership_repeat_contact_guard", lambda *args, **kwargs: {"blocked": True})
    class Cursor:
        def execute(self, *args): raise AssertionError("must not queue after reply")
    assert "ответила" in review.approve_reviewed_campaigns(Cursor(), "batch", [{"lead_id": "lead"}], "user")
