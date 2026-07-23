from __future__ import annotations

import os
from typing import Any

from services.llm.contracts import LLMTaskDefinition


AGENT_COMPILER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "trigger": {"type": "string"},
        "compiled_template_key": {"type": "string"},
        "source": {"type": "string"},
        "destination": {"type": "string"},
        "read_capability": {"type": "string"},
        "write_capability": {"type": "string"},
        "required_connectors": {"type": "array", "items": {"type": "string"}},
        "workflow_draft": {"type": "object"},
        "approval_points": {"type": "array"},
        "unsupported_requests": {"type": "array"},
        "approval_reasons": {"type": "array", "items": {"type": "string"}},
        "limits": {"type": "object"},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["source", "destination"],
}
DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "array"},
        "risks": {"type": "array"},
        "facts": {"type": "array"},
        "fields": {"type": "object"},
        "next_questions": {"type": "array"},
        "rules_applied": {"type": "array"},
    },
    "required": ["title", "summary", "facts"],
}
TABLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "array"},
        "exceptions": {"type": "array"},
        "rows_to_review": {"type": "array"},
        "recommendations": {"type": "array"},
        "rules_applied": {"type": "array"},
    },
    "required": ["title", "summary", "exceptions", "rows_to_review"],
}
AVERAGE_TICKET_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "growth_opportunities": {"type": "array"},
        "packages": {"type": "array"},
        "upsells": {"type": "array"},
        "evidence": {"type": "array"},
        "expected_effect_range": {"type": "object"},
        "risks": {"type": "array"},
        "questions": {"type": "array"},
    },
    "required": ["growth_opportunities", "packages", "upsells", "evidence", "risks"],
}
SERVICE_CATALOG_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "duplicates": {"type": "array"},
        "groups": {"type": "array"},
        "price_gaps": {"type": "array"},
        "strategy": {"type": "array"},
        "source_service_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["duplicates", "groups", "price_gaps", "strategy", "source_service_ids"],
}
REVIEW_SIGNAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "signals": {"type": "array"},
        "themes": {"type": "array"},
        "urgent_review_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["signals", "themes"],
}
LEAD_AUDIT_ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary_text": {"type": "string"},
        "recommended_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        },
        "why_now": {"type": "string"},
    },
    "required": ["summary_text", "recommended_actions", "why_now"],
}


def _task(
    key: str,
    *,
    provider: str = "gigachat",
    profile: str = "gigachat_max",
    data_class: str = "business_internal",
    response_kind: str = "text",
    schema: dict[str, Any] | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.1,
    timeout: int = 60,
    prompt_version: str = "v1",
    shadow_allowed: bool = False,
    allow_text_fallback: bool = False,
    fallback_data_class: str = "",
    pipeline_stage: str = "",
) -> LLMTaskDefinition:
    return LLMTaskDefinition(
        task_key=key,
        primary_provider=provider,
        model_profile=profile,
        data_class=data_class,
        response_kind=response_kind,
        response_schema=schema,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_seconds=timeout,
        prompt_version=prompt_version,
        shadow_allowed=shadow_allowed,
        allow_text_fallback=allow_text_fallback,
        fallback_data_class=fallback_data_class,
        pipeline_stage=pipeline_stage,
        quality_gate="schema_valid" if schema else "non_empty",
    )


TASK_REGISTRY: dict[str, LLMTaskDefinition] = {
    "review_reply": _task("review_reply", data_class="pii", prompt_version="review_reply_v1", allow_text_fallback=True, fallback_data_class="business_internal", pipeline_stage="copy"),
    "news_generation": _task("news_generation", data_class="public", prompt_version="news_generation_v1", allow_text_fallback=True, pipeline_stage="copy"),
    "social_post_generation": _task("social_post_generation", data_class="public", prompt_version="social_post_generation_v1", allow_text_fallback=True, pipeline_stage="copy"),
    "service_optimization": _task("service_optimization", prompt_version="service_optimization_v1", allow_text_fallback=True, pipeline_stage="copy"),
    "service_copy_generation": _task("service_copy_generation", response_kind="json", allow_text_fallback=True, pipeline_stage="copy"),
    "outreach_personalization": _task("outreach_personalization", data_class="pii", prompt_version="outreach_personalization_v4", pipeline_stage="copy"),
    "lead_audit_enrichment": _task(
        "lead_audit_enrichment",
        provider="deepseek",
        profile="deepseek_fast",
        data_class="public",
        response_kind="json",
        schema=LEAD_AUDIT_ENRICHMENT_SCHEMA,
        max_tokens=2500,
        temperature=0.0,
        timeout=45,
        prompt_version="lead_audit_enrichment_v2",
        pipeline_stage="analysis",
    ),
    "agent_email_draft": _task("agent_email_draft", data_class="pii", prompt_version="agent_email_draft_v1", pipeline_stage="copy"),
    "agent_review_replies": _task("agent_review_replies", data_class="pii", prompt_version="agent_review_replies_v8", allow_text_fallback=True, fallback_data_class="business_internal", pipeline_stage="copy"),
    "ai_agent_booking": _task("ai_agent_booking", data_class="pii", prompt_version="ai_agent_booking_v1"),
    "ai_agent_booking_complex": _task("ai_agent_booking_complex", profile="gigachat_max", data_class="pii"),
    "ai_agent_marketing": _task("ai_agent_marketing", prompt_version="ai_agent_marketing_v1"),
    "agent_custom_message_draft": _task("agent_custom_message_draft"),
    "knowledge_semantic_analysis": _task("knowledge_semantic_analysis", prompt_version="knowledge_semantic_analysis_v1"),
    "average_ticket_matrix": _task(
        "average_ticket_matrix", data_class="financial_sensitive", allow_text_fallback=True,
        fallback_data_class="financial_aggregated", pipeline_stage="copy",
    ),
    "average_ticket_analysis": _task(
        "average_ticket_analysis", provider="deepseek", profile="deepseek_reasoning",
        data_class="financial_aggregated", response_kind="json", schema=AVERAGE_TICKET_ANALYSIS_SCHEMA,
        max_tokens=5000, temperature=0.0, timeout=45, shadow_allowed=True, pipeline_stage="analysis",
    ),
    "service_catalog_analysis": _task(
        "service_catalog_analysis", provider="deepseek", profile="deepseek_reasoning",
        response_kind="json", schema=SERVICE_CATALOG_ANALYSIS_SCHEMA,
        max_tokens=5000, temperature=0.0, timeout=45, shadow_allowed=True, pipeline_stage="analysis",
    ),
    "review_signal_classify": _task(
        "review_signal_classify", provider="deepseek", profile="deepseek_fast",
        response_kind="json", schema=REVIEW_SIGNAL_SCHEMA,
        max_tokens=2500, temperature=0.0, timeout=20, shadow_allowed=True, pipeline_stage="analysis",
    ),
    "review_signal_synthesis": _task(
        "review_signal_synthesis", provider="deepseek", profile="deepseek_reasoning",
        response_kind="json", schema=REVIEW_SIGNAL_SCHEMA,
        max_tokens=4000, temperature=0.0, timeout=45, shadow_allowed=True, pipeline_stage="analysis",
    ),
    "operator_intent_classify": _task(
        "operator_intent_classify",
        provider="deepseek",
        profile="deepseek_fast",
        response_kind="json",
        schema={
            "type": "object",
            "properties": {"intent": {"type": "string"}},
            "required": ["intent"],
        },
        max_tokens=500,
        temperature=0.0,
        timeout=20,
        shadow_allowed=True,
    ),
    "agent_compiler": _task(
        "agent_compiler",
        provider="deepseek",
        profile="deepseek_reasoning",
        response_kind="json",
        schema=AGENT_COMPILER_SCHEMA,
        max_tokens=5000,
        temperature=0.0,
        timeout=45,
        prompt_version="agent_compiler_v1",
        shadow_allowed=True,
    ),
    "agent_document_analysis": _task(
        "agent_document_analysis",
        provider="deepseek",
        profile="deepseek_reasoning",
        response_kind="json",
        schema=DOCUMENT_SCHEMA,
        max_tokens=5000,
        temperature=0.0,
        timeout=45,
        prompt_version="agent_document_analysis_v1",
        shadow_allowed=True,
    ),
    "agent_table_analysis": _task(
        "agent_table_analysis",
        provider="deepseek",
        profile="deepseek_fast",
        response_kind="json",
        schema=TABLE_SCHEMA,
        max_tokens=4000,
        temperature=0.0,
        timeout=20,
        prompt_version="agent_table_analysis_v1",
        shadow_allowed=True,
    ),
    "generic_russian_analysis": _task("generic_russian_analysis"),
}


def get_task_definition(task_key: str) -> LLMTaskDefinition | None:
    return TASK_REGISTRY.get(str(task_key or "").strip())


def list_task_definitions() -> list[LLMTaskDefinition]:
    return list(TASK_REGISTRY.values())


def model_for_definition(definition: LLMTaskDefinition) -> str:
    profiles = {
        "gigachat_default": os.getenv("GIGACHAT_MODEL", "GigaChat-Max"),
        "gigachat_max": os.getenv("GIGACHAT_MODEL_MAX", "GigaChat-Max"),
        "deepseek_fast": os.getenv("DEEPSEEK_MODEL_FAST", "deepseek-v4-flash"),
        "deepseek_reasoning": os.getenv("DEEPSEEK_MODEL_REASONING", "deepseek-v4-pro"),
    }
    return profiles.get(definition.model_profile, definition.model_profile)
