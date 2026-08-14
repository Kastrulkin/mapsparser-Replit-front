import pytest


TEMPLATE_KEYS = (
    "daily_owner_digest",
    "negative_review_reply",
    "service_seo_cleanup",
    "card_posts_from_signals",
    "tomorrow_bookings_check",
    "google_sheets_business_result",
)

BUSINESSES = (
    {"business_key": "riderra", "business_id": "riderra-id", "business_name": "Riderra (Tallinn)", "owner_id": "owner-1", "available_credits": 145},
    {"business_key": "veselaya", "business_id": "veselaya-id", "business_name": "Весёлая расчёска", "owner_id": "owner-1", "available_credits": 145},
    {"business_key": "organika", "business_id": "organika-id", "business_name": "Органика", "owner_id": "owner-2", "available_credits": 24},
)


def test_pilot_plan_distributes_required_runs_and_72_credit_limit_evenly():
    from services.agent_template_pilot_plan import build_agent_template_pilot_plan

    plan = build_agent_template_pilot_plan(TEMPLATE_KEYS, BUSINESSES)

    assert plan["status"] == "ready_for_authorization"
    assert plan["execution_authorized"] is False
    assert plan["totals"] == {
        "templates": 6,
        "preview_runs": 60,
        "production_runs": 30,
        "base_credit_limit": 60,
        "buffer_credit_limit": 12,
        "credit_limit": 72,
        "top_up_required": 0,
    }
    assert [item["preview_runs"] for item in plan["businesses"]] == [20, 20, 20]
    assert [item["production_runs"] for item in plan["businesses"]] == [10, 10, 10]
    assert [item["credit_limit"] for item in plan["businesses"]] == [24, 24, 24]
    assert plan["funding_groups"] == [
        {
            "owner_id": "owner-1",
            "business_keys": ["riderra", "veselaya"],
            "available_credits": 145,
            "planned_credit_limit": 48,
            "top_up_required": 0,
            "status": "ready",
        },
        {
            "owner_id": "owner-2",
            "business_keys": ["organika"],
            "available_credits": 24,
            "planned_credit_limit": 24,
            "top_up_required": 0,
            "status": "ready",
        },
    ]

    for template in plan["templates"]:
        assert template["preview_runs"] == 10
        assert template["production_runs"] == 5
        assert template["max_credits"] == 10
        assert all(item["production_runs"] >= 1 for item in template["allocations"])
        assert all(item["genuine_feedback_required"] is True for item in template["allocations"])


def test_pilot_plan_waits_for_missing_verified_business_id():
    from services.agent_template_pilot_plan import build_agent_template_pilot_plan

    businesses = [dict(item) for item in BUSINESSES]
    businesses[0]["business_id"] = ""

    plan = build_agent_template_pilot_plan(TEMPLATE_KEYS, businesses)

    assert plan["status"] == "awaiting_business_ids"
    assert plan["missing_business_ids"] == ["riderra"]


def test_pilot_plan_reports_owner_level_top_up_without_double_counting_shared_balance():
    from services.agent_template_pilot_plan import build_agent_template_pilot_plan

    businesses = [dict(item) for item in BUSINESSES]
    businesses[2]["available_credits"] = 0

    plan = build_agent_template_pilot_plan(TEMPLATE_KEYS, businesses)

    assert plan["status"] == "funding_required"
    assert plan["totals"]["top_up_required"] == 24
    assert plan["funding_groups"][0]["planned_credit_limit"] == 48
    assert plan["funding_groups"][0]["top_up_required"] == 0
    assert plan["funding_groups"][1]["top_up_required"] == 24


@pytest.mark.parametrize(
    "businesses,error",
    [
        (BUSINESSES[:2], "exactly_3_pilot_businesses_required"),
        (BUSINESSES + (BUSINESSES[0],), "exactly_3_pilot_businesses_required"),
        ((BUSINESSES[0], BUSINESSES[0], BUSINESSES[2]), "duplicate_pilot_business_key"),
    ],
)
def test_pilot_plan_rejects_invalid_cohort(businesses, error):
    from services.agent_template_pilot_plan import build_agent_template_pilot_plan

    with pytest.raises(ValueError, match=error):
        build_agent_template_pilot_plan(TEMPLATE_KEYS, businesses)


def test_pilot_plan_rejects_partial_first_wave():
    from services.agent_template_pilot_plan import build_agent_template_pilot_plan

    with pytest.raises(ValueError, match="exactly_6_first_wave_templates_required"):
        build_agent_template_pilot_plan(TEMPLATE_KEYS[:5], BUSINESSES)


def test_pilot_runner_pauses_only_active_scheduled_blueprints_after_production():
    from scripts.run_compiled_ai_template_pilot import _pause_scheduled_pilot_blueprints

    class Cursor:
        def __init__(self):
            self.query = ""
            self.params = ()

        def execute(self, query, params=None):
            self.query = " ".join(query.split()).lower()
            self.params = params or ()

        def fetchall(self):
            return [{"id": "scheduled-1"}, {"id": "scheduled-2"}]

    class Connection:
        def __init__(self, cursor):
            self._cursor = cursor
            self.commits = 0

        def cursor(self):
            return self._cursor

        def commit(self):
            self.commits += 1

    class Database:
        def __init__(self):
            self.cursor = Cursor()
            self.conn = Connection(self.cursor)

    db = Database()
    result = _pause_scheduled_pilot_blueprints(db, ["scheduled-2", "manual-1", "scheduled-1", ""])

    assert result == {"paused_count": 2, "blueprint_ids": ["scheduled-1", "scheduled-2"]}
    assert db.cursor.params == (["manual-1", "scheduled-1", "scheduled-2"],)
    assert "blueprint.status = 'active'" in db.cursor.query
    assert "version.trigger like 'schedule.%%'" in db.cursor.query
    assert "set status = 'paused'" in db.cursor.query
    assert db.conn.commits == 1
