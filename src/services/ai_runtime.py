from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import uuid
import urllib.request
import time
from typing import Any

from psycopg2.extras import Json

from services.gigachat_client import get_gigachat_client
from services.media_file_storage import load_media_file
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits


PHOTO_ANALYSIS_ACTION_KEY = "photo_analysis"
PHOTO_ANALYSIS_CREDITS = 2
VISION_PROVIDER = "gigachat_vision"
VISION_CAPABILITY = "vision_enabled"
PHOTO_ANALYSIS_MAX_ATTEMPTS = 3


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    columns = [col[0] for col in (getattr(cursor, "description", None) or [])]
    if isinstance(row, (list, tuple)) and columns:
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return None


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def is_capability_enabled(cursor: Any, business_id: str, capability: str) -> bool:
    cursor.execute(
        """
        SELECT enabled
        FROM ai_capability_settings
        WHERE business_id = %s AND capability = %s
        LIMIT 1
        """,
        (business_id, capability),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("enabled"))


def set_capability_enabled(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    capability: str,
    enabled: bool,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    setting_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO ai_capability_settings (
            id, business_id, capability, enabled, enabled_by, enabled_at, metadata_json, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END, %s, NOW(), NOW())
        ON CONFLICT (business_id, capability)
        DO UPDATE SET
            enabled = EXCLUDED.enabled,
            enabled_by = EXCLUDED.enabled_by,
            enabled_at = CASE WHEN EXCLUDED.enabled THEN NOW() ELSE NULL END,
            metadata_json = ai_capability_settings.metadata_json || EXCLUDED.metadata_json,
            updated_at = NOW()
        RETURNING id, business_id, capability, enabled, enabled_at, metadata_json
        """,
        (
            setting_id,
            business_id,
            capability,
            bool(enabled),
            user_id,
            bool(enabled),
            Json(metadata or {}),
        ),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    row["metadata_json"] = _json_value(row.get("metadata_json"), {})
    return row


def list_capability_settings(cursor: Any, business_id: str) -> dict[str, dict[str, Any]]:
    capabilities = [
        VISION_CAPABILITY,
        "image_processing_enabled",
        "image_generation_enabled",
        "document_enabled",
        "browser_enabled",
    ]
    cursor.execute(
        """
        SELECT capability, enabled, enabled_at, metadata_json
        FROM ai_capability_settings
        WHERE business_id = %s
        """,
        (business_id,),
    )
    rows = [_row_to_dict(cursor, row) or {} for row in (cursor.fetchall() or [])]
    indexed = {str(row.get("capability") or ""): row for row in rows}
    result: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        row = indexed.get(capability) or {}
        result[capability] = {
            "capability": capability,
            "enabled": bool(row.get("enabled")),
            "enabled_at": row.get("enabled_at"),
            "metadata_json": _json_value(row.get("metadata_json"), {}),
        }
    return result


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"raw_response": text[:1000], "quality_score": 40, "category": "other"}


def _download_image_as_base64(url: str) -> str:
    clean_url = str(url or "").strip()
    if not clean_url.startswith(("http://", "https://")):
        return ""
    req = urllib.request.Request(clean_url, headers={"User-Agent": "LocalOS Media Intelligence/1.0"})
    response = urllib.request.urlopen(req, timeout=20)
    try:
        data = response.read(10 * 1024 * 1024 + 1)
    finally:
        response.close()
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Фото слишком большое для анализа")
    return base64.b64encode(data).decode("ascii")


def _load_stored_image_as_base64(asset: dict[str, Any]) -> str:
    versions = _json_value(asset.get("versions_json"), {})
    original = versions.get("original") if isinstance(versions, dict) else {}
    storage_path = ""
    if isinstance(original, dict):
        storage_path = str(original.get("storage_path") or "").strip()
    if not storage_path:
        storage_path = str(asset.get("storage_key") or "").strip()
    if not storage_path:
        return ""
    data = load_media_file(storage_path)
    if data is None:
        return ""
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Фото слишком большое для анализа")
    return base64.b64encode(data).decode("ascii")


def _normalize_photo_analysis(parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    def int_between(value: Any, default: int, minimum: int = 0, maximum: int = 100) -> int:
        try:
            number = int(value)
        except Exception:
            number = default
        return max(minimum, min(number, maximum))

    def list_text(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text[:80])
        return result[:12]

    orientation = str(parsed.get("orientation") or "").strip().lower()
    if orientation not in {"vertical", "horizontal", "square", "unknown"}:
        orientation = "unknown"
    category = str(parsed.get("category") or "").strip().lower() or "other"
    category = re.sub(r"[^a-zа-я0-9_\\-]+", "_", category)[:80] or "other"
    quality_score = int_between(parsed.get("quality_score"), 50)
    freshness_score = int_between(parsed.get("freshness_score"), 70)
    people_count = int_between(parsed.get("people_count"), 0, 0, 100)
    suitable_platforms = list_text(parsed.get("suitable_platforms"))
    if not suitable_platforms:
        suitable_platforms = ["telegram", "vk", "google_business", "yandex_maps"]
    return {
        "schema": "localos_photo_analysis_v1",
        "category": category,
        "quality_score": quality_score,
        "freshness_score": freshness_score,
        "orientation": orientation,
        "people_count": people_count,
        "emotion": str(parsed.get("emotion") or "").strip()[:120],
        "service_tags": list_text(parsed.get("service_tags") or parsed.get("tags")),
        "suitable_platforms": suitable_platforms,
        "caption": str(parsed.get("caption") or "").strip()[:500],
        "why": str(parsed.get("why") or "").strip()[:700],
        "warnings": list_text(parsed.get("warnings")),
        "context": {
            "business_type": str(context.get("business_type") or "").strip()[:120],
            "goal": str(context.get("goal") or "").strip()[:160],
        },
    }


def _build_photo_prompt(context: dict[str, Any]) -> str:
    return f"""
Ты визуальный редактор LocalOS для локального бизнеса.
Проанализируй фото как контентный актив для карт и соцсетей.

Контекст бизнеса: {json.dumps(context, ensure_ascii=False)}

Верни только JSON:
{{
  "category": "entrance|interior|team|process|result|before_after|event|product|atmosphere|other",
  "quality_score": 0-100,
  "freshness_score": 0-100,
  "orientation": "vertical|horizontal|square|unknown",
  "people_count": 0,
  "emotion": "коротко",
  "service_tags": ["..."],
  "suitable_platforms": ["instagram","telegram","vk","google_business","yandex_maps","two_gis"],
  "caption": "что видно на фото",
  "why": "почему фото полезно или слабое",
  "warnings": ["что может мешать доверию"]
}}
""".strip()


def _load_cache(
    cursor: Any,
    *,
    provider: str,
    action_type: str,
    asset_id: str,
    asset_version: int,
    prompt_hash: str,
    context_hash: str,
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT result_json, usage_event_id
        FROM ai_runtime_cache
        WHERE provider = %s
          AND action_type = %s
          AND asset_id = %s
          AND asset_version = %s
          AND prompt_hash = %s
          AND context_hash = %s
        LIMIT 1
        """,
        (provider, action_type, asset_id, asset_version, prompt_hash, context_hash),
    )
    row = _row_to_dict(cursor, cursor.fetchone())
    if not row:
        return None
    result = _json_value(row.get("result_json"), {})
    result["cache_hit"] = True
    result["usage_event_id"] = row.get("usage_event_id")
    return result


def estimate_photo_analysis_credits(photo_count: Any) -> dict[str, Any]:
    try:
        count = int(photo_count or 0)
    except Exception:
        count = 0
    count = max(count, 0)
    return {
        "action_type": PHOTO_ANALYSIS_ACTION_KEY,
        "photo_count": count,
        "credits_per_photo": PHOTO_ANALYSIS_CREDITS,
        "estimated_credits": count * PHOTO_ANALYSIS_CREDITS,
        "rule": "photo_analysis = 2 credits per new photo analysis",
    }


def estimate_photo_analysis_economics(
    *,
    photo_count: Any,
    provider_total_cost: Any,
    credit_price: Any,
    multiplier: Any = 10,
) -> dict[str, Any]:
    credits = estimate_photo_analysis_credits(photo_count)
    try:
        provider_cost = float(provider_total_cost or 0)
    except Exception:
        provider_cost = 0.0
    try:
        one_credit_price = float(credit_price or 0)
    except Exception:
        one_credit_price = 0.0
    try:
        margin_multiplier = float(multiplier or 0)
    except Exception:
        margin_multiplier = 0.0
    count = int(credits["photo_count"])
    charged_credits = int(credits["estimated_credits"])
    revenue = charged_credits * one_credit_price
    target_min_revenue = provider_cost * margin_multiplier
    return {
        **credits,
        "provider_total_cost": provider_cost,
        "provider_cost_per_photo": provider_cost / count if count else 0,
        "credit_price": one_credit_price,
        "estimated_revenue": revenue,
        "target_min_revenue": target_min_revenue,
        "margin_ratio": revenue / provider_cost if provider_cost else None,
        "needs_meter_adjustment": bool(provider_cost and revenue < target_min_revenue),
    }


def _mark_photo_analysis_status(
    cursor: Any,
    *,
    business_id: str,
    asset_id: str,
    status: str,
    error: str = "",
    increment_attempts: bool = False,
    meta_storage_key: str = "",
) -> None:
    cursor.execute(
        f"""
        UPDATE photo_assets
        SET analysis_status = %s,
            analysis_error = %s,
            analysis_attempts = analysis_attempts + %s,
            last_analyzed_at = CASE WHEN %s THEN NOW() ELSE last_analyzed_at END,
            meta_storage_key = COALESCE(NULLIF(%s, ''), meta_storage_key),
            updated_at = NOW()
        WHERE id = %s AND business_id = %s
        """,
        (
            status,
            error or None,
            1 if increment_attempts else 0,
            status == "analyzed",
            meta_storage_key,
            asset_id,
            business_id,
        ),
    )


def _release_photo_analysis_reservation(
    cursor: Any,
    *,
    reservation: dict[str, Any],
    business_id: str,
    user_id: str,
    external_id: str,
) -> None:
    reservation_id = str(reservation.get("reservation_id") or "")
    if not reservation_id:
        return
    finalize_reserved_action_credits(
        cursor,
        reservation_id=reservation_id,
        business_id=business_id,
        user_id=user_id,
        finalization_mode="release",
        external_id=external_id,
    )


def _record_usage_event(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_type: str,
    provider: str,
    raw_units: int,
    raw_unit_type: str,
    estimated_credits: int,
    charged_credits: int,
    reservation_id: str | None,
    cache_hit: bool,
    metadata: dict[str, Any],
) -> str:
    usage_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO ai_usage_events (
            id, business_id, user_id, action_type, provider, raw_units, raw_unit_type,
            provider_cost, estimated_credits, charged_credits, reservation_id, cache_hit, metadata_json, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, NOW())
        """,
        (
            usage_id,
            business_id,
            user_id,
            action_type,
            provider,
            raw_units,
            raw_unit_type,
            estimated_credits,
            charged_credits,
            reservation_id,
            bool(cache_hit),
            Json(metadata),
        ),
    )
    return usage_id


def analyze_photo_runtime(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    asset_id: str,
    image_base64: str = "",
    image_url: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not is_capability_enabled(cursor, business_id, VISION_CAPABILITY):
        return {
            "success": False,
            "status": "vision_disabled",
            "message": "Работа с фотографиями выключена.",
            "next_action": "Включите интеллектуальную работу с фотографиями в настройках ИИ.",
        }

    clean_context = context or {}
    prompt = _build_photo_prompt(clean_context)
    prompt_hash = _stable_hash(prompt)
    context_hash = _stable_hash(clean_context)

    cursor.execute(
        """
        SELECT id, asset_version, original_url, storage_key, versions_json
        FROM photo_assets
        WHERE id = %s AND business_id = %s
        LIMIT 1
        """,
        (asset_id, business_id),
    )
    asset = _row_to_dict(cursor, cursor.fetchone())
    if not asset:
        return {"success": False, "status": "asset_not_found", "message": "Фото не найдено."}
    asset_version = int(asset.get("asset_version") or 1)
    cached = _load_cache(
        cursor,
        provider=VISION_PROVIDER,
        action_type=PHOTO_ANALYSIS_ACTION_KEY,
        asset_id=asset_id,
        asset_version=asset_version,
        prompt_hash=prompt_hash,
        context_hash=context_hash,
    )
    if cached:
        _record_usage_event(
            cursor,
            business_id=business_id,
            user_id=user_id,
            action_type=PHOTO_ANALYSIS_ACTION_KEY,
            provider=VISION_PROVIDER,
            raw_units=0,
            raw_unit_type="cache_hit",
            estimated_credits=0,
            charged_credits=0,
            reservation_id=None,
            cache_hit=True,
            metadata={"asset_id": asset_id, "source_usage_event_id": cached.get("usage_event_id")},
        )
        return {"success": True, "status": "cached", "analysis": cached, "charged_credits": 0}

    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=PHOTO_ANALYSIS_ACTION_KEY,
        estimated_credits=PHOTO_ANALYSIS_CREDITS,
        idempotency_key=_stable_hash(["photo_analysis", business_id, user_id, asset_id, asset_version, prompt_hash, context_hash]),
        metadata={"asset_id": asset_id, "provider": VISION_PROVIDER},
    )
    if reservation.get("status") != "reserved":
        return {
            "success": False,
            "status": "insufficient_credits",
            "message": "Недостаточно кредитов для анализа фото.",
            "details": reservation,
        }

    clean_image_base64 = str(image_base64 or "").strip()
    try:
        if not clean_image_base64:
            clean_image_base64 = _load_stored_image_as_base64(asset)
        if not clean_image_base64:
            clean_image_base64 = _download_image_as_base64(image_url or asset.get("original_url") or "")
    except Exception:
        _release_photo_analysis_reservation(
            cursor,
            reservation=reservation,
            business_id=business_id,
            user_id=user_id,
            external_id=f"photo-analysis-download-failed:{asset_id}:{asset_version}",
        )
        message = str(sys.exc_info()[1])[:500] or "Не удалось загрузить фото."
        _mark_photo_analysis_status(
            cursor,
            business_id=business_id,
            asset_id=asset_id,
            status="analysis_failed",
            error=message,
        )
        return {
            "success": False,
            "status": "analysis_failed",
            "message": "Не удалось автоматически проанализировать фотографию.",
            "retry_available": True,
            "charged_credits": 0,
            "details": message,
        }
    if not clean_image_base64:
        _release_photo_analysis_reservation(
            cursor,
            reservation=reservation,
            business_id=business_id,
            user_id=user_id,
            external_id=f"photo-analysis-empty:{asset_id}:{asset_version}",
        )
        return {"success": False, "status": "image_required", "message": "Нужен файл или URL фото для анализа."}

    client = get_gigachat_client()
    response_text = ""
    last_error = ""
    for attempt in range(1, PHOTO_ANALYSIS_MAX_ATTEMPTS + 1):
        try:
            response_text = client.analyze_screenshot(
                clean_image_base64,
                prompt,
                task_type="ai_agent_marketing",
                business_id=business_id,
                user_id=user_id,
            )
            last_error = ""
            break
        except Exception:
            last_error = str(sys.exc_info()[1])[:500] or "VisionProvider error"
            if attempt < PHOTO_ANALYSIS_MAX_ATTEMPTS:
                time.sleep(0.2 * attempt)
    if last_error:
        _release_photo_analysis_reservation(
            cursor,
            reservation=reservation,
            business_id=business_id,
            user_id=user_id,
            external_id=f"photo-analysis-provider-failed:{asset_id}:{asset_version}",
        )
        _mark_photo_analysis_status(
            cursor,
            business_id=business_id,
            asset_id=asset_id,
            status="analysis_failed",
            error=last_error,
            increment_attempts=True,
        )
        return {
            "success": False,
            "status": "analysis_failed",
            "message": "Не удалось автоматически проанализировать фотографию.",
            "retry_available": True,
            "attempts": PHOTO_ANALYSIS_MAX_ATTEMPTS,
            "charged_credits": 0,
        }
    analysis = _normalize_photo_analysis(_extract_json_object(response_text), clean_context)
    usage_event_id = _record_usage_event(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_type=PHOTO_ANALYSIS_ACTION_KEY,
        provider=VISION_PROVIDER,
        raw_units=1,
        raw_unit_type="image",
        estimated_credits=PHOTO_ANALYSIS_CREDITS,
        charged_credits=PHOTO_ANALYSIS_CREDITS,
        reservation_id=str(reservation.get("reservation_id") or ""),
        cache_hit=False,
        metadata={"asset_id": asset_id, "asset_version": asset_version},
    )
    finalize_reserved_action_credits(
        cursor,
        reservation_id=str(reservation.get("reservation_id") or ""),
        business_id=business_id,
        user_id=user_id,
        actual_credits=PHOTO_ANALYSIS_CREDITS,
        finalization_mode="charge",
        external_id=f"photo-analysis:{asset_id}:{asset_version}:{usage_event_id}",
    )
    cursor.execute(
        """
        UPDATE photo_assets
        SET metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s::jsonb,
            analysis_status = 'analyzed',
            analysis_error = NULL,
            analysis_attempts = analysis_attempts + 1,
            last_analyzed_at = NOW(),
            meta_storage_key = %s,
            category = %s,
            quality_score = %s,
            freshness_score = %s,
            orientation = %s,
            people_count = %s,
            service_tags = %s,
            suitable_platforms = %s,
            updated_at = NOW()
        WHERE id = %s AND business_id = %s
        """,
        (
            Json({"analysis": analysis}),
            f"businesses/{business_id}/media/meta/{asset_id}/v{asset_version}/photo.meta.json",
            analysis["category"],
            analysis["quality_score"],
            analysis["freshness_score"],
            analysis["orientation"],
            analysis["people_count"],
            Json(analysis["service_tags"]),
            Json(analysis["suitable_platforms"]),
            asset_id,
            business_id,
        ),
    )
    cache_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO ai_runtime_cache (
            id, provider, action_type, asset_id, asset_version, prompt_hash, context_hash,
            result_json, usage_event_id, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (provider, action_type, asset_id, asset_version, prompt_hash, context_hash)
        DO UPDATE SET result_json = EXCLUDED.result_json, usage_event_id = EXCLUDED.usage_event_id, updated_at = NOW()
        """,
        (
            cache_id,
            VISION_PROVIDER,
            PHOTO_ANALYSIS_ACTION_KEY,
            asset_id,
            asset_version,
            prompt_hash,
            context_hash,
            Json(analysis),
            usage_event_id,
        ),
    )
    return {"success": True, "status": "analyzed", "analysis": analysis, "charged_credits": PHOTO_ANALYSIS_CREDITS}
