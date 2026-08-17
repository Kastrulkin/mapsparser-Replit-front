from datetime import datetime, timezone

from services import web_tracking_maintenance


class Cursor:
    def __init__(self):
        self.queries = []
        self.current = None
        self.rowcount = 0

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.queries.append((normalized, params))
        if "SELECT COUNT(*) AS count" in normalized:
            self.current = {"count": 12}
            self.rowcount = 1
        elif normalized.startswith("WITH ") and "DELETE FROM web_events" in normalized:
            self.rowcount = 5
        elif normalized.startswith("WITH ") and "DELETE FROM web_sessions" in normalized:
            self.rowcount = 2
        elif normalized.startswith("WITH ") and "DELETE FROM web_visitors" in normalized:
            self.rowcount = 1
        else:
            self.current = None
            self.rowcount = 1

    def fetchone(self):
        return self.current


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def test_maintenance_defaults_to_non_destructive_dry_run():
    cursor = Cursor()

    result = web_tracking_maintenance.run_web_tracking_maintenance(cursor, dry_run=True, now=NOW)

    assert result["dry_run"] is True
    assert result["eligible_events"] == 12
    assert result["deleted_events"] == 0
    assert not any("DELETE FROM web_events" in query for query, _params in cursor.queries)


def test_maintenance_aggregates_and_deletes_in_bounded_batches(monkeypatch):
    cursor = Cursor()
    monkeypatch.setattr(web_tracking_maintenance, "aggregate_web_tracking_day", lambda _cursor, _date: 7)

    result = web_tracking_maintenance.run_web_tracking_maintenance(
        cursor,
        dry_run=False,
        batch_size=500,
        now=NOW,
    )

    assert result["metrics_rows"] == 7
    assert result["deleted_events"] == 5
    assert result["deleted_metrics"] == 1
    assert result["deleted_sessions"] == 2
    assert result["deleted_visitors"] == 1
    destructive = [(query, params) for query, params in cursor.queries if query.startswith("WITH ") and "DELETE FROM" in query]
    assert len(destructive) == 4
    assert all(params == (500,) for _query, params in destructive)
    assert "checksum.raw_events = m.events" in "\n".join(query for query, _params in cursor.queries)


def test_daily_aggregation_has_total_page_source_and_event_dimensions():
    cursor = Cursor()

    rows = web_tracking_maintenance.aggregate_web_tracking_day(cursor, NOW.date())

    joined = "\n".join(query for query, _params in cursor.queries)
    assert rows == 5
    assert "'total'" in joined
    assert "'page'" in joined
    assert "'source'" in joined
    assert "'event'" in joined
    assert "'action'" in joined
    assert "raw_events" in joined
    assert "aggregate_events" in joined


def test_maintenance_persists_checksum_failure_without_partial_deletes(monkeypatch):
    cursor = Cursor()

    def fail_aggregation(_cursor, _date):
        raise web_tracking_maintenance.WebTrackingAggregationError("daily_event_checksum_mismatch")

    monkeypatch.setattr(web_tracking_maintenance, "aggregate_web_tracking_day", fail_aggregation)

    result = web_tracking_maintenance.run_web_tracking_maintenance(cursor, dry_run=False, now=NOW)

    assert result["status"] == "failed"
    assert result["error_code"] == "daily_event_checksum_mismatch"
    joined = "\n".join(query for query, _params in cursor.queries)
    assert "ROLLBACK TO SAVEPOINT web_tracking_maintenance_work" in joined
    assert "SET status = 'failed'" in joined
    assert "DELETE FROM web_events" not in joined
