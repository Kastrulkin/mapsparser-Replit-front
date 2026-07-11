from decimal import Decimal

from services.operator_core import operator_capability_catalog, route_operator_message


class ServiceCursor:
    def __init__(self, services=None):
        self.services = list(services or [])
        self.description = []
        self._rows = []
        self._row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
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
            price, service_id, _business_id = params
            selected = next(item for item in self.services if item["id"] == service_id)
            selected["price"] = price
            self._row = {"id": service_id, "name": selected["name"], "price": price}

    def fetchall(self):
        return self._rows

    def fetchone(self):
        value = self._row
        self._row = None
        return value


class AppointmentsOrchestrator:
    def __init__(self):
        self.envelope = None

    def execute(self, envelope, user_data):
        self.envelope = envelope
        return {
            "success": True,
            "status": "completed",
            "action_id": "action-1",
            "result": {"count": 2, "appointments": [{"id": "booking-1"}, {"id": "booking-2"}]},
            "billing": {},
        }


def test_exact_service_price_update_returns_result_link() -> None:
    cursor = ServiceCursor([{"id": "service-1", "name": "Маникюр", "price": Decimal("1000")}])

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Измени цену услуги Маникюр на 1500",
        channel="web",
    )

    assert result["status"] == "completed"
    assert result["capability"] == "services.price.update"
    assert result["service"]["price"] == Decimal("1500")
    assert result["result_ref"]["href"] == "/dashboard/card?tab=services"
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
    assert second["status"] == "completed"
    assert second["service"]["price"] == Decimal("1500")
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


def test_catalog_covers_all_operator_status_classes() -> None:
    catalog = operator_capability_catalog()
    statuses = {item["status"] for item in catalog}
    names = {item["name"] for item in catalog}

    assert {"available", "draft_only", "request_only", "manual", "approval_required", "gap"}.issubset(statuses)
    assert {
        "services.price.update",
        "news.generate",
        "content_plan.generate",
        "finance.manage",
        "appointments.manage",
        "partnerships.manage",
        "settings.manage",
    }.issubset(names)


def test_appointments_read_uses_action_orchestrator_and_returns_link() -> None:
    orchestrator = AppointmentsOrchestrator()

    result, pending = route_operator_message(
        ServiceCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Покажи записи на завтра",
        channel="web",
        action_orchestrator=orchestrator,
    )

    assert result["status"] == "completed"
    assert result["capability"] == "appointments.manage"
    assert result["result_ref"]["href"] == "/dashboard/bookings"
    assert result["appointments"][0]["id"] == "booking-1"
    assert orchestrator.envelope["capability"] == "appointments.read"
    assert orchestrator.envelope["payload"]["from"] == orchestrator.envelope["payload"]["to"]
    assert pending == {}
