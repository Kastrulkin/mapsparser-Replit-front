from database_manager import DatabaseManager
from services.operator_async_jobs import (
    claim_next_operator_async_job,
    recover_stale_operator_async_jobs,
    update_operator_async_job,
)


class _Connection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


def test_database_manager_context_rolls_back_on_error_without_legacy_commit():
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.conn = _Connection()
    manager._closed = False

    manager.__exit__(RuntimeError, RuntimeError("boom"), None)

    assert manager.conn.rollbacks == 1
    assert manager.conn.commits == 0
    assert manager.conn.closed == 1


class _JobCursor:
    def __init__(self):
        self.queries = []
        self.params = []
        self.rowcount = 1
        self._rows = [
            {"id": "job-1", "payload_json": "{}"},
            {"id": "job-1", "payload_json": "{}", "lease_token": "lease-1"},
        ]

    def execute(self, query, params=()):
        self.queries.append(" ".join(str(query).lower().split()))
        self.params.append(params)

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


def test_operator_job_claim_assigns_lease_and_fenced_completion_checks_it():
    cursor = _JobCursor()

    claimed = claim_next_operator_async_job(cursor)
    updated = update_operator_async_job(
        cursor,
        job_id="job-1",
        status="completed",
        progress=100,
        stage="готово",
        lease_token="lease-1",
    )

    assert claimed["id"] == "job-1"
    assert "lease_token = %s" in cursor.queries[1]
    assert cursor.params[1][1] == "job-1"
    assert "lease_token = case when %s then null else lease_token end" in cursor.queries[2]
    assert "lease_token = %s" in cursor.queries[2]
    assert updated is True


def test_operator_stale_recovery_skips_a_live_locked_job():
    cursor = _JobCursor()

    recovered = recover_stale_operator_async_jobs(cursor)

    assert recovered == 1
    assert "for update skip locked" in cursor.queries[0]
    assert "lease_token = null" in cursor.queries[0]
    assert "worker heartbeat expired; retry scheduled" in cursor.queries[0]


def test_dedicated_worker_roles_do_not_run_each_others_loops(monkeypatch):
    import worker

    monkeypatch.setenv("WORKER_ROLE", "agent")
    assert worker._worker_role_enabled("agent") is True
    assert worker._worker_role_enabled("parser") is False
    assert worker._worker_role_enabled("dispatcher") is False

    monkeypatch.setenv("WORKER_ROLE", "all")
    assert all(worker._worker_role_enabled(role) for role in ("parser", "agent", "operator", "dispatcher", "maintenance"))
