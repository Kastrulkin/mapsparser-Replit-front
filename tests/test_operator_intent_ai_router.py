from services.operator_intent_ai_router import (
    OPERATOR_INTENT_CLASSIFY_ACTION_KEY,
    classify_operator_intent_with_ai,
    normalize_ai_intent,
    should_use_ai_intent_router,
)


class FakeCursor:
    def __init__(self, *, balance=100):
        self.balance = balance
        self.last_query = ""
        self.last_params = ()
        self.current_reservation_lookup = False
        self.reservation = None
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
            if "operatorcreditreservations" in table_ref:
                return {"to_regclass": "operatorcreditreservations"}
            return {"to_regclass": table_ref}
        if "from operatorconsentpolicies" in query:
            return {"mode": "ask_each_time"}
        if "select credits_balance from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            if "charged_credits" in query and "greatest" in query:
                return {"used_credits": 0}
            return {"reserved_credits": 0, "used_credits": 0}
        if self.current_reservation_lookup:
            return self.reservation
        if "returning id, status, reserved_credits" in query:
            return {
                "id": (self.reservation or {}).get("id"),
                "status": "reserved",
                "reserved_credits": (self.reservation or {}).get("reserved_credits"),
            }
        return None

    def fetchall(self):
        return []


def intent_generator_card(prompt, *, business_id, user_id):
    return '{"intent": "card_refresh"}'


def intent_generator_garbage(prompt, *, business_id, user_id):
    return "не json"


def intent_generator_fails(prompt, *, business_id, user_id):
    raise RuntimeError("model unavailable")


def test_normalize_ai_intent_accepts_aliases_and_unknown() -> None:
    assert normalize_ai_intent('{"intent": "map_reviews_refresh"}') == "card_refresh"
    assert normalize_ai_intent('{"intent": "bulk_review_replies_generate"}') == "review_replies_generate"
    assert normalize_ai_intent('{"intent": "operator_help"}') == "operator_help"
    assert normalize_ai_intent("some nonsense") == "unknown"


def test_ai_router_cheap_gate_skips_smalltalk_and_allows_operator_commands() -> None:
    assert should_use_ai_intent_router("посмотри что там с карточкой")
    assert should_use_ai_intent_router("надо ответить людям")
    assert should_use_ai_intent_router("собери свежие данные по салону")
    assert should_use_ai_intent_router("почему рейтинг просел")
    assert should_use_ai_intent_router("разберись с этим")
    assert not should_use_ai_intent_router("привет")
    assert not should_use_ai_intent_router("Добрый день!")
    assert not should_use_ai_intent_router("спасибо")
    assert not should_use_ai_intent_router("?")


def test_ai_router_charges_credit_and_returns_normalized_intent() -> None:
    cursor = FakeCursor(balance=100)

    result = classify_operator_intent_with_ai(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="посмотри что там с карточкой",
        intent_generator=intent_generator_card,
    )

    assert result["status"] == "completed"
    assert result["intent"] == "operator_intent_ai_router"
    assert result["normalized_intent"] == "card_refresh"
    assert "raw_response" not in result
    assert result["credit_charged"] is True
    assert result["charged_credits"] == 1
    assert cursor.reservation["action_key"] == OPERATOR_INTENT_CLASSIFY_ACTION_KEY
    assert len(cursor.ledger_entries) == 1
    assert cursor.ledger_entries[0][2] == -1


def test_ai_router_blocks_without_credits_before_model_call() -> None:
    cursor = FakeCursor(balance=0)
    calls = []

    def generator(prompt, *, business_id, user_id):
        calls.append(prompt)
        return '{"intent": "card_refresh"}'

    result = classify_operator_intent_with_ai(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="посмотри что там с карточкой",
        intent_generator=generator,
    )

    assert result["status"] == "blocked"
    assert "insufficient_balance" in result["blocked_reasons"]
    assert result["billing_url"] == "/dashboard/billing"
    assert result["credit_charged"] is False
    assert calls == []
    assert len(cursor.ledger_entries) == 0


def test_ai_router_charges_even_when_model_returns_unknown() -> None:
    cursor = FakeCursor(balance=100)

    result = classify_operator_intent_with_ai(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="абракадабра",
        intent_generator=intent_generator_garbage,
    )

    assert result["status"] == "completed"
    assert result["normalized_intent"] == "unknown"
    assert result["credit_charged"] is True
    assert len(cursor.ledger_entries) == 1


def test_ai_router_releases_when_model_fails() -> None:
    cursor = FakeCursor(balance=100)

    result = classify_operator_intent_with_ai(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="посмотри что там с карточкой",
        intent_generator=intent_generator_fails,
    )

    assert result["status"] == "blocked"
    assert result["credit_charged"] is False
    assert result["finalization_result"]["status"] == "released"
    assert len(cursor.ledger_entries) == 0
