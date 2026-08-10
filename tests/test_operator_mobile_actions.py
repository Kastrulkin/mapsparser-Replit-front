from datetime import datetime, timezone

from services.operator_mobile_actions import confirm_mobile_action, create_mobile_action_preview


class ActionCursor:
    def __init__(self):
        self.query = ""
        self.params = ()
        self.rows = []
        self.action = None
        self.archived_actions = []

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
        elif self.query.startswith("select id, name from businesses"):
            self.rows = [{"id": "b-1", "name": "Первая"}] if params[0] == "b-1" else []
        elif "from contentplans plan" in self.query:
            self.rows = [{"id": "plan-1", "business_id": "b-1", "title": "План на месяц", "business_name": "Первая", "items_count": 8}] if params[0] == "plan-1" else []
        elif "from contentplanitems item" in self.query:
            self.rows = [{"id": "item-1", "business_id": "b-1", "theme": "Летний уход", "status": "planned", "plan_id": "plan-1", "business_name": "Первая"}] if params[0] == "item-1" else []
        elif "from userservices service" in self.query:
            self.rows = [{"id": "s-1", "business_id": "b-1", "name": "Стрижка", "description": "С укладкой", "category": "Стрижки", "price": "2900", "is_active": True, "business_name": "Первая"}] if params[0] == "s-1" else []
        elif "from userservices" in self.query:
            self.rows = [
                {"id": "s-1", "business_id": "b-1", "name": "Стрижка", "description": "С укладкой", "category": "Стрижки", "price": "2900"},
                {"id": "s-2", "business_id": "b-1", "name": "Окрашивание", "description": "", "category": "Цвет", "price": "5000"},
            ] if params[0] == "b-1" else []
        elif "from financialtransactions transaction" in self.query:
            self.rows = [{"id": "t-1", "business_id": "b-1", "amount": 2900, "transaction_date": "2026-07-24", "description": "Стрижка", "business_name": "Первая"}] if params == ("t-1", "b-1") else []
        elif "from lead_workstreams workstream" in self.query:
            requested = set(params[1])
            source = [
                {"id": "lead-1", "name": "Партнёр один", "city": "Москва", "category": "Кофе", "business_id": "b-1", "business_name": "Первая"},
                {"id": "lead-2", "name": "Партнёр два", "city": "Москва", "category": "Цветы", "business_id": "b-1", "business_name": "Первая"},
            ]
            self.rows = [item for item in source if params[0] == "b-1" and item["id"] in requested]
        elif "from parsequeue queue" in self.query:
            self.rows = [{"id": "q-1", "business_id": "b-1", "url": "https://yandex.ru/maps/org/1", "status": "failed", "source": "yandex", "error_message": "timeout", "business_name": "Первая"}] if params[0] == "q-1" else []
        elif "from knowledge_source_subscriptions subscription" in self.query:
            self.rows = [{"id": "source-1", "business_id": "b-1", "title": "Beauty Owners", "canonical_url": "https://t.me/beauty", "business_name": "Первая"}] if params == ("b-1", "source-1") else []
        elif "from outreachmessagedrafts draft" in self.query:
            self.rows = [{"id": "draft-1", "lead_id": "lead-1", "channel": "email", "status": "draft", "lead_name": "Партнёр один", "business_id": "b-1", "business_name": "Первая"}] if params == ("draft-1", "b-1") else []
        elif "from operatoractions" in self.query and "idempotency_key" in self.query and "select id, status" in self.query:
            self.rows = [self.action] if self.action and self.action["user_id"] == params[0] and self.action["idempotency_key"] == params[1] else []
        elif self.query.startswith("update operatoractions") and "set preview_json" in self.query:
            if self.action:
                self.action["preview_json"] = params[0]
                self.action["expires_at"] = params[1]
            self.rows = []
        elif self.query.startswith("update operatoractions") and "set idempotency_key = idempotency_key ||" in self.query:
            if self.action and self.action["id"] == params[0]:
                self.action["idempotency_key"] = f"{self.action['idempotency_key']}:closed:{self.action['id'][:8]}"
                self.archived_actions.append(self.action)
                self.action = None
            self.rows = []
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


def test_finance_preview_keeps_reviewed_sales_and_business_target():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="finance.sales_import",
        input_payload={
            "business_id": "b-1",
            "transactions": [
                {"transaction_date": "2026-07-24", "amount": 2900, "title": "Стрижка", "sale_type": "service"},
                {"transaction_date": "2026-07-24", "amount": 850, "title": "Шампунь", "sale_type": "cross_sell"},
            ],
        },
    )

    assert preview["status"] == "preview"
    assert preview["estimated_credits"] == 0
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]
    assert [item["sale_type"] for item in preview["objects"]] == ["service", "cross_sell"]


def test_card_schedule_preview_uses_scope_business_not_untrusted_target():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="cards.schedule.update",
        input_payload={"business_id": "b-2", "enabled": True, "interval_hours": 48},
    )

    assert preview["status"] == "preview"
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]
    assert preview["changes"][0]["interval_hours"] == 48
    assert preview["estimated_credits"] == 0


def test_completed_repeatable_action_does_not_block_a_new_user_intent():
    cursor = ActionCursor()
    scope = {"kind": "business", "id": "b-1", "business_ids": ["b-1"]}
    first = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope=scope,
        capability="cards.refresh",
        input_payload={"business_id": "b-1", "source": "all"},
    )
    cursor.action["status"] = "completed"
    cursor.action["result_json"] = {"status": "completed", "job_id": "old-job"}

    second = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope=scope,
        capability="cards.refresh",
        input_payload={"business_id": "b-1", "source": "all"},
    )

    assert first["status"] == "preview"
    assert second["status"] == "preview"
    assert second["action_id"] != first["action_id"]


def test_identical_unconfirmed_preview_is_reused():
    cursor = ActionCursor()
    scope = {"kind": "business", "id": "b-1", "business_ids": ["b-1"]}
    first = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope=scope,
        capability="cards.refresh",
        input_payload={"business_id": "b-1", "source": "all"},
    )
    second = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope=scope,
        capability="cards.refresh",
        input_payload={"business_id": "b-1", "source": "all"},
    )

    assert second["action_id"] == first["action_id"]
    assert cursor.archived_actions == []


def test_community_source_unsubscribe_preview_is_scoped_to_the_business():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="community_sources.unsubscribe",
        input_payload={"business_id": "b-2", "source_id": "source-1"},
    )

    assert preview["status"] == "preview"
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]
    assert preview["objects"][0]["id"] == "source-1"


def test_partnership_draft_delete_preview_is_scoped_to_the_business():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="partnerships.draft.delete",
        input_payload={"business_id": "b-2", "draft_id": "draft-1"},
    )

    assert preview["status"] == "preview"
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]
    assert preview["objects"][0]["id"] == "draft-1"
    assert preview["changes"][0]["label"] == "Удалить черновик для Партнёр один"


def test_partnership_draft_delete_preview_rejects_missing_draft():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="partnerships.draft.delete",
        input_payload={"draft_id": "draft-foreign"},
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_reasons"] == ["partnership_draft_not_found_or_forbidden"]


def test_content_plan_delete_preview_contains_affected_items():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="content.plan.delete",
        input_payload={"plan_id": "plan-1"},
    )

    assert preview["status"] == "preview"
    assert preview["changes"] == [{
        "object_id": "plan-1",
        "operation": "content.plan.delete",
        "label": "Удалить контент-план",
        "items_count": 8,
    }]
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]


def test_content_plan_delete_preview_rejects_other_scope():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-2", "business_ids": ["b-2"]},
        capability="content.plan.delete",
        input_payload={"plan_id": "plan-1"},
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_reasons"] == ["plan_not_found_or_forbidden"]


def test_service_optimization_uses_common_preview_and_verified_catalog():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="services.optimize",
        input_payload={"business_id": "b-2", "request_id": "intent-1"},
    )

    assert preview["status"] == "preview"
    assert preview["estimated_credits"] == 2
    assert [item["id"] for item in preview["objects"]] == ["s-1", "s-2"]
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]
    assert cursor.action["envelope_json"] == '{"business_id": "b-1", "service_ids": ["s-1", "s-2"], "request_id": "intent-1"}'


def test_finance_delete_preview_is_bound_to_scope_and_transaction():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="finance.transaction.delete",
        input_payload={"business_id": "b-2", "transaction_id": "t-1"},
    )

    assert preview["status"] == "preview"
    assert preview["confirmation_required"] is True
    assert preview["objects"][0]["amount"] == 2900
    assert preview["changes"] == [{
        "object_id": "t-1",
        "operation": "finance.transaction.delete",
        "label": "Удалить финансовую операцию",
    }]


def test_partnership_delete_preview_resolves_only_current_business_workstream():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="partnerships.leads.bulk_delete",
        input_payload={"business_id": "b-2", "lead_ids": ["lead-1", "lead-2"]},
    )

    assert preview["status"] == "preview"
    assert preview["confirmation_required"] is True
    assert preview["is_mass_action"] is True
    assert [item["id"] for item in preview["objects"]] == ["lead-1", "lead-2"]
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]


def test_partnership_delete_preview_rejects_missing_or_foreign_lead():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="partnerships.lead.delete",
        input_payload={"lead_id": "foreign-lead"},
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_reasons"] == ["partnership_leads_not_found_or_forbidden"]


def test_content_plan_generation_preview_is_bound_to_business_and_period():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="content.plan.generate",
        input_payload={"business_id": "b-2", "period_days": 30, "density": "active"},
    )

    assert preview["status"] == "preview"
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]
    assert preview["changes"][0]["label"] == "Собрать контент-план на 30 дней"


def test_content_draft_preview_checks_item_scope():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-2", "business_ids": ["b-2"]},
        capability="content.item.generate",
        input_payload={"item_id": "item-1"},
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_reasons"] == ["content_item_not_found_or_forbidden"]


def test_service_archive_preview_requires_current_active_state():
    cursor = ActionCursor()
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="services.archive",
        input_payload={"service_id": "s-1"},
    )

    assert preview["status"] == "preview"
    assert preview["objects"][0]["name"] == "Стрижка"
    assert preview["changes"][0]["label"] == "Убрать услугу в архив"


def test_diagnostic_retry_requires_platform_scope_and_failed_job():
    cursor = ActionCursor()
    blocked = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
        capability="diagnostics.retry",
        input_payload={"job_id": "q-1"},
    )
    preview = create_mobile_action_preview(
        cursor,
        user_id="u-1",
        scope={"kind": "platform", "id": None, "business_ids": ["b-1"]},
        capability="diagnostics.retry",
        input_payload={"job_id": "q-1"},
    )

    assert blocked["status"] == "blocked"
    assert blocked["blocked_reasons"] == ["platform_scope_required"]
    assert preview["status"] == "preview"
    assert preview["target_businesses"] == [{"id": "b-1", "name": "Первая"}]
    assert preview["changes"][0]["label"] == "Повторить сбор данных карточки"
