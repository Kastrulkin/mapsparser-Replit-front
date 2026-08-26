from __future__ import annotations

from decimal import Decimal

from core.action_policy import evaluate_risk_policy
from services import agent_capability_handlers, operator_core
from services.operator_core import confirm_pending_operator_action, route_operator_message
from services.operator_finance_ingest import build_finance_sales_preview, normalize_finance_sales


class PreviewCursor:
    def __init__(self, duplicate_keys=None):
        self.duplicate_keys = set(duplicate_keys or [])
        self.rows = []
        self.params = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.params = params
        if "select duplicate_key from financialtransactions" in normalized:
            requested = set((params or (None, []))[1])
            self.rows = [{"duplicate_key": key} for key in requested & self.duplicate_keys]
            return None
        raise AssertionError(f"Unhandled preview SQL: {query}")

    def fetchall(self):
        return list(self.rows)


class FakeActionOrchestrator:
    def __init__(self):
        self.prepared = []

    def execute(self, envelope, user_data):
        self.prepared.append((envelope, user_data))
        return {
            "success": True,
            "status": "pending_human",
            "action_id": "finance-bulk-action-1",
            "approval": {"status": "pending_human"},
        }


def _arguments():
    return {
        "transactions": [
            {
                "transaction_date": "2026-08-26",
                "amount": 2500,
                "title": "Стрижка",
                "sale_type": "service",
            },
            {
                "transaction_date": "2026-08-26",
                "amount": 7500,
                "title": "Окрашивание",
                "sale_type": "upsell",
            },
        ]
    }


def test_finance_sales_preview_normalizes_totals_and_keeps_tenant_out_of_arguments():
    result = build_finance_sales_preview(
        PreviewCursor(),
        business_id="business-1",
        message="Добавь сегодняшние продажи",
        arguments={**_arguments(), "business_id": "attacker-business"},
    )

    assert result["status"] == "ready"
    assert result["import_count"] == 2
    assert result["total_amount"] == "10000.00"
    assert "10000.00" in result["chat_response"]
    assert result["result_ref"]["href"] == "/dashboard/finance"
    assert all("business_id" not in row for row in result["rows"])


def test_finance_sales_preview_asks_one_question_when_date_is_missing():
    result = build_finance_sales_preview(
        PreviewCursor(),
        business_id="business-1",
        message="Стрижка 2500",
        arguments={"transactions": [{"amount": 2500, "title": "Стрижка"}]},
    )

    assert result["status"] == "clarification_required"
    assert "нет даты" in result["chat_response"]
    assert result["result_ref"]["href"] == "/dashboard/finance"
    assert result["external_writes_performed"] is False


def test_finance_sales_preview_does_not_offer_reimport_for_same_source():
    normalized = normalize_finance_sales(
        _arguments(),
        business_id="business-1",
        message="Продажи за сегодня",
    )
    keys = [row["duplicate_key"] for row in normalized["rows"]]

    result = build_finance_sales_preview(
        PreviewCursor(keys),
        business_id="business-1",
        message="Продажи за сегодня",
        arguments=_arguments(),
    )

    assert result["status"] == "completed"
    assert result["duplicate_count"] == 2
    assert "уже есть" in result["chat_response"]


def test_operator_compiles_sales_list_into_one_approval_without_writing():
    orchestrator = FakeActionOrchestrator()
    result, pending = route_operator_message(
        PreviewCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Добавь продажи за сегодня: стрижка 2500, окрашивание 7500",
        channel="web",
        action_orchestrator=orchestrator,
        tool_planner=lambda _state: {
            "action": "tool_call",
            "tool": "finance.ingest_sales",
            "arguments": _arguments(),
        },
    )

    envelope, user_data = orchestrator.prepared[0]
    assert result["status"] == "approval_required"
    assert result["capability"] == "finance.sales_import"
    assert result["finance_preview"]["total_amount"] == "10000.00"
    assert result["result_ref"]["href"] == "/dashboard/finance"
    assert envelope["tenant_id"] == "business-1"
    assert envelope["capability"] == "finance.sales_import.apply_operator"
    assert len(envelope["payload"]["rows"]) == 2
    assert user_data["user_id"] == "user-1"
    assert pending == {}


def test_operator_returns_finance_fallback_when_duplicate_check_is_unavailable():
    class BrokenCursor:
        def execute(self, _query, _params=None):
            raise RuntimeError("schema unavailable")

    result, _pending = route_operator_message(
        BrokenCursor(),
        business_id="business-1",
        user_id="user-1",
        message="Добавь продажи за сегодня",
        channel="web",
        tool_planner=lambda _state: {
            "action": "tool_call",
            "tool": "finance.ingest_sales",
            "arguments": _arguments(),
        },
    )

    assert result["status"] == "manual_handoff"
    assert result["result_ref"]["href"] == "/dashboard/finance"
    assert result["planner_steps"] == 1


def test_bulk_finance_apply_always_requires_human_review():
    decision = evaluate_risk_policy("finance.sales_import.apply_operator", {"rows": _arguments()["transactions"]}, {})

    assert decision["ok"] is True
    assert decision["requires_human"] is True


def test_failed_finance_confirmation_returns_manual_import_link(monkeypatch):
    class FailedOrchestrator:
        def resolve_human_decision(self, *_args, **_kwargs):
            return {"success": False, "error_code": "finance_apply_failed"}

    monkeypatch.setattr(
        operator_core,
        "get_operator_action",
        lambda *_args, **_kwargs: {
            "id": "operator-action-1",
            "status": "pending",
            "capability": "finance.sales_import",
            "envelope_json": {"orchestrator_action_id": "finance-bulk-action-1"},
        },
    )

    result, idempotent = confirm_pending_operator_action(
        object(),
        action_id="operator-action-1",
        business_id="business-1",
        user_id="user-1",
        action_orchestrator=FailedOrchestrator(),
    )

    assert result["status"] == "blocked"
    assert result["result_ref"]["href"] == "/dashboard/finance"
    assert "Финансы" in result["chat_response"]
    assert idempotent is False


def test_bulk_finance_apply_is_idempotent_and_returns_today_summary(monkeypatch):
    class FinanceCursor:
        def __init__(self):
            self.columns = {
                "id", "business_id", "user_id", "amount", "transaction_type", "transaction_date",
                "duplicate_key", "source_hash", "import_batch_id", "description", "notes", "source", "services",
            }
            self.last_result = None
            self.last_results = []
            self.inserted = {}
            self.description = []

        def execute(self, query, params=None):
            normalized = " ".join(str(query).split()).lower()
            values = tuple(params or ())
            if "from information_schema.columns" in normalized:
                self.last_results = [(column,) for column in sorted(self.columns)]
                return None
            if normalized.startswith("insert into financialtransactions"):
                duplicate_key = str(values[5])
                if duplicate_key in self.inserted:
                    self.last_result = None
                else:
                    self.inserted[duplicate_key] = values
                    self.last_result = (values[0],)
                return None
            if "select count(*) as transactions_count" in normalized:
                amounts = [Decimal(str(item[2])) for item in self.inserted.values()]
                income = sum(amounts, Decimal("0"))
                average = income / len(amounts) if amounts else Decimal("0")
                self.last_result = {
                    "transactions_count": len(amounts),
                    "income": income,
                    "average_ticket": average,
                }
                return None
            raise AssertionError(f"Unhandled apply SQL: {query}")

        def fetchall(self):
            return list(self.last_results)

        def fetchone(self):
            return self.last_result

    class FinanceDatabase:
        def __init__(self):
            self.cursor_instance = FinanceCursor()
            self.conn = self
            self.commits = 0

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.commits += 1

        def rollback(self):
            raise AssertionError("valid sales import must not roll back")

        def close(self):
            return None

    db = FinanceDatabase()
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", lambda: db)
    handler = agent_capability_handlers.build_capability_handlers()["finance.sales_import.apply_operator"]
    normalized = normalize_finance_sales(
        _arguments(),
        business_id="business-1",
        message="Продажи за сегодня",
    )
    envelope = {
        "tenant_id": "business-1",
        "action_id": "approved-bulk-action",
        "actor": {"id": "user-1"},
        "capability": "finance.sales_import.apply_operator",
        "payload": {"rows": normalized["rows"], "import_batch_id": normalized["import_batch_id"]},
    }

    first = handler(envelope, {"user_id": "user-1"})["result"]
    second = handler(envelope, {"user_id": "user-1"})["result"]

    assert first["status"] == "finance_sales_import_completed"
    assert first["created_count"] == 2
    assert first["summary"]["income"] == Decimal("10000.00")
    assert first["localos_write_performed"] is True
    assert second["created_count"] == 0
    assert second["duplicate_count"] == 2
    assert len(db.cursor_instance.inserted) == 2
