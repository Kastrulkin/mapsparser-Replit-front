from services.operator_manual_publish import mark_review_reply_draft_manual_published


class FakeCursor:
    def __init__(self, *, draft=None):
        if draft is None:
            draft = {
                "id": "draft-1",
                "business_id": "biz-1",
                "review_id": "review-1",
                "generated_text": "Спасибо за отзыв.",
                "edited_text": "",
                "status": "draft",
            }
        self.draft = draft
        self.updated_draft = None
        self.review_updates = []
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "update reviewreplydrafts" in self.last_query:
            self.updated_draft = {
                "id": params[0],
                "review_id": self.draft.get("review_id"),
                "status": "manual_published",
                "updated_at": "2026-05-23T10:00:00+00:00",
            }
        if "update externalbusinessreviews" in self.last_query:
            self.review_updates.append(params or ())

    def fetchone(self):
        if "select id, business_id, review_id" in self.last_query:
            return self.draft
        if "returning id, review_id, status" in self.last_query:
            return self.updated_draft
        return None


def test_mark_review_reply_draft_manual_published_updates_local_state_only() -> None:
    cursor = FakeCursor()

    result = mark_review_reply_draft_manual_published(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        draft_id="draft-1",
    )

    assert result["status"] == "completed"
    assert result["draft"]["status"] == "manual_published"
    assert result["manual_publication_only"] is True
    assert result["external_writes_performed"] is False
    assert result["ui_actions"][0]["action"] == "open_reviews"
    assert len(cursor.review_updates) == 1
    assert cursor.review_updates[0][0] == "Спасибо за отзыв."


def test_mark_review_reply_draft_manual_published_blocks_missing_draft() -> None:
    cursor = FakeCursor(draft={})

    result = mark_review_reply_draft_manual_published(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        draft_id="draft-404",
    )

    assert result["status"] == "blocked"
    assert "draft_not_found" in result["blocked_reasons"]
    assert result["external_writes_performed"] is False
