from datetime import date

from services.operator_mobile_modules import list_operator_mobile_module


class ModuleCursor:
    def __init__(self, table_name, rows, existing_tables=None):
        self.table_name = table_name
        self.existing_tables = set(existing_tables or [table_name])
        self.source_rows = rows
        self.rows = []
        self.params = ()
        self.query = ""

    def execute(self, query, params=()):
        normalized = " ".join(str(query).lower().split())
        self.query = normalized
        self.params = params or ()
        if "to_regclass" in normalized:
            requested_table = str(params[0]).split(".")[-1]
            self.rows = [{"table_ref": f"public.{requested_table}" if requested_table in self.existing_tables else None}]
        else:
            platform, business_ids = params
            allowed = set(business_ids)
            self.rows = [item for item in self.source_rows if platform or item.get("business_id") in allowed]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_services_module_only_returns_scope_businesses():
    cursor = ModuleCursor("userservices", [
        {"id": "s-1", "business_id": "b-1", "title": "Стрижка", "status": "active"},
        {"id": "s-2", "business_id": "b-2", "title": "Укладка", "status": "active"},
    ])

    result = list_operator_mobile_module(
        cursor,
        module="services",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
    )

    assert result["status"] == "available"
    assert result["counts"]["total"] == 1
    assert result["items"][0]["title"] == "Стрижка"
    assert result["available_actions"][0]["key"] == "services.update"


def test_unknown_module_does_not_query_or_return_placeholder_data():
    cursor = ModuleCursor("userservices", [])

    result = list_operator_mobile_module(
        cursor,
        module="unknown",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
    )

    assert result == {"status": "hidden", "items": []}


def test_finance_module_is_scope_filtered_and_real():
    cursor = ModuleCursor("financialtransactions", [
        {"id": "f-1", "business_id": "b-1", "title": "Поступление", "amount": 1500},
        {"id": "f-2", "business_id": "b-2", "title": "Расход", "amount": 500},
    ])

    result = list_operator_mobile_module(
        cursor,
        module="finance",
        scope={"kind": "network", "id": "n-1", "business_ids": ["b-1"]},
    )

    assert result["status"] == "available"
    assert result["counts"]["total"] == 1
    assert result["items"][0]["amount"] == 1500
    assert result["available_actions"] == [{"key": "finance.sales_import", "label": "Загрузить продажи"}]


class AnalyticsCursor:
    def __init__(self):
        self.rows = []
        self.query = ""

    def execute(self, query, params=()):
        normalized = " ".join(str(query).lower().split())
        self.query = normalized
        if "to_regclass" in normalized:
            self.rows = [{"table_ref": "public.financialtransactions"}]
        elif "generate_series" in normalized:
            self.rows = [
                {"day": date(2026, 7, 23), "revenue": 0, "orders_count": 0},
                {"day": date(2026, 7, 24), "revenue": 1000, "orders_count": 1},
            ]
        else:
            self.rows = [{
                "revenue": 1000,
                "orders_count": 1,
                "average_ticket": 1000,
                "previous_revenue": 500,
                "previous_orders_count": 1,
            }]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_analytics_module_returns_real_period_metrics_and_daily_series():
    result = list_operator_mobile_module(
        AnalyticsCursor(),
        module="analytics",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
    )

    assert result["status"] == "read_only"
    assert result["items"][0]["metric_key"] == "revenue"
    assert result["items"][0]["amount"] == 1000
    assert result["items"][0]["previous_amount"] == 500
    assert result["items"][-1] == {
        "id": "analytics-day-2026-07-24",
        "kind": "analytics_day",
        "day": "2026-07-24",
        "amount": 1000.0,
        "orders_count": 1,
    }


def test_content_module_only_loads_the_latest_plan_for_each_business():
    cursor = ModuleCursor(
        "contentplanitems",
        [{"id": "item-1", "business_id": "b-1", "title": "Тема", "plan_id": "plan-new", "scheduled_for": date(2026, 7, 24)}],
        existing_tables={"contentplans", "contentplanitems"},
    )

    result = list_operator_mobile_module(
        cursor,
        module="content",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
    )

    assert result["counts"]["total"] == 1
    assert result["items"][0]["scheduled_for"] == "2026-07-24"
    assert "row_number() over" in cursor.query
    assert "p.plan_rank = 1" in cursor.query
