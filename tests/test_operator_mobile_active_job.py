from api import operator_api


class ActiveJobCursor:
    def __init__(self, job_id="job-1"):
        self.job_id = job_id
        self.fetch_count = 0
        self.params = None

    def execute(self, _query, params=None):
        self.params = params

    def fetchone(self):
        self.fetch_count += 1
        if self.fetch_count == 1:
            return {"table_ref": "operator_async_jobs"}
        return {"id": self.job_id} if self.job_id else None


def test_mobile_active_job_is_resolved_inside_selected_scope(monkeypatch):
    cursor = ActiveJobCursor()
    captured = {}
    monkeypatch.setattr(
        operator_api,
        "load_operator_async_job",
        lambda _cursor, **kwargs: captured.update(kwargs) or {"id": kwargs["job_id"]},
    )
    scope = {"kind": "business", "id": "business-2", "business_ids": ["business-2"]}

    result = operator_api._mobile_active_job(
        cursor,
        user_id="user-1",
        scope=scope,
        is_superadmin=False,
    )

    assert result == {"id": "job-1"}
    assert cursor.params == ("user-1", False, ["business-2"])
    assert captured["scope"] == scope


def test_mobile_active_job_returns_none_when_scope_has_no_active_job(monkeypatch):
    cursor = ActiveJobCursor(job_id="")
    called = False

    def unexpected_loader(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(operator_api, "load_operator_async_job", unexpected_loader)

    result = operator_api._mobile_active_job(
        cursor,
        user_id="user-1",
        scope={"kind": "business", "id": "business-2", "business_ids": ["business-2"]},
        is_superadmin=False,
    )

    assert result is None
    assert called is False
