from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any

import requests
from services.llm.contracts import LLMTaskDefinition, LLMTaskRequest, LLMTaskResult
from services.llm.registry import model_for_definition


def _usage_dict(value: Any) -> dict[str, int]:
    usage = value if isinstance(value, dict) else {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
    }


def _record_llm_usage(
    request: LLMTaskRequest,
    result: LLMTaskResult,
    *,
    prompt_version: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not request.business_id and not request.user_id:
        return
    db = None
    try:
        from database_manager import DatabaseManager
        from psycopg2.extras import Json

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT to_regclass('public.tokenusage')")
        row = cursor.fetchone()
        table_name = row.get("to_regclass") if isinstance(row, dict) else (row[0] if row else None)
        if not table_name:
            return
        cursor.execute(
            """
            INSERT INTO tokenusage (
                id, business_id, user_id, task_type, model,
                prompt_tokens, completion_tokens, total_tokens, endpoint,
                provider, provider_request_id, latency_ms, request_status,
                prompt_version, shadow, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                request.business_id or None,
                request.user_id or None,
                request.task_key,
                result.model,
                int(result.usage.get("prompt_tokens") or 0),
                int(result.usage.get("completion_tokens") or 0),
                int(result.usage.get("total_tokens") or 0),
                request.usage_reference or "chat/completions",
                result.provider,
                result.provider_request_id or None,
                result.latency_ms,
                result.status,
                prompt_version,
                bool(result.shadow),
                Json(metadata or {}),
            ),
        )
        db.conn.commit()
    except Exception:
        return
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


class GigaChatAdapter:
    provider = "gigachat"

    def generate(
        self,
        request: LLMTaskRequest,
        definition: LLMTaskDefinition,
        *,
        prompt: str,
        shadow: bool = False,
    ) -> LLMTaskResult:
        from services.gigachat_client import get_gigachat_client
        from gigachat_config import get_gigachat_config

        started = time.monotonic()
        model = str(get_gigachat_config().get_model_config(task_type=request.task_key).get("model") or "")
        try:
            content, usage = get_gigachat_client().analyze_text(
                prompt,
                task_type=request.task_key,
                business_id=request.business_id or None,
                user_id=request.user_id or None,
                usage_reference=request.usage_reference or None,
                prompt_version=request.prompt_version or definition.prompt_version,
                shadow=shadow,
                record_usage=False,
            )
            result = LLMTaskResult(
                status="completed",
                content=str(content or ""),
                provider=self.provider,
                model=model,
                usage=_usage_dict(usage),
                latency_ms=int((time.monotonic() - started) * 1000),
                shadow=shadow,
            )
            return result
        except Exception:
            result = LLMTaskResult(
                status="provider_error",
                provider=self.provider,
                model=model,
                latency_ms=int((time.monotonic() - started) * 1000),
                fallback_reason="GIGACHAT_REQUEST_FAILED",
                shadow=shadow,
            )
            return result


class DeepSeekAdapter:
    provider = "deepseek"

    def __init__(self) -> None:
        self.api_key = str(os.getenv("DEEPSEEK_API_KEY") or "").strip()
        self.base_url = str(os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")

    def generate(
        self,
        request: LLMTaskRequest,
        definition: LLMTaskDefinition,
        *,
        prompt: str,
        shadow: bool = False,
    ) -> LLMTaskResult:
        model = (
            model_for_definition(definition)
            if definition.model_profile.startswith("deepseek_")
            else str(os.getenv("DEEPSEEK_MODEL_REASONING") or "deepseek-v4-pro")
        )
        if not self.api_key:
            result = LLMTaskResult(
                status="provider_unavailable",
                provider=self.provider,
                model=model,
                fallback_reason="DEEPSEEK_API_KEY_MISSING",
                shadow=shadow,
            )
            return result
        expects_json = bool(
            definition.response_kind == "json"
            or request.response_schema
            or definition.response_schema
        )
        effective_prompt = prompt
        if expects_json and "json" not in prompt.lower():
            effective_prompt = prompt + "\n\nReturn only a valid JSON object without markdown."
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": effective_prompt}],
            "temperature": definition.temperature,
            "max_tokens": definition.max_tokens,
        }
        if expects_json:
            body["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        last_error = ""
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=definition.timeout_seconds,
                )
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    last_error = f"HTTP_{response.status_code}"
                    time.sleep(0.4)
                    continue
                response.raise_for_status()
                payload = response.json()
                choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
                message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
                content = str(message.get("content") or "") if isinstance(message, dict) else ""
                result = LLMTaskResult(
                    status="completed" if content else "empty_response",
                    content=content,
                    provider=self.provider,
                    model=str(payload.get("model") or model),
                    usage=_usage_dict(payload.get("usage")),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    fallback_reason="" if content else "DEEPSEEK_EMPTY_RESPONSE",
                    shadow=shadow,
                    provider_request_id=str(payload.get("id") or ""),
                )
                return result
            except Exception:
                last_error = str(sys.exc_info()[1])[:240]
                if attempt == 0:
                    time.sleep(0.4)
        result = LLMTaskResult(
            status="provider_error",
            provider=self.provider,
            model=model,
            latency_ms=int((time.monotonic() - started) * 1000),
            fallback_reason="DEEPSEEK_REQUEST_FAILED",
            shadow=shadow,
        )
        return result
