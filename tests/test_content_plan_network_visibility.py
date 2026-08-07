from services import content_plan_service


class NetworkPlanCursor:
    def __init__(self):
        self.rows = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.rows = []
        if "from contentplans p" not in normalized:
            return

        local_plan = {
            "id": "local-plan",
            "title": "Старый план точки",
            "scope_type": "network_location",
            "scope_target_id": "location-1",
            "period_days": 30,
            "period_start": "2026-08-06",
            "period_end": "2026-09-04",
            "plan_status": "generated",
            "generation_mode": "manual",
            "created_at": "2026-08-06T16:08:43",
            "updated_at": "2026-08-06T16:08:43",
            "total_items": 13,
            "needs_draft_items": 13,
            "ready_items": 0,
            "news_items": 0,
            "skipped_items": 0,
        }
        network_plan = {
            "id": "network-plan",
            "title": "Новый общий план сети",
            "scope_type": "network_parent",
            "scope_target_id": "network-1",
            "period_days": 30,
            "period_start": "2026-08-07",
            "period_end": "2026-09-05",
            "plan_status": "generated",
            "generation_mode": "manual",
            "created_at": "2026-08-07T08:59:46",
            "updated_at": "2026-08-07T08:59:46",
            "total_items": 13,
            "needs_draft_items": 0,
            "ready_items": 13,
            "news_items": 0,
            "skipped_items": 0,
        }

        # Model the database contract: a network plan is visible from a location
        # only when the query includes plans containing items for that location.
        includes_location_items = (
            "and exists" in normalized
            and "contentplanitems" in normalized
            and "business_id = %s" in normalized
        )
        self.rows = [network_plan, local_plan] if includes_location_items else [local_plan]

    def fetchall(self):
        return list(self.rows)


class NetworkPlanDatabase:
    def __init__(self):
        self.cursor_value = NetworkPlanCursor()
        self.conn = self

    def cursor(self):
        return self.cursor_value

    def close(self):
        return None


def test_network_location_sees_parent_plan_with_items_for_that_location(monkeypatch):
    database = NetworkPlanDatabase()
    monkeypatch.setattr(content_plan_service, "DatabaseManager", lambda: database)
    monkeypatch.setattr(content_plan_service, "ensure_content_plan_tables", lambda _cursor: None)
    monkeypatch.setattr(content_plan_service, "get_business_owner_id", lambda _cursor, _business_id: "owner-1")
    monkeypatch.setattr(content_plan_service, "_resolve_scope_target_meta", lambda *_args: {})

    plans = content_plan_service.list_content_plans("owner-1", "location-1")

    assert [plan["id"] for plan in plans] == ["network-plan", "local-plan"]
    assert plans[0]["ready_count"] == 13
    assert plans[0]["needs_draft_count"] == 0
