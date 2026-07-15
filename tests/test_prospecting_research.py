import json
from pathlib import Path

from flask import Flask

from api import agent_prospecting_api
from services.prospecting_research_service import import_report, normalize_candidate, parse_report, preview_report


ROOT = Path(__file__).resolve().parents[1]


def test_confirmed_demand_signal_gets_evidence_backed_priority():
    candidate = normalize_candidate(
        {
            "candidate_id": "clinic-1",
            "name": "Example Clinic",
            "score_breakdown": {
                "pain_strength": 5,
                "product_fit": 5,
                "timing": 5,
                "reachability": 5,
                "evidence_quality": 5,
            },
            "why_now": "The company is publicly looking for a simpler review workflow.",
            "sources": [
                {
                    "title": "Public company post",
                    "url": "https://example.com/company-post",
                    "published_at": "2026-07-10",
                }
            ],
            "signals": [
                {
                    "kind": "demand",
                    "observed": "The company asked for a review-management recommendation.",
                    "source_url": "https://example.com/company-post",
                }
            ],
            "suggested_opener": "Saw your public request for a simpler review workflow.",
            "opener_source_url": "https://example.com/company-post",
            "message_brief": {
                "segment": "clinics",
                "buyer_persona": "operations lead",
                "pain": "review work is fragmented",
                "signal": "the company asked for a review-management recommendation",
                "result": "a review workflow gap analysis",
                "proof": "the public company post",
                "cta": "Would a short gap analysis be useful?",
            },
            "contacts": {
                "email": {
                    "value": "hello@example.com",
                    "source_url": "https://example.com/company-post",
                    "observed_at": "2026-07-11",
                    "confidence": 0.9,
                }
            },
        }
    )

    assert candidate["score"] == 100
    assert candidate["signal_label"] == "strong_signal"
    assert candidate["qualification_stage"] == "high_intent"
    assert candidate["sources"][0]["published_at"] == "2026-07-10"
    assert candidate["suggested_opener"].startswith("Saw your public request")
    assert candidate["opener_source_url"] == "https://example.com/company-post"
    assert candidate["message_brief"]["result"] == "a review workflow gap analysis"
    assert candidate["email"] == "hello@example.com"
    assert candidate["contact_evidence"] == [
        {
            "field": "email",
            "source_url": "https://example.com/company-post",
            "observed_at": "2026-07-11",
            "confidence": 0.9,
        }
    ]


def test_missing_evidence_blocks_opener_and_does_not_invent_pain():
    candidate = normalize_candidate(
        {
            "name": "No Evidence Company",
            "why_now": "",
            "suggested_opener": "We know your sales are falling.",
            "message_brief": {
                "pain": "sales are falling",
                "signal": "unverified decline",
                "result": "a short review",
            },
            "score_breakdown": {
                "pain_strength": 5,
                "product_fit": 5,
                "timing": 5,
                "reachability": 5,
                "evidence_quality": 5,
            },
            "sources": [{"title": "Unsafe", "url": "javascript:alert(1)"}],
            "signals": [
                {
                    "kind": "pain",
                    "observed": "Unverified claim",
                    "source_url": "javascript:alert(1)",
                }
            ],
        }
    )

    assert candidate["sources"] == []
    assert candidate["signals"] == []
    assert candidate["suggested_opener"] == ""
    assert "pain" not in candidate["message_brief"]
    assert "signal" not in candidate["message_brief"]
    assert candidate["signal_label"] == "fit_only"
    assert candidate["opener_source_url"] == ""
    assert any("not confirmed" in item.lower() or "не подтверждён" in item.lower() for item in candidate["limitations"])


def test_client_partner_report_requires_explicit_business_context():
    try:
        parse_report({"mode": "client-partners", "candidates": []})
    except ValueError as error:
        assert "client_business_id" in str(error)
    else:
        raise AssertionError("client-partners report must require client_business_id")


def test_localos_sales_report_cannot_attach_itself_to_a_client_business():
    report = parse_report(
        {
            "mode": "localos-sales",
            "client_business_id": "business-foreign",
            "candidates": [{"candidate_id": "lead-1", "name": "Direct LocalOS Lead"}],
        }
    )

    assert report["workstream_type"] == "localos_sales"
    assert report["client_business_id"] is None


class _AmbiguousCursor:
    def execute(self, _query, _params=None):
        return None

    def fetchall(self):
        return [
            {"id": "lead-1", "name": "Same Company", "city": "Moscow", "address": "First address"},
            {"id": "lead-2", "name": "Same Company", "city": "Moscow", "address": "Second address"},
        ]


def test_preview_keeps_ambiguous_company_out_of_automatic_import():
    report = parse_report(
        {
            "mode": "localos-sales",
            "candidates": [{"candidate_id": "same-1", "name": "Same Company"}],
        }
    )

    items = preview_report(_AmbiguousCursor(), report)

    assert items[0]["action"] == "ambiguous"
    assert items[0]["workstream_id"] is None
    assert len(items[0]["matches"]) == 2


class _ExistingImportCursor:
    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return {"report_hash": "different-report", "result_json": {"success": True}}


class _ExistingImportConnection:
    def cursor(self, cursor_factory=None):
        return _ExistingImportCursor()


def test_idempotency_key_cannot_be_reused_for_another_report():
    report = parse_report({"mode": "localos-sales", "candidates": []})

    try:
        import_report(_ExistingImportConnection(), report, [], "agent-1", "same-key")
    except ValueError as error:
        assert "another prospecting report" in str(error)
    else:
        raise AssertionError("idempotency key reuse must be rejected")


class _Cursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((" ".join(str(query).split()).lower(), params))


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()

    def cursor(self, cursor_factory=None):
        return self.cursor_instance

    def commit(self):
        return None

    def close(self):
        return None


def test_prepare_authenticates_before_workstream_lookup(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(agent_prospecting_api.agent_prospecting_bp)
    connection = _Connection()
    monkeypatch.setattr(agent_prospecting_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(agent_prospecting_api, "load_agent_client_by_key", lambda _cursor, _key: None)
    monkeypatch.setattr(agent_prospecting_api, "log_agent_action", lambda _cursor, **_kwargs: "ledger-1")

    response = app.test_client().post("/api/agent-api/prospecting/workstreams/private-id/prepare")

    assert response.status_code in {401, 403}
    assert all("from lead_workstreams" not in query for query, _params in connection.cursor_instance.queries)


def test_client_business_id_does_not_replace_explicit_agent_grant(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(agent_prospecting_api.agent_prospecting_bp)
    connection = _Connection()
    monkeypatch.setattr(agent_prospecting_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(
        agent_prospecting_api,
        "load_agent_client_by_key",
        lambda _cursor, _key: {
            "id": "agent-1",
            "status": "live",
            "allowed_scopes": ["prospecting:context:read"],
        },
    )
    monkeypatch.setattr(agent_prospecting_api, "grant_allows", lambda *_args: False)
    monkeypatch.setattr(agent_prospecting_api, "log_agent_action", lambda _cursor, **_kwargs: "ledger-1")
    monkeypatch.setattr(
        agent_prospecting_api,
        "load_context",
        lambda *_args: (_ for _ in ()).throw(AssertionError("context must not load without a grant")),
    )

    response = app.test_client().get(
        "/api/agent-api/prospecting/context?mode=client-partners&business_id=business-foreign",
        headers={"X-LocalOS-Agent-Key": "localos_agent_live_test"},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "PROSPECTING_GRANT_REQUIRED"


def test_agent_prospecting_contract_has_no_send_operation():
    contract = json.loads((ROOT / "frontend/public/localos-agent-openapi.json").read_text(encoding="utf-8"))
    prospecting_paths = {
        path: value
        for path, value in contract["paths"].items()
        if path.startswith("/api/agent-api/prospecting/")
    }

    assert set(prospecting_paths) == {
        "/api/agent-api/prospecting/context",
        "/api/agent-api/prospecting/import-preview",
        "/api/agent-api/prospecting/import",
        "/api/agent-api/prospecting/workstreams/{workstream_id}/prepare",
    }
    for operations in prospecting_paths.values():
        for operation in operations.values():
            assert operation["x-localos"]["external_send"] is False
            assert "send" not in operation["operationId"].lower()


def test_research_migration_preserves_history_and_idempotency():
    migration = (ROOT / "alembic_migrations/versions/20260715_add_lead_research.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS lead_workstream_research" in migration
    assert "uq_lead_workstream_research_hash" in migration
    assert "agent_client_prospecting_grants" in migration
    assert "uq_agent_prospecting_import_idempotency" in migration
    assert "contact_evidence_json" in migration
    assert "opener_source_url" in migration
    assert "DROP TABLE IF EXISTS lead_workstreams" not in migration


def test_room_handlers_use_agent_owner_while_ledger_keeps_agent_identity():
    service = (ROOT / "src/services/prospecting_research_service.py").read_text(encoding="utf-8")

    assert "SELECT owner_user_id FROM agent_clients" in service
    assert service.count("user_id=actor_user_id") == 2
    assert "created_by_agent_client_id" in service
    assert 'result["external_send_performed"] = False' in service


def test_reused_import_does_not_prepare_a_second_room_or_draft():
    api = (ROOT / "src/api/agent_prospecting_api.py").read_text(encoding="utf-8")

    assert 'if result.get("reused"):' in api
    assert 'prepared = result.get("prepared")' in api
    assert "UPDATE agent_prospecting_imports" in api
    assert "SET result_json = %s" in api
