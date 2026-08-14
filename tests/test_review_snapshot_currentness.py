from services.operator_review_canonicalization import CANONICAL_REVIEWS_CTE
from services.yandex_full_reviews_sync import (
    apply_complete_review_snapshot,
    normalize_actor_review,
)


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((" ".join(str(query).lower().split()), params or ()))


def test_mobile_review_list_ignores_reviews_missing_from_latest_complete_snapshot():
    normalized = " ".join(CANONICAL_REVIEWS_CTE.lower().split())

    assert "coalesce(source_reviews.is_current, true) = true" in normalized


def test_complete_snapshot_marks_previous_rows_inactive_and_current_rows_active():
    cursor = RecordingCursor()
    reviews = [
        {
            "external_review_id": "review-1",
            "rating": 5,
            "author_name": "Анна",
            "text": "Спасибо",
            "response_text": "Рады вам",
            "raw_payload": {},
        },
        {
            "external_review_id": "review-2",
            "rating": 4,
            "author_name": "Иван",
            "text": "Всё хорошо",
            "response_text": None,
            "raw_payload": {},
        },
    ]

    result = apply_complete_review_snapshot(
        cursor,
        business_id="business-1",
        reviews=reviews,
        expected_total=2,
    )

    assert result["total"] == 2
    assert result["without_response"] == 1
    assert "set is_current = false" in cursor.calls[0][0]
    assert sum("is_current = true" in query for query, _params in cursor.calls[1:]) == 2


def test_actor_review_normalization_reads_yandex_owner_reply():
    review = normalize_actor_review(
        {
            "reviewId": "review-1",
            "rating": 5,
            "reviewText": "Отлично",
            "reviewerName": "Анна",
            "ownerReplyText": "Спасибо!",
            "reviewDate": "2026-08-14T08:00:00Z",
        }
    )

    assert review is not None
    assert review["response_text"] == "Спасибо!"
    assert review["published_at"].isoformat().startswith("2026-08-14T08:00:00")
