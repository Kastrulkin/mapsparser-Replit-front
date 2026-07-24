from pathlib import Path
import threading

from services.llm import LLMTaskRequest, LLMTaskResult
from services.llm import gateway
from services.llm.adapters import DeepSeekAdapter
from services.llm.policy import most_restrictive_data_class, prepare_prompt_for_provider
from services.llm.registry import get_task_definition, list_task_definitions, model_for_definition
from services.llm.metrics import normalize_pilot_metric, pilot_metrics_select
from services.llm.analytics import (
    build_average_ticket_analysis_payload,
    build_review_signal_payload,
    build_service_catalog_analysis_payload,
)
from services.llm.schema import validate_json_schema


def test_registry_assigns_expected_provider_and_models(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL_REASONING", "deepseek-v4-pro")
    monkeypatch.setenv("DEEPSEEK_MODEL_FAST", "deepseek-v4-flash")

    compiler = get_task_definition("agent_compiler")
    document = get_task_definition("agent_document_analysis")
    table = get_task_definition("agent_table_analysis")
    review = get_task_definition("review_reply")

    assert compiler is not None and compiler.primary_provider == "deepseek"
    assert document is not None and model_for_definition(document) == "deepseek-v4-pro"
    assert table is not None and model_for_definition(table) == "deepseek-v4-flash"
    assert review is not None and review.primary_provider == "gigachat"


def test_registry_has_an_explicit_provider_for_every_supported_task():
    deepseek_tasks = {
        "agent_compiler",
        "agent_document_analysis",
        "agent_table_analysis",
        "operator_intent_classify",
        "average_ticket_analysis",
        "service_catalog_analysis",
        "review_signal_classify",
        "review_signal_synthesis",
        "lead_audit_enrichment",
    }
    expected_tasks = {
        "review_reply",
        "news_generation",
        "social_post_generation",
        "service_optimization",
        "service_copy_generation",
        "outreach_personalization",
        "agent_email_draft",
        "agent_review_replies",
        "ai_agent_booking",
        "ai_agent_booking_complex",
        "ai_agent_marketing",
        "agent_custom_message_draft",
        "knowledge_semantic_analysis",
        "average_ticket_matrix",
        "finance_sales_recognition",
        "generic_russian_analysis",
        *deepseek_tasks,
    }
    definitions = {item.task_key: item for item in list_task_definitions()}

    assert set(definitions) == expected_tasks
    assert {key for key, item in definitions.items() if item.primary_provider == "deepseek"} == deepseek_tasks
    assert all(item.primary_provider in {"gigachat", "deepseek"} for item in definitions.values())


def test_finance_sales_recognition_is_registered_as_sensitive_json():
    definition = get_task_definition("finance_sales_recognition")

    assert definition is not None
    assert definition.primary_provider == "gigachat"
    assert definition.data_class == "financial_sensitive"
    assert definition.response_kind == "json"
    assert definition.response_schema["required"] == ["transactions"]


def test_all_gigachat_tasks_default_to_max(monkeypatch):
    monkeypatch.delenv("GIGACHAT_MODEL", raising=False)
    monkeypatch.delenv("GIGACHAT_MODEL_MAX", raising=False)

    models = {
        model_for_definition(item)
        for item in list_task_definitions()
        if item.primary_provider == "gigachat"
    }

    assert models == {"GigaChat-Max"}
    assert "GigaChat-Pro" not in models


def test_unknown_task_fails_closed():
    result = gateway.run_llm_task(LLMTaskRequest(task_key="missing", prompt="test"))

    assert result.status == "task_blocked"
    assert result.fallback_reason == "LLM_TASK_NOT_REGISTERED"


def test_deepseek_policy_blocks_sensitive_classes_and_credentials():
    pii = prepare_prompt_for_provider("client data", provider="deepseek", data_class="pii")
    finance = prepare_prompt_for_provider("revenue", provider="deepseek", data_class="financial_sensitive")
    secret = prepare_prompt_for_provider("api_key=top-secret", provider="deepseek", data_class="public")

    assert pii.allowed is False and pii.reason_code == "DEEPSEEK_DATA_CLASS_BLOCKED"
    assert finance.allowed is False and finance.reason_code == "DEEPSEEK_DATA_CLASS_BLOCKED"
    assert secret.allowed is False and secret.reason_code == "LLM_CREDENTIALS_BLOCKED"


def test_deepseek_policy_redacts_business_internal_pii():
    decision = prepare_prompt_for_provider(
        "Клиент: Иван Петров\nТелефон +7 999 123-45-67\nemail ivan@example.com\nЦель: создать агента",
        provider="deepseek",
        data_class="business_internal",
    )

    assert decision.allowed is True
    assert decision.redacted is True
    assert "Иван Петров" not in decision.prompt
    assert "999 123" not in decision.prompt
    assert "ivan@example.com" not in decision.prompt
    assert "создать агента" in decision.prompt


def test_deepseek_policy_handles_quoted_json_pii_and_credentials():
    redacted = prepare_prompt_for_provider(
        '{"client_name":"Иван Петров","email":"ivan@example.com","goal":"draft"}',
        provider="deepseek",
        data_class="business_internal",
    )
    blocked = prepare_prompt_for_provider(
        '{"api_key":"top-secret"}',
        provider="deepseek",
        data_class="public",
    )

    assert redacted.allowed is True
    assert "Иван Петров" not in redacted.prompt
    assert "ivan@example.com" not in redacted.prompt
    assert blocked.allowed is False
    assert blocked.reason_code == "LLM_CREDENTIALS_BLOCKED"


def test_request_cannot_downgrade_registry_data_class():
    assert most_restrictive_data_class("pii", "public") == "pii"
    assert most_restrictive_data_class("business_internal", "financial_sensitive") == "financial_sensitive"
    assert most_restrictive_data_class("business_internal", "unknown") == "unknown"


def test_schema_validator_reports_required_and_nested_type_errors():
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"type": "string"}}},
        "required": ["items", "title"],
    }

    errors = validate_json_schema({"items": ["ok", 3]}, schema)

    assert "$.title: required" in errors
    assert "$[unexpected]" not in errors
    assert "$.items[1]: expected string" in errors


def test_router_uses_deepseek_only_for_enabled_cohort(monkeypatch):
    calls = []

    def fake_generate(request, definition, *, provider, prompt, shadow=False):
        calls.append((provider, shadow, prompt))
        return LLMTaskResult(
            status="completed",
            content='{"source":"manual","destination":"manual"}',
            parsed_data={"source": "manual", "destination": "manual"},
            provider=provider,
            model="test-model",
            shadow=shadow,
        )

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LLM_SHADOW_MODE", "false")
    monkeypatch.setenv("LLM_DEEPSEEK_BUSINESS_IDS", "business-1")
    monkeypatch.setattr(gateway, "_generate_once", fake_generate)

    enabled = gateway.run_llm_task(
        LLMTaskRequest(task_key="agent_compiler", prompt="build", business_id="business-1")
    )
    disabled = gateway.run_llm_task(
        LLMTaskRequest(task_key="agent_compiler", prompt="build", business_id="business-2")
    )

    assert enabled.provider == "deepseek"
    assert disabled.provider == "gigachat"
    assert calls[0][0] == "deepseek"
    assert calls[1][0] == "gigachat"


def test_operator_router_can_use_deepseek_without_enabling_other_tasks(monkeypatch):
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "false")
    monkeypatch.setenv("OPERATOR_DEEPSEEK_ROUTER_ENABLED", "true")

    definition = get_task_definition("operator_intent_classify")
    other_definition = get_task_definition("agent_compiler")

    assert definition is not None
    assert other_definition is not None
    assert gateway._provider_for_request(
        definition,
        LLMTaskRequest(task_key="operator_intent_classify", prompt="classify", business_id="business-2"),
    ) == "deepseek"
    assert gateway._provider_for_request(
        other_definition,
        LLMTaskRequest(task_key="agent_compiler", prompt="build", business_id="business-2"),
    ) == "gigachat"


def test_public_platform_audit_uses_deepseek_without_tenant_id(monkeypatch):
    calls = []

    def fake_generate(request, definition, *, provider, prompt, shadow=False):
        calls.append(provider)
        return LLMTaskResult(
            status="completed",
            content='{"summary_text":"Недостаток","recommended_actions":[],"why_now":"Сейчас"}',
            provider=provider,
            model="test-model",
        )

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LLM_SHADOW_MODE", "true")
    monkeypatch.setattr(gateway, "_generate_once", fake_generate)

    result = gateway.run_llm_task(
        LLMTaskRequest(task_key="lead_audit_enrichment", prompt="public audit")
    )

    assert result.status == "completed"
    assert calls == ["deepseek"]


def test_shadow_keeps_gigachat_result_and_records_deepseek_attempt(monkeypatch):
    calls = []
    shadow_finished = threading.Event()

    def fake_generate(request, definition, *, provider, prompt, shadow=False):
        calls.append((provider, shadow))
        if shadow:
            shadow_finished.set()
        return LLMTaskResult(
            status="completed",
            content='{"source":"manual","destination":"manual"}',
            provider=provider,
            model="test-model",
            shadow=shadow,
        )

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LLM_SHADOW_MODE", "true")
    monkeypatch.setenv("LLM_DEEPSEEK_BUSINESS_IDS", "business-1")
    monkeypatch.setattr(gateway, "_generate_once", fake_generate)

    result = gateway.run_llm_task(
        LLMTaskRequest(task_key="agent_compiler", prompt="build", business_id="business-1")
    )

    assert result.provider == "gigachat"
    assert result.shadow is False
    assert shadow_finished.wait(timeout=1)
    assert calls == [("gigachat", False), ("deepseek", True)]


def test_shadow_saturation_does_not_change_user_result(monkeypatch):
    calls = []

    class BusyShadowSlots:
        def acquire(self, *, blocking):
            assert blocking is False
            return False

    def fake_generate(request, definition, *, provider, prompt, shadow=False):
        calls.append((provider, shadow))
        return LLMTaskResult(
            status="completed",
            content='{"source":"manual","destination":"manual"}',
            provider=provider,
            model="test-model",
            shadow=shadow,
        )

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LLM_SHADOW_MODE", "true")
    monkeypatch.setenv("LLM_DEEPSEEK_BUSINESS_IDS", "business-1")
    monkeypatch.setattr(gateway, "_SHADOW_SEMAPHORE", BusyShadowSlots())
    monkeypatch.setattr(gateway, "_generate_once", fake_generate)

    result = gateway.run_llm_task(
        LLMTaskRequest(task_key="agent_compiler", prompt="build", business_id="business-1")
    )

    assert result.status == "completed"
    assert result.provider == "gigachat"
    assert calls == [("gigachat", False)]


def test_shadow_uses_same_single_schema_correction_retry(monkeypatch):
    class ShadowSlot:
        def release(self):
            return None

    responses = iter([
        LLMTaskResult(status="completed", content="not-json", provider="deepseek", shadow=True),
        LLMTaskResult(
            status="completed",
            content='{"source":"manual","destination":"manual"}',
            provider="deepseek",
            shadow=True,
        ),
    ])
    recorded = []

    monkeypatch.setattr(gateway, "_generate_once", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(
        gateway,
        "_record_llm_usage",
        lambda request, result, **kwargs: recorded.append((result.status, kwargs["metadata"])),
    )
    monkeypatch.setattr(gateway, "_SHADOW_SEMAPHORE", ShadowSlot())

    definition = get_task_definition("agent_compiler")
    assert definition is not None
    gateway._run_shadow_request(
        LLMTaskRequest(task_key="agent_compiler", prompt="build", shadow=True),
        definition,
    )

    assert recorded[0][0] == "completed"
    assert recorded[0][1]["correction_attempted"] is True


def test_invalid_json_gets_one_correction_retry(monkeypatch):
    responses = iter(
        [
            LLMTaskResult(status="completed", content="not-json", provider="deepseek"),
            LLMTaskResult(status="completed", content='{"intent":"unknown"}', provider="deepseek"),
        ]
    )
    calls = []

    def fake_generate(request, definition, *, provider, prompt, shadow=False):
        calls.append(prompt)
        return next(responses)

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LLM_SHADOW_MODE", "false")
    monkeypatch.setenv("LLM_DEEPSEEK_BUSINESS_IDS", "business-1")
    monkeypatch.setattr(gateway, "_generate_once", fake_generate)

    result = gateway.run_llm_task(
        LLMTaskRequest(task_key="operator_intent_classify", prompt="classify", business_id="business-1")
    )

    assert result.status == "completed"
    assert result.parsed_data == {"intent": "unknown"}
    assert len(calls) == 2
    assert "Исправь только формат" in calls[1]


def test_second_invalid_json_requires_deterministic_fallback(monkeypatch):
    recorded = []

    def fake_generate(request, definition, *, provider, prompt, shadow=False):
        return LLMTaskResult(status="completed", content="still-not-json", provider="deepseek")

    monkeypatch.setenv("LLM_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LLM_DEEPSEEK_BUSINESS_IDS", "business-1")
    monkeypatch.setattr(gateway, "_generate_once", fake_generate)
    monkeypatch.setattr(
        gateway,
        "_record_llm_usage",
        lambda request, result, **kwargs: recorded.append(result.status),
    )

    result = gateway.run_llm_task(
        LLMTaskRequest(task_key="operator_intent_classify", prompt="classify", business_id="business-1")
    )

    assert result.status == "fallback_required"
    assert result.fallback_reason == "LLM_SCHEMA_RETRY_EXHAUSTED"
    assert recorded == ["fallback_required"]


def test_max_failure_uses_deepseek_once_and_records_both_attempts(monkeypatch):
    calls = []
    recorded = []

    def fake_generate(request, definition, *, provider, prompt, shadow=False, **kwargs):
        calls.append(provider)
        if provider == "gigachat":
            return LLMTaskResult(status="provider_error", provider=provider, fallback_reason="MAX_DOWN")
        return LLMTaskResult(status="completed", provider=provider, model="deepseek-v4-pro", content="Черновик")

    monkeypatch.setattr(gateway, "_generate_once", fake_generate)
    monkeypatch.setattr(
        gateway,
        "_record_llm_usage",
        lambda request, result, **kwargs: recorded.append((result.provider, result.status, kwargs["metadata"])),
    )

    result = gateway.run_llm_task(LLMTaskRequest(task_key="news_generation", prompt="Новость"))

    assert calls == ["gigachat", "deepseek"]
    assert result.status == "completed"
    assert result.provider == "deepseek"
    assert result.primary_provider == "gigachat"
    assert result.fallback_provider == "deepseek"
    assert result.primary_failure_reason == "MAX_DOWN"
    assert len(recorded) == 2


def test_review_fallback_requires_explicit_sanitized_prompt(monkeypatch):
    calls = []

    def fake_generate(request, definition, *, provider, prompt, shadow=False, **kwargs):
        calls.append((provider, prompt))
        return LLMTaskResult(status="provider_error", provider=provider, fallback_reason="DOWN")

    monkeypatch.setattr(gateway, "_generate_once", fake_generate)

    result = gateway.run_llm_task(
        LLMTaskRequest(task_key="review_reply", prompt="Телефон +7 999 123-45-67")
    )

    assert result.status == "provider_error"
    assert calls == [("gigachat", "Телефон +7 999 123-45-67")]


def test_analytics_payloads_are_aggregated_and_anonymized():
    average_payload = build_average_ticket_analysis_payload(
        {
            "average_ticket": 3500.0,
            "average_ticket_delta_30d": 4.2,
            "client_name": "Иван Петров",
            "transactions": [{"card": "1234"}],
            "events": {"offered": 8, "bought": 3},
            "by_category": [{"category": "Волосы", "offered": 4, "bought": 2, "conversion": 50.0}],
        },
        [{"id": "svc-1", "name": "Стрижка", "price": "2500", "client_phone": "+79991234567"}],
    )
    service_payload = build_service_catalog_analysis_payload(
        [{"id": "svc-1", "name": "Стрижка", "price": "2500", "description": "private"}]
    )
    review_payload = build_review_signal_payload(
        [{"review_id": "raw-1", "author_name": "Иван", "rating": 2, "text": "Иван Петров, звоните +7 999 123-45-67, ivan@example.com"}]
    )

    serialized_average = str(average_payload)
    assert "Иван Петров" not in serialized_average
    assert "transactions" not in average_payload["calculated_metrics"]
    assert average_payload["calculated_metrics"]["average_ticket"] == 3500.0
    assert service_payload["services"][0]["service_id"] == "svc-1"
    assert "description" not in service_payload["services"][0]
    assert review_payload["reviews"][0]["review_id"] != "raw-1"
    assert "Иван" not in str(review_payload)
    assert "Петров" not in str(review_payload)
    assert "999 123" not in str(review_payload)
    assert "ivan@example.com" not in str(review_payload)


def test_compiler_reports_selected_provider(monkeypatch):
    from services import agent_compiler_llm

    monkeypatch.setattr(
        agent_compiler_llm,
        "run_llm_task",
        lambda request: LLMTaskResult(
            status="completed",
            content='{"source":"manual","destination":"communications","trigger":"manual.run"}',
            provider="deepseek",
            model="deepseek-v4-pro",
        ),
    )

    result = agent_compiler_llm.infer_agent_workflow_intent("Create a manual draft workflow")

    assert result["status"] == "compiled_intent"
    assert result["source"] == "deepseek"


def test_agent_creation_billing_does_not_write_estimated_token_duplicate():
    source = Path("src/services/agent_builder_billing.py").read_text(encoding="utf-8")

    assert "agent_compiler_estimate" not in source
    assert '"usage_record_mode": "provider_actual"' in source


def test_observability_migration_is_idempotent():
    source = Path("alembic_migrations/versions/20260722_add_llm_routing_observability.py").read_text(
        encoding="utf-8"
    )

    assert source.count("ADD COLUMN IF NOT EXISTS") == 7
    assert "CREATE INDEX IF NOT EXISTS" in source
    assert "provider_request_id" in source
    assert "metadata_json" in source


def test_pilot_metrics_apply_rollout_thresholds():
    metric = normalize_pilot_metric({
        "task_key": "agent_compiler",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "shadow": True,
        "requests_count": 100,
        "completed_count": 98,
        "corrected_count": 3,
        "fallback_count": 2,
        "policy_blocked_count": 0,
        "average_latency_ms": 12000,
        "p95_latency_ms": 44000,
    })

    assert metric["completion_rate"] == 0.98
    assert metric["first_pass_valid_rate"] == 0.95
    assert metric["fallback_rate"] == 0.02
    assert metric["automated_gate_passed"] is True
    assert metric["manual_review_required"] is True


def test_pilot_metrics_fail_on_policy_attempt_or_flash_latency():
    metric = normalize_pilot_metric({
        "task_key": "agent_table_analysis",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "requests_count": 50,
        "completed_count": 50,
        "fallback_count": 0,
        "policy_blocked_count": 1,
        "p95_latency_ms": 20001,
    })

    assert metric["latency_limit_ms"] == 20000
    assert metric["automated_checks"]["policy_boundary"] is False
    assert metric["automated_checks"]["p95_latency"] is False
    assert metric["automated_gate_passed"] is False


def test_pilot_metrics_query_groups_by_task_provider_model_and_shadow():
    query = pilot_metrics_select("business_id = %s AND created_at >= %s")

    assert "PERCENTILE_CONT(0.95)" in query
    assert "metadata_json ->> 'correction_attempted'" in query
    assert "COALESCE(task_type, 'unknown')" in query
    assert "WHERE business_id = %s AND created_at >= %s" in query


def test_deepseek_adapter_adds_json_instruction_when_caller_omits_it(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "request-1",
                "model": "deepseek-v4-flash",
                "choices": [{"message": {"content": '{"intent":"unknown"}'}}],
                "usage": {"total_tokens": 5},
            }

    def fake_post(url, *, headers, json, timeout):
        captured["body"] = json
        return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("services.llm.adapters.requests.post", fake_post)
    definition = get_task_definition("operator_intent_classify")
    assert definition is not None
    result = DeepSeekAdapter().generate(
        LLMTaskRequest(task_key="operator_intent_classify", prompt="Classify this request"),
        definition,
        prompt="Classify this request",
    )

    assert result.status == "completed"
    assert "JSON" in captured["body"]["messages"][0]["content"]
    assert captured["body"]["response_format"] == {"type": "json_object"}
