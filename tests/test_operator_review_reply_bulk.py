from services.operator_review_reply_bulk import (
    classify_bulk_review_reply_intent,
    format_bulk_review_reply_result_for_telegram,
    generate_review_reply_drafts_for_unanswered_reviews,
)


class FakeCursor:
    def __init__(self, *, balance=100, reviews=None, generator_should_fail=False):
        self.balance = balance
        self.reviews = reviews or [
            {
                "id": "review-1",
                "business_id": "biz-1",
                "source": "yandex",
                "external_review_id": "ext-1",
                "rating": 5,
                "author_name": "Клиент",
                "text": "Очень понравился сервис и массаж лица.",
                "published_at": "2026-05-23T10:00:00+00:00",
            },
            {
                "id": "review-2",
                "business_id": "biz-1",
                "source": "yandex",
                "external_review_id": "ext-2",
                "rating": 5,
                "author_name": "Клиент",
                "text": "Приятная команда, обязательно вернусь.",
                "published_at": "2026-05-23T11:00:00+00:00",
            },
        ]
        self.generator_should_fail = generator_should_fail
        self.last_query = ""
        self.last_params = ()
        self.reservation = None
        self.current_reservation_lookup = False
        self.drafts = []
        self.ledger_entries = []
        self.user_updates = []
        self.reservation_updates = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        self.current_reservation_lookup = "from operatorcreditreservations" in self.last_query and "where id =" in self.last_query
        if "insert into operatorcreditreservations" in self.last_query:
            self.reservation = {
                "id": params[0],
                "business_id": params[1],
                "user_id": params[2],
                "action_key": params[3],
                "idempotency_key": params[4],
                "status": "reserved",
                "estimated_credits": params[5],
                "reserved_credits": params[6],
                "charged_credits": 0,
                "released_credits": 0,
                "credit_ledger_id": None,
            }
        if "insert into reviewreplydrafts" in self.last_query:
            self.drafts.append(
                {
                    "id": params[0],
                    "business_id": params[1],
                    "review_id": params[2],
                    "user_id": params[3],
                    "source": params[4],
                    "rating": params[5],
                    "author_name": params[6],
                    "review_text": params[7],
                    "generated_text": params[8],
                    "status": "draft",
                }
            )
        if "update users" in self.last_query:
            self.user_updates.append(params or ())
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())
        if "update operatorcreditreservations" in self.last_query:
            self.reservation_updates.append(params or ())
            if self.reservation:
                self.reservation["status"] = params[0] if params else self.reservation["status"]
                self.reservation["charged_credits"] = params[1] if len(params or ()) > 1 else 0
                self.reservation["released_credits"] = params[2] if len(params or ()) > 2 else 0

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            table_ref = str(params[0] if params else "")
            if "externalbusinessreviews" in table_ref:
                return {"to_regclass": "externalbusinessreviews"}
            if "reviewreplydrafts" in table_ref:
                return {"to_regclass": "reviewreplydrafts"}
            if "operatorcreditreservations" in table_ref:
                return {"to_regclass": "operatorcreditreservations"}
            return {"table_ref": "operatorconsentpolicies"}
        if "from operatorconsentpolicies" in query:
            return {"mode": "ask_each_time"}
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": 0, "used_credits": 0}
        if self.current_reservation_lookup:
            return self.reservation
        if "returning id, status, reserved_credits" in query:
            return {
                "id": (self.reservation or {}).get("id"),
                "status": "reserved",
                "reserved_credits": (self.reservation or {}).get("reserved_credits"),
            }
        if "returning id, business_id, review_id" in query:
            return self.drafts[-1] if self.drafts else None
        return None

    def fetchall(self):
        if "from externalbusinessreviews" in self.last_query:
            review_id = self.last_params[1] if len(self.last_params) > 1 else None
            if review_id:
                return [item for item in self.reviews if item.get("id") == review_id]
            return self.reviews
        return []


def fake_reply_generator(prompt, *, business_id, user_id):
    return '{"reply": "Спасибо за отзыв. Нам очень приятно, что вы остались довольны. Будем рады видеть вас снова."}'


def failing_reply_generator(prompt, *, business_id, user_id):
    raise RuntimeError("model unavailable")


def test_classifies_bulk_review_reply_intent() -> None:
    assert classify_bulk_review_reply_intent("Подготовь ответы на отзывы")
    assert classify_bulk_review_reply_intent("Сгенерируй ответы на отзывы без ответа")
    assert not classify_bulk_review_reply_intent("Добавь новый отзыв в список и сгенерируй ответ: Отличный салон")
    assert not classify_bulk_review_reply_intent("Что требует внимания сегодня?")


def test_generate_review_reply_drafts_for_unanswered_reviews_charges_per_draft() -> None:
    cursor = FakeCursor(balance=100)

    result = generate_review_reply_drafts_for_unanswered_reviews(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        reply_generator=fake_reply_generator,
    )

    assert result["status"] == "completed"
    assert result["reviews_found"] == 2
    assert len(result["drafts"]) == 2
    assert result["charged_credits"] == 2
    assert result["credit_charged"] is True
    assert result["manual_publication_only"] is True
    assert result["external_writes_performed"] is False
    assert len(cursor.ledger_entries) == 1
    assert cursor.ledger_entries[0][2] == -2


def test_generate_review_reply_targets_exact_review() -> None:
    cursor = FakeCursor(balance=100)

    result = generate_review_reply_drafts_for_unanswered_reviews(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        review_id="review-2",
        reply_generator=fake_reply_generator,
    )

    assert result["status"] == "completed"
    assert result["reviews_found"] == 1
    assert result["drafts"][0]["review_id"] == "review-2"
    assert result["charged_credits"] == 1


def test_generate_review_reply_drafts_blocks_when_credits_are_missing() -> None:
    cursor = FakeCursor(balance=1)

    result = generate_review_reply_drafts_for_unanswered_reviews(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        reply_generator=fake_reply_generator,
    )

    assert result["status"] == "blocked"
    assert "insufficient_balance" in result["blocked_reasons"]
    assert result["billing_url"] == "/dashboard/billing"
    assert len(cursor.drafts) == 0
    assert len(cursor.ledger_entries) == 0


def test_generate_review_reply_drafts_releases_when_all_generations_fail() -> None:
    cursor = FakeCursor(balance=100)

    result = generate_review_reply_drafts_for_unanswered_reviews(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        reply_generator=failing_reply_generator,
    )

    assert result["status"] == "blocked"
    assert result["finalization_result"]["status"] == "released"
    assert len(result["drafts"]) == 0
    assert len(cursor.ledger_entries) == 0


def test_formats_bulk_review_reply_result_for_telegram_with_manual_boundary() -> None:
    text = format_bulk_review_reply_result_for_telegram(
        {
            "chat_response": "Подготовил черновики ответов: 2.",
            "drafts": [
                {"generated_text": "Спасибо за отзыв."},
                {"generated_text": "Будем рады видеть вас снова."},
            ],
        }
    )

    assert "Ответ 1:" in text
    assert "Спасибо за отзыв." in text
    assert "Публикация в карты остаётся ручной" in text
    assert "не публиковал" in text
