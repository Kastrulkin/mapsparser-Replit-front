from core.sensitive_text import redact_sensitive_text
from services.yandex_review_delta_sync import (
    apply_yandex_review_delta,
    native_delta_completeness,
    normalize_native_review,
)


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((" ".join(str(query).lower().split()), params or ()))


def test_native_delta_requires_known_review_boundary():
    card_data = {
        "reviews": [
            {"id": "new-1", "text": "Новый", "rating": 5},
            {"id": "known-1", "text": "Старый", "rating": 4},
        ],
        "_parser_run": {"delta_boundary_reached": True, "review_stop_reason": "known_review_id"},
    }

    assert native_delta_completeness(
        card_data,
        known_review_ids=["known-1"],
        expected_total=300,
    ) == (True, "known_review_id")

    incomplete = dict(card_data)
    incomplete["reviews"] = [{"id": "new-1", "text": "Новый", "rating": 5}]
    incomplete["_parser_run"] = {"delta_boundary_reached": False, "review_stop_reason": "no_new_review_ids"}
    assert native_delta_completeness(
        incomplete,
        known_review_ids=["known-1"],
        expected_total=300,
    ) == (False, "no_new_review_ids")


def test_delta_upsert_does_not_deactivate_previous_snapshot():
    cursor = RecordingCursor()
    result = apply_yandex_review_delta(
        cursor,
        business_id="business-1",
        reviews=[
            {
                "id": "review-1",
                "author": "Анна",
                "text": "Отлично",
                "rating": "5",
                "org_reply": "Спасибо!",
                "date": "2026-08-25T10:00:00Z",
            }
        ],
    )

    assert result["upserted"] == 1
    assert len(cursor.calls) == 1
    assert "on conflict (id)" in cursor.calls[0][0]
    assert "set is_current = false" not in cursor.calls[0][0]


def test_native_review_normalization_keeps_reply_and_stable_id():
    review = normalize_native_review(
        {
            "id": "review-1",
            "author": "Иван",
            "text": "Хорошо",
            "rating": "4.0",
            "response_text": "Благодарим",
        }
    )

    assert review is not None
    assert review["external_review_id"] == "review-1"
    assert review["rating"] == 4
    assert review["response_text"] == "Благодарим"


def test_parser_errors_redact_query_header_and_json_secrets():
    raw = (
        "https://api.apify.com/v2/runs?token=secret-token&x=1 "
        "Authorization: Bearer bearer-secret "
        "{'password':'proxy-secret'}"
    )
    safe = redact_sensitive_text(raw)

    assert "secret-token" not in safe
    assert "bearer-secret" not in safe
    assert "proxy-secret" not in safe
    assert safe.count("[REDACTED]") == 3
