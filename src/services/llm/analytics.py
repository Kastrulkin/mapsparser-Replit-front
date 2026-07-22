from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from services.llm import LLMTaskRequest, run_llm_shadow_task
from services.llm.policy import EMAIL_PATTERN, PHONE_PATTERN


PERSON_NAME_PATTERN = re.compile(
    r"\b(?:[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}|[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _opaque_id(value: Any) -> str:
    return hashlib.sha256(_clean(value).encode("utf-8")).hexdigest()[:20]


def _safe_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _service_payload(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in services:
        result.append(
            {
                "service_id": _clean(item.get("id")),
                "name": _clean(item.get("optimized_name") or item.get("name"))[:240],
                "category": _clean(item.get("category"))[:160],
                "price": _clean(item.get("price"))[:80],
            }
        )
    return result


def build_average_ticket_analysis_payload(
    kpis: dict[str, Any],
    services: list[dict[str, Any]],
) -> dict[str, Any]:
    allowed_metrics = (
        "average_ticket",
        "average_ticket_delta_30d",
        "add_on_rate",
        "upsell_conversion",
        "cross_sell_rate",
        "package_sales",
        "package_conversion",
        "upsell_revenue",
        "potential_growth",
        "average_ticket_with_upsell",
        "average_ticket_without_upsell",
    )
    metrics = {key: _safe_number(kpis.get(key)) for key in allowed_metrics}
    events = kpis.get("events") if isinstance(kpis.get("events"), dict) else {}
    metrics["events"] = {
        key: _safe_number(events.get(key))
        for key in ("offered", "bought", "declined", "package_offered", "package_bought")
    }
    categories = kpis.get("by_category") if isinstance(kpis.get("by_category"), list) else []
    metrics["by_category"] = [
        {
            "category": _clean(item.get("category"))[:160],
            "offered": _safe_number(item.get("offered")),
            "bought": _safe_number(item.get("bought")),
            "conversion": _safe_number(item.get("conversion")),
        }
        for item in categories
        if isinstance(item, dict)
    ]
    return {"calculated_metrics": metrics, "service_catalog": _service_payload(services)}


def build_service_catalog_analysis_payload(services: list[dict[str, Any]]) -> dict[str, Any]:
    return {"services": _service_payload(services)}


def _redact_review_text(value: Any) -> str:
    text = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", _clean(value))
    text = PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
    text = PERSON_NAME_PATTERN.sub("[NAME_REDACTED]", text)
    text = re.sub(r"https?://\S+", "[LINK_REDACTED]", text, flags=re.IGNORECASE)
    return text[:2000]


def redact_review_text(value: Any) -> str:
    return _redact_review_text(value)


def build_review_signal_payload(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "reviews": [
            {
                "review_id": _opaque_id(item.get("review_id") or item.get("id")),
                "rating": _safe_number(item.get("rating")),
                "source": _clean(item.get("source"))[:80],
                "text": _redact_review_text(item.get("text") or item.get("review_text")),
            }
            for item in reviews
            if isinstance(item, dict)
        ]
    }


def _queue(
    task_key: str,
    payload: dict[str, Any],
    *,
    business_id: str,
    user_id: str,
    pipeline_id: str,
) -> bool:
    prompt = (
        "Проанализируй только переданные обезличенные данные. Не пересчитывай и не изменяй "
        "значения calculated_metrics. Все выводы свяжи с входными идентификаторами и фактами. "
        "Верни строго JSON по заданной схеме.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    return run_llm_shadow_task(
        LLMTaskRequest(
            task_key=task_key,
            prompt=prompt,
            business_id=business_id,
            user_id=user_id,
            data_class="financial_aggregated" if task_key == "average_ticket_analysis" else "business_internal",
            usage_reference=f"llm-pipeline:{pipeline_id}",
            pipeline_id=pipeline_id,
            pipeline_stage="analysis",
        )
    )


def queue_average_ticket_analysis(
    kpis: dict[str, Any],
    services: list[dict[str, Any]],
    *,
    business_id: str,
    user_id: str,
    pipeline_id: str = "",
) -> str:
    current_pipeline_id = pipeline_id or str(uuid.uuid4())
    _queue(
        "average_ticket_analysis",
        build_average_ticket_analysis_payload(kpis, services),
        business_id=business_id,
        user_id=user_id,
        pipeline_id=current_pipeline_id,
    )
    return current_pipeline_id


def queue_service_catalog_analysis(
    services: list[dict[str, Any]],
    *,
    business_id: str,
    user_id: str,
    pipeline_id: str = "",
) -> str:
    current_pipeline_id = pipeline_id or str(uuid.uuid4())
    _queue(
        "service_catalog_analysis",
        build_service_catalog_analysis_payload(services),
        business_id=business_id,
        user_id=user_id,
        pipeline_id=current_pipeline_id,
    )
    return current_pipeline_id


def queue_review_signal_analysis(
    reviews: list[dict[str, Any]],
    *,
    business_id: str,
    user_id: str,
    pipeline_id: str = "",
) -> str:
    current_pipeline_id = pipeline_id or str(uuid.uuid4())
    payload = build_review_signal_payload(reviews)
    for task_key in ("review_signal_classify", "review_signal_synthesis"):
        _queue(
            task_key,
            payload,
            business_id=business_id,
            user_id=user_id,
            pipeline_id=current_pipeline_id,
        )
    return current_pipeline_id
