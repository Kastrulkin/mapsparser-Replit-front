from services.operator_mobile_modules import list_operator_mobile_module


class ModuleCursor:
    def __init__(self, table_name, rows):
        self.table_name = table_name
        self.source_rows = rows
        self.rows = []
        self.params = ()

    def execute(self, query, params=()):
        normalized = " ".join(str(query).lower().split())
        self.params = params or ()
        if "to_regclass" in normalized:
            self.rows = [{"table_ref": f"public.{self.table_name}" if str(params[0]).endswith(self.table_name) else None}]
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

    assert result["status"] == "read_only"
    assert result["counts"]["total"] == 1
    assert result["items"][0]["title"] == "Стрижка"


def test_hidden_module_does_not_query_or_return_placeholder_data():
    cursor = ModuleCursor("userservices", [])

    result = list_operator_mobile_module(
        cursor,
        module="finance",
        scope={"kind": "business", "id": "b-1", "business_ids": ["b-1"]},
    )

    assert result == {"status": "hidden", "items": []}
