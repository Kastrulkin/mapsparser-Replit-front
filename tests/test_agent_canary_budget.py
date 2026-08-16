from datetime import datetime, timezone

from services.agent_canary_budget import evaluate_agent_canary_budget


def _blueprint() -> dict:
    return {
        "id": "blueprint-1",
        "metadata_json": {
            "certification_canary": {
                "schema": "localos_agent_canary_v1",
                "status": "active",
                "key": "compiled-ai-canary-20260817",
                "starts_at": "2026-08-16T21:00:00Z",
                "ends_at": "2026-08-23T20:59:59Z",
                "max_reserved_credits": 64,
            }
        },
    }


class Cursor:
    def __init__(self, reserved_credits: int = 0):
        self.reserved_credits = reserved_credits
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return {"reserved_credits": self.reserved_credits}


def test_canary_waits_for_approved_start_without_querying_spend():
    cursor = Cursor()
    result = evaluate_agent_canary_budget(
        cursor,
        blueprint=_blueprint(),
        requested_credits=2,
        now=datetime(2026, 8, 16, 20, 59, tzinfo=timezone.utc),
    )

    assert result["allowed"] is False
    assert result["reason"] == "not_started"
    assert cursor.queries == []


def test_canary_allows_planned_run_within_hard_credit_limit():
    cursor = Cursor(reserved_credits=58)
    result = evaluate_agent_canary_budget(
        cursor,
        blueprint=_blueprint(),
        requested_credits=2,
        now=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc),
    )

    assert result["allowed"] is True
    assert result["projected_reserved_credits"] == 60
    assert result["max_reserved_credits"] == 64
    assert "pg_advisory_xact_lock" in cursor.queries[0][0]


def test_canary_blocks_before_reservation_would_exceed_limit():
    cursor = Cursor(reserved_credits=64)
    result = evaluate_agent_canary_budget(
        cursor,
        blueprint=_blueprint(),
        requested_credits=2,
        now=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc),
    )

    assert result["allowed"] is False
    assert result["reason"] == "budget_exhausted"
    assert result["projected_reserved_credits"] == 66


def test_canary_blocks_after_approved_window():
    cursor = Cursor()
    result = evaluate_agent_canary_budget(
        cursor,
        blueprint=_blueprint(),
        requested_credits=2,
        now=datetime(2026, 8, 23, 21, 0, tzinfo=timezone.utc),
    )

    assert result["allowed"] is False
    assert result["reason"] == "ended"
    assert cursor.queries == []


def test_due_scheduler_stops_canary_before_approved_start(monkeypatch):
    from services import agent_trigger_runtime

    blueprint = _blueprint()
    blueprint.update({"business_id": "business-1", "status": "active"})
    monkeypatch.setattr(agent_trigger_runtime, "_ensure_trigger_event_table", lambda cursor: None)
    monkeypatch.setattr(
        agent_trigger_runtime,
        "_load_scheduled_blueprints",
        lambda cursor, blueprint_limit: [blueprint],
    )
    monkeypatch.setattr(
        agent_trigger_runtime,
        "_resolve_active_version",
        lambda cursor, item: (_ for _ in ()).throw(AssertionError("version must not load before canary start")),
    )

    result = agent_trigger_runtime.dispatch_due_scheduled_agent_blueprints(
        Cursor(),
        now=datetime(2026, 8, 16, 20, 59, tzinfo=timezone.utc),
    )

    assert result["dispatched_count"] == 0
    assert result["skipped"] == [{
        "blueprint_id": "blueprint-1",
        "business_id": "business-1",
        "reason": "canary_not_started",
    }]
