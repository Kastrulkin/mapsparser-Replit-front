from flask import Flask

from api import operator_api


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeCursor:
    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def execute(self, query, params=None):
        return None


class FakeDatabaseManager:
    instances = []

    def __init__(self):
        self.conn = FakeConnection()
        self.closed = False
        FakeDatabaseManager.instances.append(self)

    def close(self):
        self.closed = True


def _client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)
    monkeypatch.setattr(operator_api, "DatabaseManager", FakeDatabaseManager)
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1", "id": "user-1"})
    monkeypatch.setattr(operator_api, "verify_business_access", lambda cursor, business_id, user_data: (True, "user-1"))
    monkeypatch.setattr(operator_api, "record_operator_event", lambda *args, **kwargs: None)
    return app.test_client()


def test_operator_chat_rule_based_refresh_does_not_call_ai_router(monkeypatch) -> None:
    client = _client(monkeypatch)
    calls = {"refresh": 0, "ai": 0}

    def refresh(cursor, *, business_id, user_id, explicit_url=None, channel="web"):
        calls["refresh"] += 1
        return {
            "status": "queued",
            "intent": "fresh_reviews_refresh",
            "chat_response": "Запустил обновление карточки.",
            "queue_id": "queue-1",
            "blocked_reasons": [],
        }

    def ai_router(*args, **kwargs):
        calls["ai"] += 1
        raise AssertionError("AI router must not run for rule-based refresh")

    monkeypatch.setattr(operator_api, "refresh_reviews_from_operator", refresh)
    monkeypatch.setattr(operator_api, "classify_operator_intent_with_ai", ai_router)

    response = client.post("/api/operator/chat", json={"business_id": "biz-1", "message": "Обнови карточку"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["operator_result"]["queue_id"] == "queue-1"
    assert "ai_router" not in body["operator_result"]
    assert calls == {"refresh": 1, "ai": 0}


def test_operator_chat_cheap_gate_skips_ai_router_for_smalltalk(monkeypatch) -> None:
    client = _client(monkeypatch)
    calls = {"ai": 0}

    def ai_router(*args, **kwargs):
        calls["ai"] += 1
        raise AssertionError("AI router must not run for smalltalk")

    monkeypatch.setattr(operator_api, "classify_operator_intent_with_ai", ai_router)

    response = client.post("/api/operator/chat", json={"business_id": "biz-1", "message": "привет"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["operator_result"]["status"] == "unsupported"
    assert body["operator_result"]["credit_charged"] is False
    assert calls["ai"] == 0


def test_operator_chat_ai_fallback_card_refresh(monkeypatch) -> None:
    client = _client(monkeypatch)
    calls = {"refresh": 0, "ai": 0}

    def ai_router(cursor, *, business_id, user_id, message, channel="web"):
        calls["ai"] += 1
        return {
            "status": "completed",
            "intent": "operator_intent_ai_router",
            "normalized_intent": "card_refresh",
            "charged_credits": 1,
            "credit_charged": True,
            "finalization_result": {
                "status": "charged",
                "charge_credits": 1,
                "release_credits": 0,
                "side_effects": {"credit_charged": True},
            },
        }

    def refresh(cursor, *, business_id, user_id, explicit_url=None, channel="web"):
        calls["refresh"] += 1
        return {
            "status": "queued",
            "intent": "fresh_reviews_refresh",
            "chat_response": "Запустил обновление карточки.",
            "queue_id": "queue-1",
            "blocked_reasons": [],
        }

    monkeypatch.setattr(operator_api, "classify_operator_intent_with_ai", ai_router)
    monkeypatch.setattr(operator_api, "refresh_reviews_from_operator", refresh)

    response = client.post("/api/operator/chat", json={"business_id": "biz-1", "message": "посмотри что там с карточкой"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    result = body["operator_result"]
    assert result["status"] == "queued"
    assert result["queue_id"] == "queue-1"
    assert result["ai_router"]["intent"] == "card_refresh"
    assert result["ai_router"]["charged_credits"] == 1
    assert "raw_response" not in result["ai_router"]
    assert calls == {"refresh": 1, "ai": 1}


def test_operator_chat_ai_manual_review_guard_does_not_add_review(monkeypatch) -> None:
    client = _client(monkeypatch)
    calls = {"process": 0, "ai": 0}
    original_process = operator_api.process_operator_chat_message

    def process(cursor, *, business_id, user_id, message, channel="web"):
        calls["process"] += 1
        return original_process(cursor, business_id=business_id, user_id=user_id, message=message, channel=channel)

    def ai_router(cursor, *, business_id, user_id, message, channel="web"):
        calls["ai"] += 1
        return {
            "status": "completed",
            "intent": "operator_intent_ai_router",
            "normalized_intent": "manual_review_add_and_reply",
            "charged_credits": 1,
            "credit_charged": True,
            "finalization_result": {
                "status": "charged",
                "charge_credits": 1,
                "release_credits": 0,
                "side_effects": {"credit_charged": True},
            },
        }

    monkeypatch.setattr(operator_api, "process_operator_chat_message", process)
    monkeypatch.setattr(operator_api, "classify_operator_intent_with_ai", ai_router)

    response = client.post("/api/operator/chat", json={"business_id": "biz-1", "message": "надо ответить людям"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is False
    result = body["operator_result"]
    assert result["status"] == "blocked"
    assert "manual_review_text_not_explicit" in result["blocked_reasons"]
    assert result["external_writes_performed"] is False
    assert result["ai_router"]["intent"] == "manual_review_add_and_reply"
    assert calls == {"process": 1, "ai": 1}
