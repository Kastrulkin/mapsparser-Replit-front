from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DATA_CLASSES = {
    "public",
    "business_internal",
    "financial_aggregated",
    "pii",
    "financial_sensitive",
    "credentials",
}


@dataclass(frozen=True)
class LLMTaskDefinition:
    task_key: str
    primary_provider: str
    model_profile: str
    data_class: str
    response_kind: str = "text"
    response_schema: dict[str, Any] | None = None
    max_tokens: int = 4000
    temperature: float = 0.1
    timeout_seconds: int = 60
    prompt_version: str = "v1"
    deterministic_fallback: str = "caller"
    shadow_allowed: bool = False
    allow_text_fallback: bool = False
    fallback_data_class: str = ""
    pipeline_stage: str = ""
    quality_gate: str = "non_empty"


@dataclass(frozen=True)
class LLMTaskRequest:
    task_key: str
    prompt: str
    business_id: str = ""
    user_id: str = ""
    prompt_version: str = ""
    response_schema: dict[str, Any] | None = None
    data_class: str = ""
    usage_reference: str = ""
    shadow: bool = False
    pipeline_id: str = ""
    pipeline_stage: str = ""
    fallback_prompt: str = ""


@dataclass
class LLMTaskResult:
    status: str
    content: str = ""
    parsed_data: dict[str, Any] | list[Any] | None = None
    provider: str = "none"
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    validation_errors: list[str] = field(default_factory=list)
    fallback_reason: str = ""
    shadow: bool = False
    provider_request_id: str = ""
    primary_provider: str = ""
    fallback_provider: str = ""
    primary_failure_reason: str = ""
    output_source: str = ""
