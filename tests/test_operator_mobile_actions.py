from datetime import datetime, timezone

from services.operator_mobile_actions import confirm_mobile_action, create_mobile_action_preview


class ActionCursor:
    def __init__(self):
        self.query = ""
        self.params = ()
        self.rows = []
        self.action = None

    def execute(self, query, params=()):
        self.query = " ".join(str(query).lower().split())
        self.params = params or ()
        if "from externalbusinessreviews reviews" in self.query:
            requested = set(params[0])
            source = [
                {"id": "r-1", "business_id": "b-1", "business_name": "Первая", "author_name": "Анна", "rating": 5, "source": "yandex"},
                {"id": "r-2", "business_id": "b-2", "business_name": "Вторая", "author_name": "Игорь", "rating": 2, "source": "2gis"},
            ]
            self.rows = [item for item in source if item["id"] in requested]
        elif self.query.startswith("insert into operatoractions"):
            if not self.action:
                self.action = {
                    "id": params[0], "business_id": params[1], "user_id": params[2], "capability": params[3],
                    "idempotency_key": params[4], "envelope_json": params[5], "scope_type": params[6],
                    "scope_id": params[7], "target_business_ids_json": params[8], "preview_json": params[9],
                    "estimated_credits": params[10], "external_effects": params[11], "is_mass_action": params[12],
                    "expires_at": params[13], "status": "pending", "result_json": {},
                }
            self.rows = [{"id": self.action["id"], "status": self.action["status"], "idempotency_key": self.action["idempotency_key"]}]
        elif "select * from operatoractions" in self.query:
            self.rows = [self.action] if self.action and self.action["id"] == params[0] and self.action["user_id"] == params[1] else []
        elif self.query.startswith("update operatoractions"):
            self.action["status"] = "completed"
            self.action["result_json"] = params[0]
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {self.query}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_preview_resolves_targets_and_confirm_is_idempotent():
    cursor = ActionCursor()
    scope = {"kind": "network", "id": "n-1", "name": "Сеть", "business_ids": ["b-1", "b-2"]}
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope=scope,
        capability="review_replies.generate",
        input_payload={"review_ids": ["r-1", "r-2"]},
    )

    assert preview["status"] == "preview"
    assert preview["is_mass_action"] is True
    assert preview["estimated_credits"] == 2
    assert [item["id"] for item in preview["target_businesses"]] == ["b-1", "b-2"]

    calls = []
    executor = lambda envelope, targets, resolved: calls.append((envelope, targets, resolved)) or {"status": "completed", "drafts": ["d-1", "d-2"]}
    first, idempotent = confirm_mobile_action(
        cursor,
        action_id=preview["action_id"],
        user_id="u-1",
        scope_resolver=lambda kind, scope_id: scope if (kind, scope_id) == ("network", "n-1") else None,
        executors={"review_replies.generate": executor},
    )
    second, repeated = confirm_mobile_action(
        cursor,
        action_id=preview["action_id"],
        user_id="u-1",
        scope_resolver=lambda kind, scope_id: scope,
        executors={"review_replies.generate": executor},
    )

    assert first["status"] == "completed"
    assert idempotent is False
    assert second["status"] == "completed"
    assert repeated is True
    assert len(calls) == 1


def test_preview_rejects_review_outside_scope():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="review_replies.generate",
        input_payload={"review_ids": ["r-2"]},
    )

    assert preview["status"] == "blocked"
    assert "objects_not_found_or_forbidden" in preview["blocked_reasons"]


def test_expired_preview_does_not_execute():
    cursor = ActionCursor()
    cursor.action = {
        "id": "a-1", "user_id": "u-1", "status": "pending", "scope_type": "business", "scope_id": "b-1",
        "target_business_ids_json": ["b-1"], "capability": "review_replies.generate", "envelope_json": {"review_ids": ["r-1"]},
        "expires_at": datetime(2020, 1, 1, tzinfo=timezone.utc), "result_json": {},
    }
    result, idempotent = confirm_mobile_action(
        cursor,
        action_id="a-1",
        user_id="u-1",
        scope_resolver=lambda kind, scope_id: {"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        executors={"review_replies.generate": lambda *_args: {"status": "completed"}},
    )

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["preview_expired"]
    assert idempotent is False
