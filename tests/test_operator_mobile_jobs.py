from datetime import datetime, timezone

from services.operator_mobile_jobs import load_mobile_job


class JobCursor:
    def __init__(self, action=None, parse_job=None, agent_run=None):
        self.action = action
        self.parse_job = parse_job
        self.agent_run = agent_run
        self.current = None

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        if "from operatoractions" in normalized:
            self.current = self.action
        elif "from parsequeue" in normalized:
            self.current = self.parse_job
        elif "from agent_runs run" in normalized:
            self.current = self.agent_run
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.current


def test_completed_action_returns_stored_result():
    now = datetime.now(timezone.utc)
    cursor = JobCursor(action={
        "id": "action-1",
        "business_id": "business-1",
        "status": "completed",
        "result_json": {"created_count": 2},
        "created_at": now,
        "updated_at": now,
    })

    result = load_mobile_job(
        cursor,
        job_id="action-1",
        user_id="user-1",
        scope={"kind": "business", "business_ids": ["business-1"]},
    )

    assert result["status"] == "completed"
    assert result["progress"] == 100
    assert result["result"] == {"created_count": 2}


def test_parse_job_is_hidden_outside_scope():
    cursor = JobCursor(parse_job={"id": "parse-1", "business_id": "business-2", "status": "running"})

    result = load_mobile_job(
        cursor,
        job_id="parse-1",
        user_id="user-1",
        scope={"kind": "business", "business_ids": ["business-1"]},
    )

    assert result is None


def test_agent_run_progress_uses_real_step_counts():
    now = datetime.now(timezone.utc)
    cursor = JobCursor(agent_run={
        "id": "run-1",
        "business_id": "business-1",
        "status": "running",
        "total_steps": 4,
        "completed_steps": 2,
        "started_at": now,
        "updated_at": now,
    })

    result = load_mobile_job(
        cursor,
        job_id="run-1",
        user_id="user-1",
        scope={"kind": "business", "business_ids": ["business-1"]},
    )

    assert result["status"] == "running"
    assert result["progress"] == 50
