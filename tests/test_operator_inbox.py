import services.operator_inbox as operator_inbox
from services.operator_inbox import build_operator_inbox


class FakeCursor:
    def __init__(self):
        self.last_query = ""
        self.last_params = ()
        self.fetchall_rows = [
            {
                "id": "draft-1",
                "review_id": "review-1",
                "author_name": "Клиент",
                "review_text": "Очень понравился массаж лица и работа мастера.",
                "generated_text": "Спасибо за тёплый отзыв. Будем рады видеть вас снова.",
                "status": "draft",
                "updated_at": "2026-05-23T10:00:00+00:00",
            }
        ]

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        if "to_regclass" in self.last_query:
            return {"table_ref": "reviewreplydrafts"}
        return None

    def fetchall(self):
        return self.fetchall_rows


def fake_attention_brief(cursor, business_id, user_id):
    return {
        "metrics": {
            "reviews_without_response": 2,
            "pending_news": 1,
            "partnership_leads_ready": 1,
        }
    }


def test_operator_inbox_combines_attention_items_drafts_and_paid_generation_offers(monkeypatch) -> None:
    monkeypatch.setattr(operator_inbox, "build_attention_brief", fake_attention_brief)
    cursor = FakeCursor()

    inbox = build_operator_inbox(cursor, business_id="biz-1", user_id="user-1")

    assert inbox["status"] == "ready"
    assert inbox["summary"]["items_count"] == 4
    assert inbox["limits"]["external_writes_performed"] is False
    assert inbox["items"][0]["kind"] == "reviews_without_response"
    assert inbox["items"][1]["kind"] == "review_reply_draft"
    assert inbox["items"][1]["primary_action"] == "copy_reply"
    assert inbox["items"][1]["secondary_action"] == "mark_manual_published"
    assert inbox["items"][1]["copy_text"].startswith("Спасибо")
    assert [offer["action_key"] for offer in inbox["paid_generation_offers"]] == [
        "review_replies_generate",
        "news_generate",
        "social_post_generate",
        "services_optimize",
    ]
