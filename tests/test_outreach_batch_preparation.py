from datetime import datetime, timezone
from pathlib import Path

from services import outreach_batch_preparation_service


class BatchCursor:
    def __init__(self):
        self.executed = []
        self.rowcount = 0

    def execute(self, query, params=None):
        self.executed.append((str(query), params))
        self.rowcount = 1 if "UPDATE outreach_campaigns" in str(query) else 0


class BatchConnection:
    def __init__(self):
        self.cursor_instance = BatchCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _candidate(**overrides):
    row = {
        "id": "workstream-1",
        "lead_id": "lead-1",
        "lead_name": "Компания",
        "workstream_type": "localos_sales",
        "client_business_id": None,
        "lifecycle_status": "active",
        "workstream_status": "in_progress",
        "pipeline_status": "in_progress",
        "lead_status": "in_progress",
        "workstream_last_contact_at": None,
        "lead_last_contact_at": None,
        "latest_campaign_id": None,
        "latest_campaign_status": None,
        "latest_campaign_stop_reason": None,
        "latest_campaign_last_reply_at": None,
        "has_blocking_campaign": False,
        "suppressed": False,
    }
    row.update(overrides)
    return row


def test_sequence_selects_localosgo_without_enabling_delivery() -> None:
    sequence = outreach_batch_preparation_service._sequence("sender-localosgo")
    assert [item["channel"] for item in sequence] == ["telegram", "email", "next", "next"]
    assert [item["day_offset"] for item in sequence] == [0, 3, 7, 12]
    assert sequence[1]["sender_account_id"] == "sender-localosgo"


def test_terminal_reply_suppression_and_cooldown_are_blocking() -> None:
    now = datetime.now(timezone.utc)
    assert outreach_batch_preparation_service._blocked_reason(
        _candidate(pipeline_status="replied"), now
    ) == "terminal_state"
    assert outreach_batch_preparation_service._blocked_reason(
        _candidate(suppressed=True), now
    ) == "suppressed"
    assert outreach_batch_preparation_service._blocked_reason(
        _candidate(latest_campaign_last_reply_at=now), now
    ) == "recipient_replied"
    assert outreach_batch_preparation_service._blocked_reason(
        _candidate(lead_last_contact_at=now), now
    ) == "contact_cooldown"


def test_preparation_prerequisite_requires_contacts_and_evidence() -> None:
    assert outreach_batch_preparation_service._preparation_prerequisite(
        _candidate(enrichment_status="collecting", contact_count=1, evidence_count=1),
        "localos",
    ) == "enrichment_in_progress"
    assert outreach_batch_preparation_service._preparation_prerequisite(
        _candidate(enrichment_status="needs_contact", contact_count=0, evidence_count=1),
        "localos",
    ) == "needs_contact"
    assert outreach_batch_preparation_service._preparation_prerequisite(
        _candidate(enrichment_status="needs_evidence", contact_count=1, evidence_count=0),
        "localos",
    ) == "needs_evidence"
    assert outreach_batch_preparation_service._preparation_prerequisite(
        _candidate(enrichment_status="ready", contact_count=1, evidence_count=1),
        "localos",
    ) is None
    assert outreach_batch_preparation_service._preparation_prerequisite(
        _candidate(
            enrichment_status="ready",
            contact_count=1,
            evidence_count=1,
            message_readiness_json={
                "source": "outreach_batch_preparation",
                "contract": outreach_batch_preparation_service._preparation_contract("localos"),
                "code": "needs_revision",
            },
        ),
        "localos",
    ) is None


def test_prepare_is_dry_run_by_default_and_never_calls_generation(monkeypatch) -> None:
    connection = BatchConnection()
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "get_db_connection",
        lambda: connection,
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_actor_id",
        lambda cursor, requested: "actor-1",
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_platform_email_sender",
        lambda cursor: "sender-localosgo",
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_candidates",
        lambda cursor, **kwargs: [_candidate(contact_count=1, evidence_count=1)],
    )

    def forbidden_preview(*args, **kwargs):
        raise AssertionError("dry-run must not generate a preview")

    monkeypatch.setattr(outreach_batch_preparation_service, "build_preview", forbidden_preview)
    result = outreach_batch_preparation_service.prepare_campaigns(
        workstream_type="localos_sales",
        execute=False,
    )

    assert result["created"] == 0
    assert result["preview_states"] == {"would_preview": 1}
    assert connection.commits == 0


def test_prepare_creates_draft_then_supersedes_stale_draft(monkeypatch) -> None:
    initial_connection = BatchConnection()
    item_connection = BatchConnection()
    connections = iter([initial_connection, item_connection])
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "get_db_connection",
        lambda: next(connections),
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_actor_id",
        lambda cursor, requested: "actor-1",
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_platform_email_sender",
        lambda cursor: "sender-localosgo",
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_candidates",
        lambda cursor, **kwargs: [
            _candidate(latest_campaign_id="campaign-old", latest_campaign_status="draft")
            | {"contact_count": 1, "evidence_count": 1}
        ],
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_campaign_is_current",
        lambda cursor, campaign_id, sender_mode: False,
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "build_preview",
        lambda *args, **kwargs: {"status": "needs_channel_setup"},
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "persist_preview",
        lambda cursor, preview, user_id: {
            "id": "campaign-new",
            "version": 2,
            "status": "draft",
        },
    )
    events = []
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "record_campaign_event",
        lambda cursor, campaign_id, event_type, **kwargs: events.append(
            (campaign_id, event_type, kwargs)
        ),
    )

    result = outreach_batch_preparation_service.prepare_campaigns(
        workstream_type="localos_sales",
        execute=True,
    )

    assert result["created"] == 1
    assert result["superseded"] == 1
    assert result["campaigns"][0]["campaign_id"] == "campaign-new"
    assert item_connection.commits == 1
    assert events[0][0:2] == ("campaign-old", "campaign_superseded")
    executed_sql = " ".join(query for query, _params in item_connection.cursor_instance.executed)
    assert "outreachsendqueue" not in executed_sql.lower()
    assert "outreachsendbatches" not in executed_sql.lower()


def test_batch_scans_past_blocked_and_current_rows(monkeypatch) -> None:
    initial_connection = BatchConnection()
    item_connections = [BatchConnection(), BatchConnection(), BatchConnection()]
    connections = iter([initial_connection, *item_connections])
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "get_db_connection",
        lambda: next(connections),
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_actor_id",
        lambda cursor, requested: "actor-1",
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_platform_email_sender",
        lambda cursor: "sender-localosgo",
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_load_candidates",
        lambda cursor, **kwargs: [
            _candidate(id="blocked", contact_count=0, evidence_count=1),
            _candidate(
                id="current",
                latest_campaign_id="campaign-current",
                latest_campaign_status="draft",
                contact_count=1,
                evidence_count=1,
            ),
            _candidate(id="eligible", contact_count=1, evidence_count=1),
        ],
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "_campaign_is_current",
        lambda cursor, campaign_id, sender_mode: campaign_id == "campaign-current",
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "build_preview",
        lambda *args, **kwargs: {"status": "needs_channel_setup"},
    )
    monkeypatch.setattr(
        outreach_batch_preparation_service,
        "persist_preview",
        lambda cursor, preview, user_id: {"id": "campaign-new", "version": 1},
    )

    result = outreach_batch_preparation_service.prepare_campaigns(
        workstream_type="localos_sales",
        batch_size=1,
        execute=True,
    )

    assert result["blocked"] == {"needs_contact": 1}
    assert result["already_current"] == 1
    assert result["attempted"] == 1
    assert result["created"] == 1


def test_batch_module_contains_no_delivery_or_approval_write() -> None:
    source = Path(outreach_batch_preparation_service.__file__).read_text(encoding="utf-8")
    forbidden = (
        "INSERT INTO outreachsendqueue",
        "INSERT INTO outreachsendbatches",
        "approve_campaign(",
        "dispatch",
    )
    for token in forbidden:
        assert token not in source
