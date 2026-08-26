from decimal import Decimal

from services import operator_core
from services.operator_core import (
    confirm_pending_operator_action,
    operator_capability_catalog,
    reject_pending_operator_action,
    route_operator_message,
)


class ServiceCursor:
    def __init__(self, services=None):
        self.services = list(services or [])
        self.description = []
        self._rows = []
        self._row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if normalized.startswith("select coalesce(nullif(lower(trim(source))"):
            self.description = [("source",), ("cnt",)]
            counts = {}
            for item in self.services:
                source = str(item.get("source") or "localos").strip().lower()
                counts[source] = counts.get(source, 0) + 1
            self._rows = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            return
        if normalized.startswith("select id, category, name, price, description from userservices"):
            self.description = [("id",), ("category",), ("name",), ("price",), ("description",)]
            limit = int((params or ["", 5])[1])
            ordered = sorted(self.services, key=lambda item: (item.get("category") or "~", item["name"]))
            self._rows = [
                (
                    item["id"],
                    item.get("category"),
                    item["name"],
                    item.get("price"),
                    item.get("description"),
                )
                for item in ordered[:limit]
            ]
            return
        if normalized.startswith("select name from businesses"):
            self._row = {"name": "Test Business"}
            return
        if normalized.startswith("select id, name, price from userservices"):
            self.description = [("id",), ("name",), ("price",)]
            pattern = str((params or ["", ""])[1]).strip("%").lower()
            self._rows = [
                (item["id"], item["name"], item["price"])
                for item in self.services
                if pattern in item["name"].lower()
            ]
            return
        if normalized.startswith("update userservices set price"):
            price, service_id, _business_id, previous_price = params
            selected = next(item for item in self.services if item["id"] == service_id)
            if Decimal(str(selected.get("price") or 0)) != Decimal(str(previous_price)):
                self._row = None
                return
            selected["price"] = price
            self._row = {"id": service_id, "name": selected["name"], "price": price}

    def fetchall(self):
        return self._rows

    def fetchone(self):
        value = self._row
        self._row = None
        return value


class FinanceCursor:
    def __init__(self):
        self.description = []
        self.params = None
        self._row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "from financialtransactions" in normalized:
            self.description = [("transactions_count",), ("income",), ("expense",), ("average_ticket",)]
            self.params = params
            self._row = (4, Decimal("12000"), Decimal("3000"), Decimal("3000"))

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


class ConnectionsCursor:
    def __init__(self):
        self.description = []
        self.params = None
        self._rows = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "from externalbusinessaccounts" in normalized:
            self.description = [
                ("id",),
                ("source",),
                ("external_id",),
                ("display_name",),
                ("is_active",),
                ("last_sync_at",),
                ("last_error",),
                ("updated_at",),
            ]
            self.params = params
            self._rows = [("account-1", "yandex", "external-1", "Test", True, None, "", None)]

    def fetchone(self):
        return None

    def fetchall(self):
        return self._rows


class FakeActionOrchestrator:
    def __init__(self):
        self.prepared = []
        self.confirmed = []

    def execute(self, envelope, user_data):
        self.prepared.append((envelope, user_data))
        return {
            "success": True,
            "status": "pending_human",
            "action_id": "ao-1",
            "approval": {"status": "pending_human", "expires_at": "2026-08-25T12:00:00"},
        }

    def resolve_human_decision(self, action_id, decision, user_data, decision_reason=""):
        self.confirmed.append((action_id, decision, user_data, decision_reason))
        if decision == "rejected":
            return {"success": True, "status": "rejected", "action_id": action_id}
        return {
            "success": True,
            "status": "completed",
            "action_id": action_id,
            "result": {
                "result_type": "finance_transaction_created",
                "request_id": "finance-request-1",
                "localos_write_performed": True,
                "provider_write_performed": False,
            },
        }


def test_exact_service_price_update_returns_confirmation_preview() -> None:
    cursor = ServiceCursor([{"id": "service-1", "name": "Маникюр", "price": Decimal("1000")}])

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Измени цену услуги Маникюр на 1500",
        channel="web",
    )

    assert result["status"] == "approval_required"
    assert result["capability"] == "services.price.update"
    assert result["preview"]["previous_price"] == Decimal("1000")
    assert result["preview"]["new_price"] == Decimal("1500")
    assert result["approval"]["envelope"]["service_id"] == "service-1"
    assert result["result_ref"]["href"] == "/dashboard/card?tab=services"
    assert cursor.services[0]["price"] == Decimal("1000")
    assert pending == {}


def test_read_top_three_services_returns_structured_list_and_link() -> None:
    cursor = ServiceCursor(
        [
            {"id": "service-4", "category": "B", "name": "Spa", "price": Decimal("5000")},
            {"id": "service-2", "category": "A", "name": "Pedicure", "price": Decimal("2000")},
            {"id": "service-1", "category": "A", "name": "Manicure", "price": Decimal("1500")},
            {"id": "service-3", "category": "A", "name": "Styling", "price": Decimal("3000")},
        ]
    )

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Выдай мне 3 верхних услуги в этом аккаунте",
        channel="web",
    )

    assert result["status"] == "completed"
    assert result["capability"] == "services.read"
    assert result["count"] == 3
    assert result["business_label"] == "Test Business"
    assert "Test Business" in result["chat_response"]
    assert [item["name"] for item in result["services"]] == ["Manicure", "Pedicure", "Styling"]
    assert result["result_ref"]["href"] == "/dashboard/card?tab=services"
    assert pending == {}


def test_read_services_understands_number_as_word() -> None:
    cursor = ServiceCursor(
        [{"id": f"service-{index}", "category": "A", "name": f"Service {index}"} for index in range(1, 6)]
    )

    result, _ = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Назови три первые услуги",
        channel="telegram",
    )

    assert result["requested_limit"] == 3
    assert len(result["services"]) == 3


def test_services_count_question_is_handled_without_ai_router() -> None:
    cursor = ServiceCursor(
        [
            {"id": "service-1", "category": "A", "name": "Manicure", "price": Decimal("1500"), "source": "yandex_maps"},
            {"id": "service-2", "category": "A", "name": "Pedicure", "price": Decimal("2000"), "source": "2gis"},
        ]
    )

    def ai_router(*_args, **_kwargs):
        raise AssertionError("A services read question must not call the AI router")

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Сколько у нас услуг на картах? На каких?",
        channel="web",
        ai_router_handler=ai_router,
    )

    assert result["status"] == "completed"
    assert result["capability"] == "services.read"
    assert result["count"] == 2
    assert result["source_counts"] == [
        {"source": "2gis", "title": "2ГИС", "count": 1},
        {"source": "yandex_maps", "title": "Яндекс Карты", "count": 1},
    ]
    assert pending == {}


def test_service_price_update_requests_missing_price_and_resumes() -> None:
    cursor = ServiceCursor([{"id": "service-1", "name": "Маникюр", "price": Decimal("1000")}])

    first, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Измени цену услуги Маникюр",
        channel="web",
    )
    second, next_pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="1500",
        channel="web",
        pending_context=pending,
    )

    assert first["status"] == "clarification_required"
    assert "цен" in first["chat_response"].lower()
    assert second["status"] == "approval_required"
    assert second["preview"]["new_price"] == Decimal("1500")
    assert cursor.services[0]["price"] == Decimal("1000")
    assert next_pending == {}


def test_manual_domain_handoff_is_honest_and_linked() -> None:
    result, pending = route_operator_message(
        ServiceCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Проверь настройки подключений",
        channel="web",
    )

    assert result["status"] == "manual_handoff"
    assert result["capability"] == "settings.manage"
    assert result["result_ref"]["href"] == "/dashboard/settings"
    assert pending == {}


def test_tool_loop_can_chain_business_context_and_services_without_crossing_scope() -> None:
    cursor = ServiceCursor(
        [
            {"id": "service-1", "category": "A", "name": "Manicure", "price": Decimal("1500"), "source": "yandex_maps"},
        ]
    )
    decisions = iter(
        [
            {"action": "tool_call", "tool": "services.inventory", "arguments": {}},
            {"action": "final", "message": "В выбранном бизнесе одна услуга на Яндекс Картах."},
        ]
    )
    states = []

    def planner(state):
        states.append(state)
        return next(decisions)

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Сопоставь каталог с предыдущим контекстом",
        channel="web",
        conversation_id="conversation-1",
        conversation_history=[{"role": "user", "content": "Работаем с этой точкой"}],
        tool_planner=planner,
    )

    assert result["status"] == "completed"
    assert result["capability"] == "services.read"
    assert result["tool_calls"] == 1
    assert states[1]["observations"][0]["count"] == 1
    assert states[1]["business_id"] == "business-1"
    assert pending == {}


def test_tool_loop_can_read_finance_inside_selected_business_scope() -> None:
    cursor = FinanceCursor()
    decisions = iter(
        [
            {"action": "tool_call", "tool": "finance.get_summary", "arguments": {"days": 30}},
            {"action": "final", "message": "За 30 дней баланс составил 9 000 ₽."},
        ]
    )

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Покажи финансовую картину за последний месяц",
        channel="web",
        tool_planner=lambda _state: next(decisions),
    )

    assert result["status"] == "completed"
    assert result["capability"] == "finance.read"
    assert cursor.params[0] == "business-1"
    assert (cursor.params[2] - cursor.params[1]).days == 29
    assert result["chat_response"] == "За 30 дней баланс составил 9 000 ₽."
    assert pending == {}


def test_tool_loop_reads_connection_health_without_exposing_credentials() -> None:
    cursor = ConnectionsCursor()
    decisions = iter(
        [
            {"action": "tool_call", "tool": "settings.check_connections", "arguments": {}},
            {"action": "final", "message": "Подключение Яндекса активно."},
        ]
    )
    states = []

    def planner(state):
        states.append(state)
        return next(decisions)

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Проверь подключения выбранной точки",
        channel="web",
        tool_planner=planner,
    )

    observation = states[1]["observations"][0]
    assert result["status"] == "completed"
    assert result["capability"] == "settings.read"
    assert cursor.params == ("business-1",)
    assert observation["accounts"][0]["external_id"] == "external-1"
    assert "auth_data" not in observation["accounts"][0]
    assert "token" not in observation["accounts"][0]
    assert pending == {}


def test_service_update_tools_expose_preview_then_separate_confirmation() -> None:
    states = []

    def planner(state):
        states.append(state)
        return {
            "action": "tool_call",
            "tool": "services.apply_updates",
            "arguments": {"job_id": "job-1", "item_ids": ["item-1"]},
        }

    result, pending = route_operator_message(
        ServiceCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Примени подготовленные изменения",
        channel="web",
        tool_planner=planner,
    )

    names = {tool["name"] for tool in states[0]["tools"]}
    assert {"services.prepare_updates", "services.apply_updates"}.issubset(names)
    assert result["status"] == "approval_required"
    assert result["capability"] == "services.apply_updates"
    assert result["approval"]["envelope"]["job_id"] == "job-1"
    assert pending == {}


def test_finance_tool_creates_action_orchestrator_approval_in_selected_tenant() -> None:
    orchestrator = FakeActionOrchestrator()
    result, pending = route_operator_message(
        ServiceCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Добавь расход 5000 на рекламу",
        channel="web",
        action_orchestrator=orchestrator,
        tool_planner=lambda _state: {
            "action": "tool_call",
            "tool": "finance.prepare_transaction",
            "arguments": {
                "amount": 5000,
                "transaction_type": "expense",
                "category": "Реклама",
            },
        },
    )

    envelope, user_data = orchestrator.prepared[0]
    assert result["status"] == "approval_required"
    assert result["capability"] == "finance.prepare_transaction"
    assert result["approval"]["envelope"]["orchestrator_action_id"] == "ao-1"
    assert envelope["tenant_id"] == "business-1"
    assert envelope["capability"] == "finance.transaction.apply_operator"
    assert envelope["payload"]["rows"][0]["amount"] == 5000
    assert user_data["user_id"] == "user-1"
    assert pending == {}


def test_operator_confirmation_resumes_same_orchestrator_action(monkeypatch) -> None:
    orchestrator = FakeActionOrchestrator()
    stored_results = []
    monkeypatch.setattr(
        operator_core,
        "get_operator_action",
        lambda *_args, **_kwargs: {
            "id": "operator-action-1",
            "status": "pending",
            "capability": "finance.prepare_transaction",
            "envelope_json": {
                "tool": "finance.prepare_transaction",
                "orchestrator_action_id": "ao-1",
                "backend_capability": "finance.transaction.apply_operator",
            },
        },
    )
    monkeypatch.setattr(
        operator_core,
        "finish_operator_action",
        lambda _cursor, *, action_id, result: stored_results.append((action_id, result)),
    )

    result, idempotent = confirm_pending_operator_action(
        ServiceCursor(),
        action_id="operator-action-1",
        business_id="business-1",
        user_id="user-1",
        action_orchestrator=orchestrator,
    )

    assert result["status"] == "completed"
    assert result["request_id"] == "finance-request-1"
    assert result["external_writes_performed"] is False
    assert orchestrator.confirmed[0][0:2] == ("ao-1", "approved")
    assert orchestrator.confirmed[0][2]["user_id"] == "user-1"
    assert stored_results[0][0] == "operator-action-1"
    assert idempotent is False


def test_service_price_changes_only_after_confirmation(monkeypatch) -> None:
    cursor = ServiceCursor([{"id": "service-1", "name": "Маникюр", "price": Decimal("1000")}])
    stored_results = []
    monkeypatch.setattr(
        operator_core,
        "get_operator_action",
        lambda *_args, **_kwargs: {
            "id": "operator-action-1",
            "status": "pending",
            "capability": "services.price.update",
            "envelope_json": {
                "tool": "services.price.update",
                "service_id": "service-1",
                "service_name": "Маникюр",
                "previous_price": "1000",
                "new_price": "1500",
            },
        },
    )
    monkeypatch.setattr(
        operator_core,
        "finish_operator_action",
        lambda _cursor, *, action_id, result: stored_results.append((action_id, result)),
    )

    result, idempotent = confirm_pending_operator_action(
        cursor,
        action_id="operator-action-1",
        business_id="business-1",
        user_id="user-1",
    )

    assert result["status"] == "completed"
    assert cursor.services[0]["price"] == Decimal("1500")
    assert stored_results[0][0] == "operator-action-1"
    assert idempotent is False


def test_service_price_confirmation_blocks_stale_preview(monkeypatch) -> None:
    cursor = ServiceCursor([{"id": "service-1", "name": "Маникюр", "price": Decimal("1200")}])
    monkeypatch.setattr(
        operator_core,
        "get_operator_action",
        lambda *_args, **_kwargs: {
            "id": "operator-action-1",
            "status": "pending",
            "capability": "services.price.update",
            "envelope_json": {
                "service_id": "service-1",
                "service_name": "Маникюр",
                "previous_price": "1000",
                "new_price": "1500",
            },
        },
    )

    result, _ = confirm_pending_operator_action(
        cursor,
        action_id="operator-action-1",
        business_id="business-1",
        user_id="user-1",
    )

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["stale_service_price_preview"]
    assert cursor.services[0]["price"] == Decimal("1200")


def test_operator_rejection_cancels_same_orchestrator_action(monkeypatch) -> None:
    orchestrator = FakeActionOrchestrator()
    stored_results = []
    monkeypatch.setattr(
        operator_core,
        "get_operator_action",
        lambda *_args, **_kwargs: {
            "id": "operator-action-1",
            "status": "pending",
            "capability": "communications.prepare_send",
            "envelope_json": {
                "tool": "communications.prepare_send",
                "orchestrator_action_id": "ao-1",
            },
        },
    )
    monkeypatch.setattr(
        operator_core,
        "reject_operator_action",
        lambda _cursor, *, action_id, result: stored_results.append((action_id, result)),
    )

    result, idempotent = reject_pending_operator_action(
        ServiceCursor(),
        action_id="operator-action-1",
        business_id="business-1",
        user_id="user-1",
        action_orchestrator=orchestrator,
    )

    assert result["status"] == "rejected"
    assert result["external_writes_performed"] is False
    assert orchestrator.confirmed[0][0:2] == ("ao-1", "rejected")
    assert stored_results[0][0] == "operator-action-1"
    assert idempotent is False


def test_catalog_covers_all_operator_status_classes() -> None:
    catalog = operator_capability_catalog()
    statuses = {item["status"] for item in catalog}
    names = {item["name"] for item in catalog}

    assert {"available", "draft_only", "request_only", "manual", "approval_required", "gap"}.issubset(statuses)
    assert {
        "services.price.update",
        "services.prepare_updates",
        "services.apply_updates",
        "news.generate",
        "content_plan.generate",
        "finance.manage",
        "crm.stats",
        "partnerships.manage",
        "settings.manage",
    }.issubset(names)


def test_deepseek_receives_complete_scoped_contract_for_required_tools() -> None:
    states = []
    route_operator_message(
        ServiceCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Сопоставь данные выбранного бизнеса",
        channel="web",
        tool_planner=lambda state: states.append(state) or {"action": "final", "message": "Показал возможности."},
    )

    tools = {tool["name"]: tool for tool in states[0]["tools"]}
    required = {
        "business.get_profile",
        "localos.query",
        "maps.get_latest_snapshot",
        "maps.get_status",
        "maps.refresh",
        "services.prepare_updates",
        "services.apply_updates",
        "reviews.prepare_replies",
        "content.create_news_draft",
        "content.create_plan",
        "finance.get_summary",
        "finance.prepare_transaction",
        "partnerships.search",
        "partnerships.prepare_message",
        "agents.list",
        "settings.check_connections",
    }
    assert required.issubset(tools)
    assert {"services.list", "reviews.list_unanswered", "content.list_items"}.isdisjoint(tools)
    for name in required:
        tool = tools[name]
        assert tool["input_schema"]["type"] == "object"
        assert tool["output_schema"]["type"] == "object"
        assert tool["scope"] == {"type": "business", "business_id": "business-1"}
        assert tool["required_permission"] == "business.access"
        assert tool["risk_class"]
        assert tool["timeout_seconds"] > 0
        assert isinstance(tool["approval_required"], bool)


def test_crm_queries_open_aggregated_progress_instead_of_booking_management() -> None:
    result, pending = route_operator_message(
        ServiceCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Покажи статистику записей и загрузки",
        channel="web",
    )

    assert result["status"] == "manual_handoff"
    assert result["capability"] == "crm.stats"
    assert result["result_ref"]["href"] == "/dashboard/progress"
    assert result["result_ref"]["label"] == "Открыть Прогресс"
    assert "не управляет записями" in result["chat_response"]
    assert pending == {}
