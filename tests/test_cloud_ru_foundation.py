from pathlib import Path

import pytest

from services import ai_spend_budget
from services.cloud_ru_foundation import (
    CloudRuConfig,
    CloudRuConfigurationError,
    CloudRuFoundationClient,
    DEFAULT_BASE_URL,
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBEDDING_DIMENSIONS,
    DEFAULT_EMBEDDING_MODEL,
)
from services.knowledge_cloud_ru_embeddings import (
    _vector_literal,
    embedding_space,
    process_cloud_ru_vectors,
)
from services.knowledge_embeddings import process_embedding_jobs
from services.llm import gateway
from services.llm.adapters import CloudRuAdapter
from services.llm.contracts import LLMTaskRequest
from services.llm.registry import get_task_definition


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    status_code = 200
    headers = {"x-request-id": "cloud-request"}

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "id": "embedding-response",
            "data": [
                {"index": 1, "embedding": [0.2] * DEFAULT_EMBEDDING_DIMENSIONS},
                {"index": 0, "embedding": [0.1] * DEFAULT_EMBEDDING_DIMENSIONS},
            ],
            "usage": {"prompt_tokens": 42, "total_tokens": 42},
        }


def test_cloud_ru_defaults_are_internal_and_fail_closed(monkeypatch):
    for name in (
        "CLOUD_RU_API_KEY",
        "CLOUD_RU_BASE_URL",
        "CLOUD_RU_CHAT_MODEL",
        "CLOUD_RU_EMBEDDING_MODEL",
        "CLOUD_RU_EMBEDDING_DIMENSIONS",
        "CLOUD_RU_EXTERNAL_MODELS_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)

    config = CloudRuConfig.from_env()

    assert config.base_url == DEFAULT_BASE_URL
    assert config.chat_model == DEFAULT_CHAT_MODEL
    assert config.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert config.embedding_dimensions == DEFAULT_EMBEDDING_DIMENSIONS
    config.validate_model(config.chat_model)
    with pytest.raises(CloudRuConfigurationError, match="CLOUD_RU_EXTERNAL_MODEL_BLOCKED"):
        config.validate_model("openai/gpt-5")


def test_cloud_ru_embedding_response_is_ordered_and_dimension_checked(monkeypatch):
    config = CloudRuConfig(
        api_key="test-key",
        base_url=DEFAULT_BASE_URL,
        chat_model=DEFAULT_CHAT_MODEL,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        embedding_dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
        allow_external_models=False,
    )
    observed = {}

    def fake_guarded_post(post, body, context):
        observed.update({"body": body, "context": context})
        return FakeResponse()

    monkeypatch.setattr("services.cloud_ru_foundation.guarded_post", fake_guarded_post)
    result = CloudRuFoundationClient(config).embeddings(["первый", "второй"])

    assert result["vectors"][0][0] == 0.1
    assert result["vectors"][1][0] == 0.2
    assert result["usage"] == 42
    assert observed["context"]["provider"] == "cloudru_embeddings"
    assert observed["body"]["model"] == DEFAULT_EMBEDDING_MODEL


def test_cloud_ru_embedding_space_is_parallel_to_current_2560_index(monkeypatch):
    monkeypatch.delenv("CLOUD_RU_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("CLOUD_RU_EMBEDDING_DIMENSIONS", raising=False)

    space = embedding_space()

    assert space.provider == "cloudru"
    assert space.dimensions == 2048
    assert _vector_literal([0.0] * 2048).startswith("[0.0,0.0")
    with pytest.raises(ValueError, match="CLOUD_RU_EMBEDDING_DIMENSION_MISMATCH"):
        _vector_literal([0.0] * 2560)


def test_cloud_ru_parallel_worker_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CLOUD_RU_EMBEDDINGS_ENABLED", raising=False)

    assert process_cloud_ru_vectors(object()) == {"status": "disabled", "processed": 0}


def test_legacy_gigachat_embedding_calls_can_stop_without_disabling_cloud_space(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_EMBEDDINGS_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_GIGACHAT_EMBEDDINGS_ENABLED", "false")

    assert process_embedding_jobs(object()) == {
        "status": "disabled",
        "processed": 0,
        "provider": "gigachat",
    }


def test_cloud_ru_chat_routing_requires_key_flag_and_business_allowlist(monkeypatch):
    definition = get_task_definition("review_reply")
    assert definition is not None
    request = LLMTaskRequest(
        task_key="review_reply",
        prompt="Ответ",
        business_id="business-one",
    )
    monkeypatch.setenv("CLOUD_RU_CHAT_ROUTER_ENABLED", "true")
    monkeypatch.setenv("CLOUD_RU_API_KEY", "test-key")
    monkeypatch.setenv("LLM_CLOUD_RU_BUSINESS_IDS", "business-one")
    monkeypatch.setenv("LLM_ROUTER_ENABLED", "false")

    assert gateway._provider_for_request(definition, request) == "cloudru"

    monkeypatch.setenv("LLM_CLOUD_RU_BUSINESS_IDS", "business-two")
    assert gateway._provider_for_request(definition, request) == "gigachat"


def test_cloud_ru_adapter_fails_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("CLOUD_RU_API_KEY", raising=False)
    definition = get_task_definition("review_reply")
    assert definition is not None

    result = CloudRuAdapter().generate(
        LLMTaskRequest(task_key="review_reply", prompt="Ответ", business_id="business-one"),
        definition,
        prompt="Ответ",
    )

    assert result.status == "provider_unavailable"
    assert result.fallback_reason == "CLOUD_RU_API_KEY_MISSING"


def test_cloud_ru_has_separate_conservative_spend_profiles():
    assert ai_spend_budget.limits("cloudru") == ai_spend_budget.CLOUD_RU_LIMITS
    assert (
        ai_spend_budget.limits("cloudru_embeddings")
        == ai_spend_budget.CLOUD_RU_EMBEDDING_LIMITS
    )
    assert ai_spend_budget.CLOUD_RU_EMBEDDING_LIMITS["monthly_tokens"] == 10_000_000


def test_cloud_ru_migration_keeps_vectors_in_a_parallel_2048_table():
    migration = (
        ROOT
        / "alembic_migrations/versions/20261122_add_cloudru_embedding_vectors.py"
    ).read_text()

    assert "knowledge_embedding_vectors" in migration
    assert "HALFVEC(2048)" in migration
    assert "knowledge_embedding_chunks(id)" in migration
    assert "provider = 'cloudru'" in migration
