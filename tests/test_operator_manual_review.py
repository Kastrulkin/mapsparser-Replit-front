from services.operator_manual_review import classify_operator_chat_intent, process_operator_chat_message


class FakeCursor:
    def __init__(self, *, balance=100, policy=None, generator_should_fail=False):
        self.balance = balance
        self.policy = policy or {"mode": "ask_each_time"}
        self.generator_should_fail = generator_should_fail
        self.last_query = ""
        self.last_params = ()
        self.review = None
        self.draft = None
        self.reservation = None
        self.ledger_entries = []
        self.user_updates = []
        self.reservation_updates = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "insert into externalbusinessreviews" in self.last_query:
            self.review = {
                "id": params[0],
                "business_id": params[1],
                "source": params[2],
                "external_review_id": params[3],
                "rating": params[4],
                "author_name": params[5],
                "text": params[6],
            }
        if "insert into reviewreplydrafts" in self.last_query:
            self.draft = {
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
        if "update users" in self.last_query:
            self.user_updates.append(params or ())
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())
        if "update operatorcreditreservations" in self.last_query:
            self.reservation_updates.append(params or ())
            if self.reservation:
                self.reservation["status"] = params[0] if params else self.reservation["status"]

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            table_ref = str(params[0] if params else "")
            if "operatorcreditreservations" in table_ref:
                return {"to_regclass": "operatorcreditreservations"}
            return {"table_ref": "operatorconsentpolicies"}
        if "from operatorconsentpolicies" in query:
            return self.policy
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": 0, "used_credits": 0}
        if "from operatorcreditreservations" in query:
            return self.reservation
        if "returning id, status, reserved_credits" in query:
            return {
                "id": (self.reservation or {}).get("id"),
                "status": "reserved",
                "reserved_credits": (self.reservation or {}).get("reserved_credits"),
            }
        if "returning id, business_id, source" in query:
            return self.review
        if "returning id, business_id, review_id" in query:
            return self.draft
        return None


def fake_reply_generator(prompt, *, business_id, user_id):
    return '{"reply": "Спасибо за такой подробный и тёплый отзыв. Рады, что вы остались довольны массажем лица и работой Виктории. Будем рады видеть вас снова в Oliver."}'


def failing_reply_generator(prompt, *, business_id, user_id):
    raise RuntimeError("model unavailable")


def test_classifies_manual_review_add_and_reply_intent() -> None:
    assert classify_operator_chat_intent("Добавь новый отзыв в список и сгенерируй ответ: Отличный салон") == "manual_review_add_and_reply_generate"


def test_process_operator_chat_message_adds_review_draft_and_charges_credit() -> None:
    cursor = FakeCursor(balance=100)

    result = process_operator_chat_message(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="Добавь новый отзыв в список и сгенерируй ответ: Попала в салон случайно. Массаж лица очень понравился.",
        reply_generator=fake_reply_generator,
    )

    assert result["status"] == "completed"
    assert result["review"]["source"] == "manual_chat"
    assert "Попала в салон случайно" in result["review"]["text"]
    assert result["draft"]["status"] == "draft"
    assert "Спасибо" in result["reply_text"]
    assert result["credit_charged"] is True
    assert result["charged_credits"] == 1
    assert result["external_writes_performed"] is False
    assert "Публикация в карты пока вручную" in result["chat_response"]
    assert result["ui_actions"][0]["action"] == "copy_reply"
    assert result["ui_actions"][0]["payload"]["text"] == result["reply_text"]
    assert result["ui_actions"][1]["href"] == "/dashboard/card?tab=reviews&review_filter=needs_reply"
    assert len(cursor.ledger_entries) == 1
    assert cursor.ledger_entries[0][2] == -1


def test_process_operator_chat_message_blocks_when_credits_are_missing() -> None:
    cursor = FakeCursor(balance=0)

    result = process_operator_chat_message(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="Добавь отзыв и сгенерируй ответ: Очень понравился сервис и массаж лица.",
        reply_generator=fake_reply_generator,
    )

    assert result["status"] == "blocked"
    assert "insufficient_balance" in result["blocked_reasons"]
    assert result["billing_url"] == "/dashboard/billing"
    assert result["ui_actions"][0]["action"] == "open_billing"
    assert "Пополните счёт" in result["chat_response"]
    assert cursor.review is None
    assert cursor.draft is None


def test_process_operator_chat_message_releases_reservation_when_generation_fails() -> None:
    cursor = FakeCursor(balance=100)

    result = process_operator_chat_message(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="Добавь отзыв и сгенерируй ответ: Хороший салон, приятная команда и сильный результат.",
        reply_generator=failing_reply_generator,
    )

    assert result["status"] == "blocked"
    assert "reply_generation_failed" in result["blocked_reasons"]
    assert result["finalization_result"]["status"] == "released"
    assert len(cursor.ledger_entries) == 0
    assert cursor.review is not None
    assert cursor.draft is None
