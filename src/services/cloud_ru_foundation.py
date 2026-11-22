"""Fail-closed OpenAI-compatible client for Cloud.ru Foundation Models."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from services.ai_spend_budget import guarded_post


DEFAULT_BASE_URL = "https://foundation-models.api.cloud.ru/v1"
DEFAULT_CHAT_MODEL = "ai-sage/GigaChat3-10B-A1.8B"
DEFAULT_EMBEDDING_MODEL = "ai-sage/Giga-Embeddings-instruct-3B"
DEFAULT_EMBEDDING_DIMENSIONS = 2048


class CloudRuConfigurationError(RuntimeError):
    """Raised before a provider request when Cloud.ru is not safely configured."""


def _enabled(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CloudRuConfig:
    api_key: str
    base_url: str
    chat_model: str
    embedding_model: str
    embedding_dimensions: int
    allow_external_models: bool

    @classmethod
    def from_env(cls) -> "CloudRuConfig":
        raw_dimensions = str(
            os.getenv("CLOUD_RU_EMBEDDING_DIMENSIONS") or DEFAULT_EMBEDDING_DIMENSIONS
        )
        try:
            dimensions = int(raw_dimensions)
        except ValueError as error:
            raise CloudRuConfigurationError("CLOUD_RU_EMBEDDING_DIMENSIONS_INVALID") from error
        if dimensions != DEFAULT_EMBEDDING_DIMENSIONS:
            raise CloudRuConfigurationError("CLOUD_RU_EMBEDDING_DIMENSIONS_UNSUPPORTED")
        return cls(
            api_key=str(os.getenv("CLOUD_RU_API_KEY") or "").strip(),
            base_url=str(os.getenv("CLOUD_RU_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
            chat_model=str(os.getenv("CLOUD_RU_CHAT_MODEL") or DEFAULT_CHAT_MODEL).strip(),
            embedding_model=str(
                os.getenv("CLOUD_RU_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
            ).strip(),
            embedding_dimensions=dimensions,
            allow_external_models=_enabled("CLOUD_RU_EXTERNAL_MODELS_ENABLED"),
        )

    def validate_model(self, model: str) -> None:
        clean = str(model or "").strip()
        if not clean:
            raise CloudRuConfigurationError("CLOUD_RU_MODEL_MISSING")
        if not self.allow_external_models and not clean.startswith("ai-sage/"):
            raise CloudRuConfigurationError("CLOUD_RU_EXTERNAL_MODEL_BLOCKED")


class CloudRuFoundationClient:
    provider = "cloudru"

    def __init__(self, config: CloudRuConfig | None = None) -> None:
        self.config = config or CloudRuConfig.from_env()

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            raise CloudRuConfigurationError("CLOUD_RU_API_KEY_MISSING")
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def list_models(self, *, timeout: int = 20) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self.config.base_url}/models",
            headers=self._headers(),
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data") if isinstance(payload, dict) else []
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    def embeddings(self, texts: list[str], *, timeout: int = 90) -> dict[str, Any]:
        if not texts:
            return {"vectors": [], "usage": 0, "request_id": "", "latency_ms": 0}
        model = self.config.embedding_model
        self.config.validate_model(model)
        headers = self._headers()
        body: dict[str, Any] = {"model": model, "input": texts, "max_tokens": 1}
        started = time.monotonic()
        response = guarded_post(
            lambda: requests.post(
                f"{self.config.base_url}/embeddings",
                headers=headers,
                json={"model": model, "input": texts},
                timeout=timeout,
            ),
            body,
            {"provider": "cloudru_embeddings", "task_key": "knowledge_embedding"},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data") if isinstance(payload, dict) else []
        ordered = sorted(
            [item for item in items if isinstance(item, dict)],
            key=lambda item: int(item.get("index") or 0),
        )
        vectors = [
            item.get("embedding")
            for item in ordered
            if isinstance(item.get("embedding"), list)
        ]
        if len(vectors) != len(texts):
            raise RuntimeError("CLOUD_RU_EMBEDDING_COUNT_MISMATCH")
        if any(len(vector) != self.config.embedding_dimensions for vector in vectors):
            raise RuntimeError("CLOUD_RU_EMBEDDING_DIMENSION_MISMATCH")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0)
        return {
            "vectors": vectors,
            "usage": prompt_tokens,
            "request_id": str(payload.get("id") or response.headers.get("x-request-id") or ""),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    def chat_completion(
        self,
        body: dict[str, Any],
        *,
        timeout: int,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model = str(body.get("model") or self.config.chat_model).strip()
        self.config.validate_model(model)
        headers = self._headers()
        request_body = {**body, "model": model}
        response = guarded_post(
            lambda: requests.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=request_body,
                timeout=timeout,
            ),
            request_body,
            {"provider": "cloudru", **(context or {})},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("CLOUD_RU_RESPONSE_INVALID")
        return payload
