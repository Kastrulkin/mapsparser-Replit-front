from __future__ import annotations

import json
import os
import threading

from services.llm.adapters import DeepSeekAdapter, GigaChatAdapter, _record_llm_usage
from services.llm.contracts import LLMTaskDefinition, LLMTaskRequest, LLMTaskResult
from services.llm.policy import most_restrictive_data_class, prepare_prompt_for_provider
from services.llm.registry import get_task_definition
from services.llm.schema import parse_json_value, validate_json_schema


def _positive_env_int(name: str, default: int) -> int:
    try:
        return max(1, int(str(os.getenv(name) or default)))
    except ValueError:
        return default


_SHADOW_SEMAPHORE = threading.BoundedSemaphore(
    _positive_env_int("LLM_SHADOW_MAX_CONCURRENCY", 4)
)


def _env_enabled(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return str(os.getenv(name, fallback) or fallback).strip().lower() in {"1", "true", "yes", "on"}


def _deepseek_business_allowed(business_id: str) -> bool:
    allowed = {
        item.strip()
        for item in str(os.getenv("LLM_DEEPSEEK_BUSINESS_IDS") or "").split(",")
        if item.strip()
    }
    return bool(business_id and business_id in allowed)


def _provider_for_request(definition: LLMTaskDefinition, request: LLMTaskRequest) -> str:
    if not _env_enabled("LLM_ROUTER_ENABLED"):
        return "gigachat"
    if definition.primary_provider != "deepseek":
        return definition.primary_provider
    if not _deepseek_business_allowed(request.business_id):
        return "gigachat"
    if _env_enabled("LLM_SHADOW_MODE") and definition.shadow_allowed:
        return "gigachat"
    return "deepseek"


def _adapter(provider: str) -> GigaChatAdapter | DeepSeekAdapter | None:
    if provider == "gigachat":
        return GigaChatAdapter()
    if provider == "deepseek":
        return DeepSeekAdapter()
    return None


def _validated_result(
    result: LLMTaskResult,
    request: LLMTaskRequest,
    definition: LLMTaskDefinition,
) -> LLMTaskResult:
    if result.status != "completed":
        return result
    schema = request.response_schema or definition.response_schema
    if definition.response_kind != "json" and not schema:
        if not result.content.strip():
            result.status = "empty_response"
            result.fallback_reason = "LLM_EMPTY_RESPONSE"
        return result
    parsed = parse_json_value(result.content)
    if parsed is None:
        result.status = "invalid_json"
        result.validation_errors = ["$: invalid JSON"]
        result.fallback_reason = "LLM_INVALID_JSON"
        return result
    errors = validate_json_schema(parsed, schema)
    result.parsed_data = parsed
    result.validation_errors = errors
    if errors:
        result.status = "schema_invalid"
        result.fallback_reason = "LLM_SCHEMA_INVALID"
    return result


def _generate_once(
    request: LLMTaskRequest,
    definition: LLMTaskDefinition,
    *,
    provider: str,
    prompt: str,
    shadow: bool = False,
    data_class_override: str = "",
) -> LLMTaskResult:
    decision = prepare_prompt_for_provider(
        prompt,
        provider=provider,
        data_class=(
            data_class_override
            or most_restrictive_data_class(definition.data_class, request.data_class)
        ),
    )
    if not decision.allowed:
        return LLMTaskResult(
            status="policy_blocked",
            provider=provider,
            fallback_reason=decision.reason_code,
            shadow=shadow,
        )
    selected = _adapter(provider)
    if selected is None:
        return LLMTaskResult(
            status="provider_unavailable",
            provider=provider,
            fallback_reason="LLM_PROVIDER_UNKNOWN",
            shadow=shadow,
        )
    return selected.generate(request, definition, prompt=decision.prompt, shadow=shadow)


def _run_shadow_request(
    request: LLMTaskRequest,
    definition: LLMTaskDefinition,
) -> None:
    try:
        result = _validated_result(
            _generate_once(
                request,
                definition,
                provider="deepseek",
                prompt=request.prompt,
                shadow=True,
            ),
            request,
            definition,
        )
        first_result = result
        correction_attempted = False
        if result.status in {"invalid_json", "schema_invalid"}:
            correction_attempted = True
            correction = (
                request.prompt
                + "\n\nИсправь только формат ответа. Верни валидный JSON без markdown.\n"
                + "Ошибки схемы: "
                + json.dumps(result.validation_errors, ensure_ascii=False)
            )
            corrected_result = _validated_result(
                _generate_once(
                    request,
                    definition,
                    provider="deepseek",
                    prompt=correction,
                    shadow=True,
                ),
                request,
                definition,
            )
            corrected_result.usage = _combined_usage(first_result, corrected_result)
            corrected_result.latency_ms += first_result.latency_ms
            result = corrected_result
            if result.status in {"invalid_json", "schema_invalid"}:
                result.status = "fallback_required"
                result.fallback_reason = "LLM_SCHEMA_RETRY_EXHAUSTED"
        _record_result(
            request,
            definition,
            result,
            correction_attempted=correction_attempted,
        )
    finally:
        release = getattr(_SHADOW_SEMAPHORE, "release", None)
        if release:
            release()


def _combined_usage(first: LLMTaskResult, second: LLMTaskResult) -> dict[str, int]:
    return {
        "prompt_tokens": int(first.usage.get("prompt_tokens") or 0) + int(second.usage.get("prompt_tokens") or 0),
        "completion_tokens": int(first.usage.get("completion_tokens") or 0) + int(second.usage.get("completion_tokens") or 0),
        "total_tokens": int(first.usage.get("total_tokens") or 0) + int(second.usage.get("total_tokens") or 0),
    }


def _usage_metadata(
    request: LLMTaskRequest,
    definition: LLMTaskDefinition,
    result: LLMTaskResult,
    *,
    correction_attempted: bool = False,
) -> dict[str, object]:
    return {
        "response_kind": definition.response_kind,
        "correction_attempted": correction_attempted,
        "validation_errors": result.validation_errors[:8],
        "pipeline_id": request.pipeline_id,
        "pipeline_stage": request.pipeline_stage or definition.pipeline_stage,
        "primary_provider": result.primary_provider or definition.primary_provider,
        "fallback_provider": result.fallback_provider,
        "primary_failure_reason": result.primary_failure_reason,
        "output_source": result.output_source or result.provider,
    }


def _record_result(
    request: LLMTaskRequest,
    definition: LLMTaskDefinition,
    result: LLMTaskResult,
    *,
    correction_attempted: bool = False,
) -> None:
    _record_llm_usage(
        request,
        result,
        prompt_version=request.prompt_version or definition.prompt_version,
        metadata=_usage_metadata(
            request,
            definition,
            result,
            correction_attempted=correction_attempted,
        ),
    )


def run_llm_shadow_task(request: LLMTaskRequest) -> bool:
    """Queue a DeepSeek-only comparison that cannot affect the user result."""
    definition = get_task_definition(request.task_key)
    should_run = bool(
        definition
        and definition.primary_provider == "deepseek"
        and definition.shadow_allowed
        and _env_enabled("LLM_ROUTER_ENABLED")
        and _env_enabled("LLM_SHADOW_MODE")
        and _deepseek_business_allowed(request.business_id)
    )
    if not should_run or not _SHADOW_SEMAPHORE.acquire(blocking=False):
        return False
    shadow_request = LLMTaskRequest(
        task_key=request.task_key,
        prompt=request.prompt,
        business_id=request.business_id,
        user_id=request.user_id,
        prompt_version=request.prompt_version,
        response_schema=request.response_schema,
        data_class=request.data_class,
        usage_reference=request.usage_reference,
        shadow=True,
        pipeline_id=request.pipeline_id,
        pipeline_stage=request.pipeline_stage,
        fallback_prompt=request.fallback_prompt,
    )
    try:
        threading.Thread(
            target=_run_shadow_request,
            args=(shadow_request, definition),
            name=f"llm-shadow-{request.task_key}",
            daemon=True,
        ).start()
        return True
    except Exception:
        _SHADOW_SEMAPHORE.release()
        return False


def run_llm_task(request: LLMTaskRequest) -> LLMTaskResult:
    definition = get_task_definition(request.task_key)
    if definition is None:
        return LLMTaskResult(
            status="task_blocked",
            fallback_reason="LLM_TASK_NOT_REGISTERED",
            shadow=request.shadow,
        )
    provider = _provider_for_request(definition, request)
    result = _validated_result(
        _generate_once(request, definition, provider=provider, prompt=request.prompt, shadow=request.shadow),
        request,
        definition,
    )
    first_result = result
    correction_attempted = False
    if result.status in {"invalid_json", "schema_invalid"}:
        correction_attempted = True
        correction = (
            request.prompt
            + "\n\nИсправь только формат ответа. Верни валидный JSON без markdown.\n"
            + "Ошибки схемы: "
            + json.dumps(result.validation_errors, ensure_ascii=False)
        )
        corrected_result = _validated_result(
            _generate_once(request, definition, provider=provider, prompt=correction, shadow=request.shadow),
            request,
            definition,
        )
        corrected_result.usage = _combined_usage(first_result, corrected_result)
        corrected_result.latency_ms += first_result.latency_ms
        result = corrected_result
        if result.status in {"invalid_json", "schema_invalid"}:
            result.status = "fallback_required"
            result.fallback_reason = "LLM_SCHEMA_RETRY_EXHAUSTED"

    result.primary_provider = provider
    result.output_source = result.provider
    should_fallback_to_deepseek = bool(
        definition.primary_provider == "gigachat"
        and provider == "gigachat"
        and definition.allow_text_fallback
        and result.status != "completed"
        and not request.shadow
        and (not definition.fallback_data_class or bool(request.fallback_prompt))
    )
    if should_fallback_to_deepseek:
        primary_failure_reason = result.fallback_reason or result.status
        result.primary_failure_reason = primary_failure_reason
        _record_result(
            request,
            definition,
            result,
            correction_attempted=correction_attempted,
        )
        fallback = _validated_result(
            _generate_once(
                request,
                definition,
                provider="deepseek",
                prompt=request.fallback_prompt or request.prompt,
                shadow=False,
                data_class_override=definition.fallback_data_class,
            ),
            request,
            definition,
        )
        fallback.primary_provider = "gigachat"
        fallback.fallback_provider = "deepseek"
        fallback.primary_failure_reason = primary_failure_reason
        fallback.output_source = "deepseek" if fallback.status == "completed" else "deterministic"
        if fallback.status != "completed":
            fallback.status = "fallback_required"
            fallback.fallback_reason = fallback.fallback_reason or "LLM_TEXT_FALLBACK_FAILED"
        _record_result(request, definition, fallback)
        result = fallback
    else:
        _record_result(
            request,
            definition,
            result,
            correction_attempted=correction_attempted,
        )

    should_shadow = bool(
        _env_enabled("LLM_ROUTER_ENABLED")
        and _env_enabled("LLM_SHADOW_MODE")
        and definition.primary_provider == "deepseek"
        and definition.shadow_allowed
        and _deepseek_business_allowed(request.business_id)
        and provider == "gigachat"
        and not request.shadow
    )
    if should_shadow:
        run_llm_shadow_task(request)
    return result


def analyze_text_with_gigachat(
    prompt: str,
    task_type: str | None = None,
    business_id: str | None = None,
    user_id: str | None = None,
    usage_reference: str | None = None,
    pipeline_id: str | None = None,
    pipeline_stage: str | None = None,
    fallback_prompt: str | None = None,
) -> str:
    result = run_llm_task(
        LLMTaskRequest(
            task_key=task_type or "generic_russian_analysis",
            prompt=prompt,
            business_id=business_id or "",
            user_id=user_id or "",
            usage_reference=usage_reference or "",
            pipeline_id=pipeline_id or "",
            pipeline_stage=pipeline_stage or "",
            fallback_prompt=fallback_prompt or "",
        )
    )
    if result.status != "completed":
        raise RuntimeError(result.fallback_reason or result.status)
    return result.content
