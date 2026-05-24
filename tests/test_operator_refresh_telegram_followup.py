from services.operator_refresh_telegram_followup import (
    dispatch_operator_refresh_telegram_followup,
    format_refresh_followup_text,
)


class FakeCursor:
    def __init__(self):
        self.last_query = ""
        self.last_params = ()
        self.reservation = {
            "id": "reservation-1",
            "status": "charged",
            "metadata": {"parsequeue_id": "queue-1", "settlement_status": "charged"},
        }
        self.contact = {"business_name": "Оливер", "telegram_id": "12345"}
        self.queue = {
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "completed",
            "source": "apify_yandex",
            "task_type": "parse_card",
            "error_message": "",
            "created_at": "2026-05-24T10:00:00+00:00",
            "updated_at": "2026-05-24T10:05:00+00:00",
        }
        self.reviews = [
            {
                "id": "review-1",
                "source": "yandex",
                "external_review_id": "ext-1",
                "rating": 5,
                "author_name": "Анна",
                "text": "Очень понравился сервис.",
                "response_text": "",
                "published_at": "2026-05-24T10:04:00+00:00",
                "created_at": "2026-05-24T10:05:00+00:00",
            }
        ]
        self.metadata_updates = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if self.last_query.startswith("update operatorcreditreservations"):
            self.metadata_updates.append(params)

    def fetchone(self):
        if "select id, status, metadata from operatorcreditreservations" in self.last_query:
            return self.reservation
        if "from businesses b join users u" in self.last_query:
            return self.contact
        if "from parsequeue" in self.last_query:
            return self.queue
        if "select to_regclass" in self.last_query:
            return {"to_regclass": "operatorcreditreservations"}
        if "select id, status, estimated_credits" in self.last_query:
            return {
                "id": "reservation-1",
                "status": "charged",
                "estimated_credits": 10,
                "reserved_credits": 10,
                "charged_credits": 4,
                "released_credits": 6,
                "metadata": {
                    "parsequeue_id": "queue-1",
                    "provider_actual_cost": "0.40",
                    "actual_credits": 4,
                    "settlement_status": "charged",
                },
                "created_at": "2026-05-24T10:00:00+00:00",
                "updated_at": "2026-05-24T10:05:00+00:00",
                "finalized_at": "2026-05-24T10:05:00+00:00",
            }
        return None

    def fetchall(self):
        if "from externalbusinessreviews" in self.last_query:
            return self.reviews
        return []


def test_dispatch_refresh_followup_sends_once_and_marks_metadata() -> None:
    cursor = FakeCursor()
    sent_messages = []

    def fake_send(chat_id, text):
        sent_messages.append((chat_id, text))
        return True

    result = dispatch_operator_refresh_telegram_followup(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        queue_id="queue-1",
        send_func=fake_send,
    )

    assert result["status"] == "sent"
    assert result["sent"] is True
    assert sent_messages
    assert sent_messages[0][0] == "12345"
    assert "Обновление завершено" in sent_messages[0][1]
    assert "публикация в карты остаётся ручной" in sent_messages[0][1].lower()
    assert len(cursor.metadata_updates) == 2
    assert "telegram_refresh_followup_attempted_at" in cursor.metadata_updates[0][0]
    assert "telegram_refresh_followup_delivered_at" in cursor.metadata_updates[1][0]


def test_dispatch_refresh_followup_skips_duplicate_attempt() -> None:
    cursor = FakeCursor()
    cursor.reservation["metadata"] = {
        "parsequeue_id": "queue-1",
        "telegram_refresh_followup_attempted_at": "2026-05-24T10:05:00Z",
    }

    result = dispatch_operator_refresh_telegram_followup(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        queue_id="queue-1",
        send_func=lambda chat_id, text: True,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "telegram_refresh_followup_already_attempted"
    assert cursor.metadata_updates == []


def test_dispatch_refresh_followup_skips_without_owner_telegram() -> None:
    cursor = FakeCursor()
    cursor.contact = {"business_name": "Оливер", "telegram_id": ""}

    result = dispatch_operator_refresh_telegram_followup(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        queue_id="queue-1",
        send_func=lambda chat_id, text: True,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "owner_telegram_id_missing"
    assert cursor.metadata_updates == []


def test_format_refresh_followup_keeps_copy_publish_boundary() -> None:
    text = format_refresh_followup_text(
        {
            "status": "completed",
            "new_reviews_count": 1,
            "new_unanswered_reviews_count": 1,
            "billing_state": {"label": "Списано по факту: 4"},
            "new_reviews": [{"author_name": "Анна", "text": "Спасибо, всё понравилось."}],
        },
        business_name="Оливер",
    )

    assert "Оливер" in text
    assert "Новых отзывов: 1" in text
    assert "Списано по факту: 4" in text
    assert "вы копируете и вставляете сами" in text
