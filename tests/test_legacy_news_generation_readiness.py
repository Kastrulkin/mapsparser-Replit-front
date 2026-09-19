"""Regression coverage for the legacy map-news draft endpoint.

The route is extracted directly from the legacy module so these tests do not
bootstrap ``main`` or connect to PostgreSQL.  The cursor accepts only the
queries on this request path, which makes unintended effects observable.
"""

import ast
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from flask import Flask, jsonify, request

from core import db_helpers
from services import content_rules, operator_social_post_generation


class _Cursor:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []
        self._one: Any = None
        self._many: list[Any] = []

    def execute(self, statement: str, params: tuple[Any, ...] | None = None) -> None:
        self.executed.append((statement, params))
        normalized = " ".join(statement.lower().split())
        self._one = None
        self._many = []
        if "from businesses b" in normalized:
            assert params == (self.state["user_id"],) * 3 + (self.state["business_id"],)
            target = params[-1] if params else None
            if target == "missing-business":
                return
            if target not in {"business-a", "business-b"}:
                raise AssertionError(f"unexpected business target: {target}")
            owner_id = "writer" if self.state["access_kind"] == "writer" else "owner-a"
            if self.state.get("missing_owner"):
                owner_id = None
            self._one = {
                "owner_id": owner_id,
                "has_business_membership": self.state["access_kind"] in {"viewer", "manager"},
                "has_network_membership": self.state["access_kind"] == "network_viewer",
                "owns_network": False,
            }
        elif "select bm.role" in normalized:
            assert params == (self.state["business_id"], self.state["user_id"]) * 3
            role = "manager" if self.state["access_kind"] == "manager" else "viewer"
            self._many = [{"role": role}]
        elif "from businesses" in normalized and "select name, business_type" in normalized:
            if params != ("business-a",):
                raise AssertionError(f"business context must use A: {params}")
            self._one = {
                "name": "Studio One",
                "business_type": "wellness",
                "industry": "wellness",
                "categories": "massage",
                "address": "Moscow",
                "description": "",
                "site": "",
                "website": "",
            }
        elif "from userservices where id" in normalized:
            if "business_id" in normalized:
                assert params == (self.state["service_id"], "business-a")
            if "business_id" not in normalized or not params or params[-1] != "business-a":
                self._one = ("Massage B", "Foreign business B service")
            elif params[0] == "service-b":
                return
            else:
                self._one = ("Massage A", "Relaxing massage for business A")
        elif "from userservices where user_id" in normalized:
            raise AssertionError("fallback service must be business-scoped without a user ownership gate")
        elif "from userservices" in normalized:
            if "business_id" not in normalized or params != ("business-a",):
                self._one = ("Massage B", "Foreign business B fallback service")
            else:
                self._one = ("Massage A", "Fallback service for business A")
        elif "from financialtransactions" in normalized:
            selected = "where id" in normalized
            if "business_id" in normalized:
                expected = (self.state["transaction_id"], "business-a") if selected else ("business-a",)
                assert params == expected
            source_is_business_a = "business_id" in normalized and bool(params) and params[-1] == "business-a"
            if selected and source_is_business_a and params[0] == "transaction-b":
                return
            services = '["Massage A"]' if source_is_business_a else '["Foreign B procedure"]'
            if selected:
                self._one = {
                    "transaction_date": "2026-09-01",
                    "amount": 100,
                    "services": services,
                    "notes": "A note" if source_is_business_a else "Foreign B note",
                    "client_type": "new",
                }
            else:
                self._one = {
                    "transaction_date": "2026-09-01",
                    "amount": 100,
                    "services": services,
                    "notes": "A note" if source_is_business_a else "Foreign B note",
                }
        elif "from userexamples" in normalized:
            if "business_id" not in normalized or params != (self.state["user_id"], "business-a"):
                self._many = [("Business B example",), ("Other-user global example",)]
                return
            self._many = (
                [("Business A example",), ("Personal global example",)]
            )
        elif "from information_schema.columns" in normalized:
            assert params[0] == "usernews"
            self._one = {"columns": [name for name in params[1] if name != self.state.get("missing_column")]}
        elif normalized.startswith("create table if not exists usernews ("):
            if self.state.get("dml_only"):
                raise PermissionError("Runtime connection has no schema-change authority")
            return
        elif normalized.startswith("insert into usernews"):
            self.state["steps"].append("insert")
            self.state["pending_effects"].append((statement, params))
        else:
            raise AssertionError(f"unexpected SQL: {statement}")

    def fetchone(self) -> Any:
        return self._one

    def fetchall(self) -> list[Any]:
        return self._many


class _Connection:
    def __init__(self, cursor: _Cursor, state: dict[str, Any]) -> None:
        self.cursor_value = cursor
        self.state = state
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> _Cursor:
        return self.cursor_value

    def commit(self) -> None:
        self.commits += 1
        self.state["pending_effects"].clear()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.state["pending_effects"].clear()


class _Database:
    def __init__(self, state: dict[str, Any]) -> None:
        self.conn = _Connection(_Cursor(state), state)
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        if self.conn.state["pending_effects"]:
            self.conn.commit()

    def rollback_and_close(self) -> None:
        self.conn.rollback()
        self.close_calls += 1


@pytest.fixture
def news_route(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Register the exact decorated ``news_generate`` definition on Flask."""
    app = Flask(__name__)
    state: dict[str, Any] = {
        "access_kind": "writer",
        "provider_result": json.dumps({"news": "Unrelated model draft without the selected service."}),
        "provider_calls": [],
        "enforce_calls": [],
        "resolved_ids": [],
        "audit_business_ids": [],
        "databases": [],
        "steps": [],
        "pending_effects": [],
        "user_id": "writer",
    }

    def database_manager() -> _Database:
        database = _Database(state)
        state["databases"].append(database)
        return database

    def resolve_business(user_id: str, requested_business_id: str | None = None) -> str | None:
        state["resolved_ids"].append((user_id, requested_business_id))
        return requested_business_id

    def provider(*args: Any, **kwargs: Any) -> str:
        state["steps"].append("provider")
        state["provider_calls"].append((args, kwargs))
        result = state["provider_result"]
        if isinstance(result, Exception):
            raise result
        return result

    def enforce(cursor: Any, business_id: str, user_id: str, text: str, *args: Any) -> str:
        state["steps"].append("enforce")
        state["enforce_calls"].append((cursor, business_id, user_id, text, args))
        if state.get("enforce_error"):
            raise ValueError("Rule validation failed")
        return "Enforced final draft for the selected business."

    def record_ai_learning_event(**kwargs: Any) -> None:
        state["steps"].append("event")
        state["audit_business_ids"].append(kwargs["business_id"])

    monkeypatch.setattr(content_rules, "enforce", enforce)
    monkeypatch.setattr(db_helpers, "ensure_user_examples_table", lambda _cursor: None)
    monkeypatch.setattr(
        operator_social_post_generation,
        "_default_social_post_generator",
        lambda *args, **kwargs: json.dumps({"valid": True, "violations": []}),
    )
    namespace = {
        "Any": Any,
        "Dict": dict,
        "app": app,
        "request": request,
        "jsonify": jsonify,
        "uuid": uuid,
        "json": json,
        "rate_limit_if_available": lambda _limit: lambda function: function,
        "verify_session": lambda _token: {"user_id": state["user_id"]},
        "get_business_id_from_user": resolve_business,
        "get_user_language": lambda _user_id, requested: requested or "en",
        "DatabaseManager": database_manager,
        "analyze_text_with_gigachat": provider,
        "_clean_generated_news_text": lambda text: str(text).strip(),
        "_fetch_news_site_description": lambda _site: "",
        "_row_to_dict": lambda _cursor, row: dict(row),
        "detect_industry_key": lambda **kwargs: "wellness",
        "format_industry_pattern_prompt": lambda *_args, **_kwargs: "",
        "load_active_industry_patterns": lambda *_args, **_kwargs: [{"id": "pattern-1"}],
        "format_loaded_active_industry_patterns": lambda _patterns: "",
        "_ensure_usernews_learning_columns": lambda _cursor: None,
        "get_prompt_from_db": lambda _key, default: default,
        "_news_text_has_demo_platform_drift": lambda _text: False,
        "_news_text_has_service_anchor": lambda _text, _service: False,
        "_service_focused_news_fallback": lambda **kwargs: (
            state["steps"].append("fallback") or "Final fallback about Massage A for Studio One."
        ),
        "_news_context_is_cultural_space": lambda _text: False,
        "_news_text_has_school_hallucination": lambda _text: False,
        "record_industry_pattern_impact_event": lambda _conn, _patterns, **kwargs: (
            state["steps"].append("event"), state["audit_business_ids"].append(kwargs["business_id"])
        ),
        "build_pattern_impact_metrics": lambda *_args, **_kwargs: {"needs_review": 0},
        "_table_has_column": lambda *_args: True,
        "record_ai_learning_event": record_ai_learning_event,
    }
    source = ast.parse(Path("src/legacy_routes/client_reports.py").read_text())
    function = next(
        node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "news_generate"
    )
    assert len(function.decorator_list) == 2
    exec(compile(ast.Module(body=[function], type_ignores=[]), "news_generate", "exec"), namespace)
    state["client"] = app.test_client()
    return state


def _post(state: dict[str, Any], business_id: str = "business-a", **payload: Any):
    body = {"business_id": business_id, "use_service": True, "service_id": "service-a"}
    body.update(payload)
    state["business_id"] = business_id
    state["service_id"] = body.get("service_id")
    state["transaction_id"] = body.get("transaction_id")
    return state["client"].post(
        "/api/news/generate",
        headers={"Authorization": "Bearer test"},
        json=body,
    )


def test_news_generation_authorizes_once_then_enforces_final_fallback_and_inserts(news_route: dict[str, Any]) -> None:
    response = _post(news_route)

    assert response.status_code == 200, response.json
    assert news_route["resolved_ids"] == [("writer", "business-a")]
    assert len(news_route["provider_calls"]) == 1
    assert news_route["enforce_calls"][0][1:4] == (
        "business-a",
        "writer",
        "Final fallback about Massage A for Studio One.",
    )
    database = news_route["databases"][0]
    inserts = [entry for entry in database.conn.cursor_value.executed if "insert into usernews" in entry[0].lower()]
    assert len(inserts) == 1
    assert inserts[0][1][2] == "business-a"
    assert inserts[0][1][5:7] == (
        "Enforced final draft for the selected business.",
        "Enforced final draft for the selected business.",
    )
    assert response.json["generated_text"] == "Enforced final draft for the selected business."
    assert news_route["audit_business_ids"] and set(news_route["audit_business_ids"]) == {"business-a"}
    assert news_route["steps"].index("provider") < news_route["steps"].index("fallback")
    assert news_route["steps"].index("fallback") < news_route["steps"].index("enforce")
    assert news_route["steps"].index("enforce") < news_route["steps"].index("event") < news_route["steps"].index("insert")
    assert database.conn.commits == 1 and database.close_calls == 1


def test_news_generation_rejects_selected_foreign_service_before_provider_or_persistence(
    news_route: dict[str, Any]
) -> None:
    response = _post(news_route, service_id="service-b")

    assert response.status_code == 400, response.json
    assert news_route["provider_calls"] == [] and news_route["enforce_calls"] == []
    cursor = news_route["databases"][0].conn.cursor_value
    assert any(
        "from userservices where id" in statement.lower() and "business_id" in statement.lower()
        for statement, _ in cursor.executed
    )
    assert not any("insert into usernews" in statement.lower() for statement, _ in cursor.executed)


def test_news_generation_fallback_service_is_scoped_to_selected_business(news_route: dict[str, Any]) -> None:
    response = _post(news_route, service_id=None)

    assert response.status_code == 200, response.json
    provider_prompt = news_route["provider_calls"][0][0][0]
    assert "Fallback service for business A" in provider_prompt
    assert "Foreign business B fallback service" not in provider_prompt
    cursor = news_route["databases"][0].conn.cursor_value
    assert any(
        "from userservices" in statement.lower()
        and "business_id" in statement.lower()
        and "user_id" not in statement.lower()
        for statement, _ in cursor.executed
    )


@pytest.mark.parametrize("transaction_id", [None, "transaction-a"])
def test_news_generation_transaction_context_is_scoped_to_selected_business(news_route: dict[str, Any], transaction_id) -> None:
    response = _post(
        news_route,
        use_service=False,
        service_id=None,
        use_transaction=True,
        transaction_id=transaction_id,
    )

    assert response.status_code == 200, response.json
    provider_prompt = news_route["provider_calls"][0][0][0]
    assert "Massage A" in provider_prompt and "A note" in provider_prompt
    assert "2026-09-01" in provider_prompt and "100₽" in provider_prompt
    assert "Foreign B procedure" not in provider_prompt and "Foreign B note" not in provider_prompt
    cursor = news_route["databases"][0].conn.cursor_value
    assert any(
        "from financialtransactions" in statement.lower() and "business_id" in statement.lower()
        for statement, _ in cursor.executed
    )


def test_news_generation_rejects_selected_foreign_transaction_before_provider_or_persistence(
    news_route: dict[str, Any]
) -> None:
    response = _post(
        news_route,
        use_service=False,
        service_id=None,
        use_transaction=True,
        transaction_id="transaction-b",
    )

    assert response.status_code == 400, response.json
    assert news_route["provider_calls"] == [] and news_route["enforce_calls"] == []
    cursor = news_route["databases"][0].conn.cursor_value
    assert any(
        "from financialtransactions" in statement.lower() and "business_id" in statement.lower()
        for statement, _ in cursor.executed
    )
    assert not any("insert into usernews" in statement.lower() for statement, _ in cursor.executed)


def test_news_generation_manager_can_use_business_scoped_source_records(news_route: dict[str, Any]) -> None:
    news_route["access_kind"] = "manager"
    news_route["user_id"] = "manager-a"
    response = _post(news_route)

    assert response.status_code == 200, response.json
    assert news_route["provider_calls"]
    cursor = news_route["databases"][0].conn.cursor_value
    service_query = next(statement for statement, _ in cursor.executed if "from userservices where id" in statement.lower())
    assert "business_id" in service_query.lower() and "user_id" not in service_query.lower()


def test_news_generation_honors_canonical_write_access_when_business_has_no_owner(news_route: dict[str, Any]) -> None:
    news_route["access_kind"] = "manager"
    news_route["user_id"] = "manager-a"
    news_route["missing_owner"] = True

    response = _post(news_route)

    assert response.status_code == 200, response.json
    assert len(news_route["provider_calls"]) == 1


def test_news_generation_examples_keep_personal_global_compatibility_but_exclude_other_business(
    news_route: dict[str, Any]
) -> None:
    response = _post(news_route)

    assert response.status_code == 200, response.json
    provider_prompt = news_route["provider_calls"][0][0][0]
    assert "Business A example" in provider_prompt and "Personal global example" in provider_prompt
    assert "Business B example" not in provider_prompt and "Other-user global example" not in provider_prompt
    cursor = news_route["databases"][0].conn.cursor_value
    assert any(
        "from userexamples" in statement.lower() and "business_id" in statement.lower()
        for statement, _ in cursor.executed
    )


def test_news_generation_does_not_persist_an_unused_service_id(news_route: dict[str, Any]) -> None:
    response = _post(news_route, use_service=False, service_id="service-b")

    assert response.status_code == 200, response.json
    cursor = news_route["databases"][0].conn.cursor_value
    insert = next(entry for entry in cursor.executed if "insert into usernews" in entry[0].lower())
    assert insert[1][3] is None


@pytest.mark.parametrize("access_kind", ["viewer", "network_viewer", "foreign"])
def test_news_generation_rejects_non_writers_before_context_provider_rules_or_writes(
    news_route: dict[str, Any], access_kind: str
) -> None:
    news_route["access_kind"] = access_kind
    response = _post(news_route, "business-b")

    assert response.status_code == 403, response.json
    assert news_route["resolved_ids"] == [("writer", "business-b")]
    assert news_route["provider_calls"] == []
    assert news_route["enforce_calls"] == []
    cursor = news_route["databases"][0].conn.cursor_value
    assert not any("select name, business_type" in statement.lower() for statement, _ in cursor.executed)
    assert not any("insert into usernews" in statement.lower() for statement, _ in cursor.executed)
    assert not any(statement.lstrip().lower().startswith(("create ", "alter ", "update ", "delete ")) for statement, _ in cursor.executed)
    assert news_route["databases"][0].close_calls == 1


def test_news_generation_reports_missing_business_before_context_or_provider(news_route: dict[str, Any]) -> None:
    response = _post(news_route, "missing-business")

    assert response.status_code == 404, response.json
    assert news_route["provider_calls"] == [] and news_route["enforce_calls"] == []


def test_news_generation_empty_provider_output_closes_without_persisting(news_route: dict[str, Any]) -> None:
    news_route["provider_result"] = json.dumps({"news": ""})
    response = _post(news_route)

    assert response.status_code == 500, response.json
    database = news_route["databases"][0]
    assert database.close_calls == 1 and database.conn.commits == 0 and database.conn.rollbacks == 1
    assert news_route["pending_effects"] == []
    assert not any("insert into usernews" in statement.lower() for statement, _ in database.conn.cursor_value.executed)


def test_news_generation_provider_error_closes_without_persisting(news_route: dict[str, Any]) -> None:
    news_route["provider_result"] = RuntimeError("provider unavailable")
    response = _post(news_route)

    assert response.status_code == 500, response.json
    database = news_route["databases"][0]
    assert database.close_calls == 1 and database.conn.commits == 0 and database.conn.rollbacks == 1
    assert news_route["pending_effects"] == []
    assert not any("insert into usernews" in statement.lower() for statement, _ in database.conn.cursor_value.executed)


def test_news_generation_rule_error_rolls_back_and_closes_without_effects(news_route: dict[str, Any]) -> None:
    news_route["enforce_error"] = True
    response = _post(news_route)

    assert response.status_code == 500, response.json
    database = news_route["databases"][0]
    assert len(news_route["provider_calls"]) == len(news_route["enforce_calls"]) == 1
    assert database.close_calls == 1 and database.conn.commits == 0 and database.conn.rollbacks == 1
    assert news_route["audit_business_ids"] == [] and news_route["pending_effects"] == []
    assert not any("insert into usernews" in statement.lower() for statement, _ in database.conn.cursor_value.executed)


def test_news_generation_does_not_log_model_content(news_route: dict[str, Any], capsys, caplog) -> None:
    marker = "synthetic-private-draft-marker"
    news_route["provider_result"] = json.dumps({"news": marker})
    response = _post(news_route)

    assert response.status_code == 200, response.json
    assert len(news_route["provider_calls"]) == 1
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err + caplog.text


@pytest.mark.parametrize("failure_kind", ["exception", "dict", "json"])
def test_news_generation_redacts_provider_exception(news_route: dict[str, Any], capsys, caplog, failure_kind) -> None:
    marker = "synthetic-private-provider-detail"
    failures = {"exception": RuntimeError(marker), "dict": {"error": marker}, "json": json.dumps({"error": marker})}
    news_route["provider_result"] = failures[failure_kind]
    response = _post(news_route)

    assert response.status_code == 500
    assert len(news_route["provider_calls"]) == 1
    captured = capsys.readouterr()
    assert marker not in response.get_data(as_text=True) + captured.out + captured.err + caplog.text
    database = news_route["databases"][0]
    assert database.close_calls == 1 and database.conn.rollbacks == 1 and database.conn.commits == 0


def test_news_generation_uses_migrated_schema_without_request_time_ddl(news_route: dict[str, Any]) -> None:
    news_route["dml_only"] = True
    response = _post(news_route)

    assert response.status_code == 200, response.json
    statements = news_route["databases"][0].conn.cursor_value.executed
    assert any("information_schema.columns" in statement for statement, _ in statements)
    assert not any(statement.lstrip().lower().startswith(("create ", "alter ", "drop ")) for statement, _ in statements)


def test_news_generation_missing_migration_fails_before_provider(news_route: dict[str, Any]) -> None:
    news_route["missing_column"] = "business_id"
    response = _post(news_route)

    assert response.status_code == 500
    assert news_route["provider_calls"] == news_route["enforce_calls"] == []
    database = news_route["databases"][0]
    assert database.close_calls == 1 and database.conn.rollbacks == 1
    assert not any("insert into usernews" in statement.lower() for statement, _ in database.conn.cursor_value.executed)
