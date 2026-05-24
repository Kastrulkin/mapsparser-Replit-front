from datetime import datetime, timezone

from services.operator_content_history import list_operator_content_history


class FakeCursor:
    def __init__(self):
        now = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
        self.last_query = ""
        self.last_params = ()
        self.review_drafts = [
            {
                "id": "reply-1",
                "review_id": "review-1",
                "status": "draft",
                "generated_text": "Спасибо за отзыв.",
                "edited_text": "",
                "author_name": "Анна",
                "created_at": now,
                "updated_at": now,
            }
        ]
        self.usernews = [
            {
                "id": "news-1",
                "user_id": "user-1",
                "business_id": "biz-1",
                "source_text": "новая услуга",
                "generated_text": "Новость о новой услуге",
                "approved": 0,
                "prompt_key": "operator_news_generate",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "post-1",
                "user_id": "user-1",
                "business_id": "biz-1",
                "source_text": "новая услуга",
                "generated_text": "Пост о новой услуге",
                "approved": 0,
                "prompt_key": "operator_social_post_generate",
                "created_at": now,
                "updated_at": now,
            },
        ]
        self.service_jobs = [
            {
                "id": "job-1",
                "status": "suggested",
                "selected_count": 3,
                "fixed_count": 0,
                "failed_count": 0,
                "message": "Operator подготовил предложения.",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "job-2",
                "status": "completed",
                "selected_count": 3,
                "fixed_count": 3,
                "failed_count": 0,
                "message": "Применено предложений: 3.",
                "created_at": now,
                "updated_at": now,
            },
        ]

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        if "to_regclass" in self.last_query:
            table_ref = str(self.last_params[0] if self.last_params else "")
            return {"to_regclass": table_ref.replace("public.", "")}
        if "information_schema.columns" in self.last_query:
            return {"?column?": 1}
        return None

    def fetchall(self):
        if "from reviewreplydrafts" in self.last_query:
            return self.review_drafts
        if "from usernews" in self.last_query:
            return self.usernews
        if "from serviceregenerationjobs" in self.last_query:
            return self.service_jobs
        return []


def test_content_history_separates_draft_types_and_service_states() -> None:
    result = list_operator_content_history(
        FakeCursor(),
        business_id="biz-1",
        user_id="user-1",
        limit=20,
    )

    assert result["status"] == "completed"
    assert result["summary"]["items_count"] == 5
    assert result["summary"]["type_counts"]["review_reply_draft"] == 1
    assert result["summary"]["type_counts"]["news_draft"] == 1
    assert result["summary"]["type_counts"]["social_post_draft"] == 1
    assert result["summary"]["type_counts"]["service_suggestion"] == 1
    assert result["summary"]["type_counts"]["service_apply"] == 1
    assert result["limits"]["external_writes_performed"] is False
