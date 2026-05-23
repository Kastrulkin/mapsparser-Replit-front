from services.operator_news_generation import (
    classify_news_generate_intent,
    extract_news_source_text,
    generate_news_draft_from_operator,
)


class FakeCursor:
    def __init__(self, *, balance=100):
        self.balance = balance
        self.last_query = ""
        self.last_params = ()
        self.current_reservation_lookup = False
        self.reservation = None
        self.news_drafts = []
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
        if "insert into usernews" in self.last_query:
            self.news_drafts.append(
                {
                    "id": params[0],
                    "user_id": params[1],
                    "business_id": params[2],
                    "source_text": params[3],
                    "generated_text": params[4],
                    "approved": 0,
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
            if "operatorcreditreservations" in table_ref:
                return {"to_regclass": "operatorcreditreservations"}
            return {"to_regclass": table_ref}
        if "from operatorconsentpolicies" in query:
            return {"mode": "ask_each_time"}
        if "select credits_balance from users" in query:
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
        if "from businesses" in query:
            return {"id": "biz-1", "name": "Oliver", "description": "Салон красоты"}
        if "returning id, user_id, business_id" in query:
            return self.news_drafts[-1] if self.news_drafts else None
        return None

    def fetchall(self):
        return []


def fake_news_generator(prompt, *, business_id, user_id):
    return '{"news": "Новая процедура в Oliver\\n\\nВ салоне появилась новая услуга для ухода за кожей. Администратор подскажет детали и поможет выбрать удобное время."}'


def empty_news_generator(prompt, *, business_id, user_id):
    return '{"news": ""}'


def failing_news_generator(prompt, *, business_id, user_id):
    raise RuntimeError("model unavailable")


def test_classifies_news_generate_intent() -> None:
    assert classify_news_generate_intent("Подготовь новость про новый массаж лица")
    assert classify_news_generate_intent("Сгенерируй новость: обновили расписание")
    assert not classify_news_generate_intent("Подготовь пост для соцсетей")
    assert not classify_news_generate_intent("Подготовь ответы на отзывы")


def test_extracts_news_source_text_after_marker() -> None:
    assert extract_news_source_text("Подготовь новость: открыли запись на январь") == "открыли запись на январь"


def test_generate_news_draft_charges_and_saves_usernews() -> None:
    cursor = FakeCursor(balance=100)

    result = generate_news_draft_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="Подготовь новость: появилась новая процедура ухода",
        news_generator=fake_news_generator,
    )

    assert result["status"] == "completed"
    assert result["intent"] == "news_generate"
    assert result["credit_charged"] is True
    assert result["charged_credits"] == 1
    assert result["manual_publication_only"] is True
    assert result["external_writes_performed"] is False
    assert len(cursor.news_drafts) == 1
    assert cursor.news_drafts[0]["business_id"] == "biz-1"
    assert "Новая процедура" in cursor.news_drafts[0]["generated_text"]
    assert len(cursor.ledger_entries) == 1
    assert cursor.ledger_entries[0][2] == -1


def test_generate_news_draft_blocks_without_credits() -> None:
    cursor = FakeCursor(balance=0)

    result = generate_news_draft_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="Подготовь новость: появилась новая процедура ухода",
        news_generator=fake_news_generator,
    )

    assert result["status"] == "blocked"
    assert "insufficient_balance" in result["blocked_reasons"]
    assert result["billing_url"] == "/dashboard/billing"
    assert len(cursor.news_drafts) == 0
    assert len(cursor.ledger_entries) == 0


def test_generate_news_draft_releases_when_generation_fails() -> None:
    cursor = FakeCursor(balance=100)

    result = generate_news_draft_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="Подготовь новость: появилась новая процедура ухода",
        news_generator=failing_news_generator,
    )

    assert result["status"] == "blocked"
    assert result["finalization_result"]["status"] == "released"
    assert result["credit_charged"] is False
    assert len(cursor.news_drafts) == 0
    assert len(cursor.ledger_entries) == 0


def test_generate_news_draft_releases_when_model_returns_empty_text() -> None:
    cursor = FakeCursor(balance=100)

    result = generate_news_draft_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        message="Подготовь новость: появилась новая процедура ухода",
        news_generator=empty_news_generator,
    )

    assert result["status"] == "blocked"
    assert result["finalization_result"]["status"] == "released"
    assert "empty_generated_news" in result["blocked_reasons"]
    assert len(cursor.news_drafts) == 0
    assert len(cursor.ledger_entries) == 0
