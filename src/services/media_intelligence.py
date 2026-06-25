from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json


PHOTO_LIBRARY: dict[str, list[dict[str, str]]] = {
    "cultural_center": [
        {"key": "entrance", "label": "вход и вывеска"},
        {"key": "interior", "label": "зал и пространство"},
        {"key": "event", "label": "события"},
        {"key": "team", "label": "команда или ведущие"},
        {"key": "atmosphere", "label": "атмосфера вечера"},
        {"key": "process", "label": "подготовка и закулисье"},
    ],
    "beauty_salon": [
        {"key": "entrance", "label": "вход и вывеска"},
        {"key": "interior", "label": "интерьер"},
        {"key": "team", "label": "мастера"},
        {"key": "process", "label": "процесс процедуры"},
        {"key": "result", "label": "результат работы"},
        {"key": "before_after", "label": "до/после"},
        {"key": "product", "label": "косметика и материалы"},
    ],
    "kids_hair_salon": [
        {"key": "entrance", "label": "вход и вывеска"},
        {"key": "interior", "label": "интерьер"},
        {"key": "play_zone", "label": "игровая зона"},
        {"key": "team", "label": "мастер с ребёнком"},
        {"key": "process", "label": "процесс стрижки"},
        {"key": "result", "label": "готовая причёска"},
        {"key": "first_haircut", "label": "первая стрижка"},
        {"key": "parents", "label": "родители рядом"},
    ],
    "default": [
        {"key": "entrance", "label": "вход и вывеска"},
        {"key": "interior", "label": "пространство"},
        {"key": "team", "label": "команда"},
        {"key": "process", "label": "процесс работы"},
        {"key": "result", "label": "результат"},
        {"key": "product", "label": "продукт или услуга"},
    ],
}


PLATFORM_HINTS: dict[str, str] = {
    "instagram": "Лучше вертикальное эмоциональное фото: лицо, результат, атмосфера.",
    "telegram": "Можно использовать оригинал, главное чтобы фото помогало понять пост.",
    "vk": "Подойдёт универсальное или горизонтальное фото с понятным объектом.",
    "facebook": "Подойдёт универсальное или горизонтальное фото с понятным объектом.",
    "google_business": "Лучше фото, которое показывает место, услугу или результат без лишней обработки.",
    "yandex_maps": "Для карт лучше вход, интерьер, процесс, результат или понятное фото услуги.",
    "two_gis": "Для карт лучше вход, интерьер, процесс, результат или понятное фото услуги.",
}


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


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def detect_photo_library_key(business: dict[str, Any] | None) -> str:
    source = " ".join(
        [
            _clean_text((business or {}).get("name")),
            _clean_text((business or {}).get("business_type")),
            _clean_text((business or {}).get("industry")),
            _clean_text((business or {}).get("categories")),
        ]
    ).lower().replace("ё", "е")
    if any(token in source for token in ["детск", "ребен", "парикмах"]):
        return "kids_hair_salon"
    if any(token in source for token in ["салон", "красот", "бьюти", "beauty", "маникюр", "косметолог"]):
        return "beauty_salon"
    if any(token in source for token in ["культур", "театр", "концерт", "афиша", "каток", "стендап"]):
        return "cultural_center"
    return "default"


def load_business(cursor: Any, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, name, business_type, industry, categories, city, address
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone()) or {"id": business_id}


def upsert_photo_asset(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    original_url: str = "",
    source: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_url = _clean_text(original_url)
    if not clean_url:
        raise ValueError("original_url обязателен")
    cursor.execute(
        """
        SELECT id
        FROM photo_assets
        WHERE business_id = %s AND original_url = %s
        LIMIT 1
        """,
        (business_id, clean_url),
    )
    existing = _row_to_dict(cursor, cursor.fetchone())
    if existing:
        cursor.execute(
            """
            UPDATE photo_assets
            SET source = %s,
                metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s AND business_id = %s
            RETURNING *
            """,
            (_clean_text(source) or "manual", Json(metadata or {}), existing["id"], business_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO photo_assets (
                id, business_id, source, original_url, metadata_json, created_by, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING *
            """,
            (str(uuid.uuid4()), business_id, _clean_text(source) or "manual", clean_url, Json(metadata or {}), user_id),
        )
    return serialize_photo_asset(cursor, _row_to_dict(cursor, cursor.fetchone()) or {})


def list_photo_assets(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT *
        FROM photo_assets
        WHERE business_id = %s
        ORDER BY quality_score DESC, updated_at DESC
        LIMIT 200
        """,
        (business_id,),
    )
    return [serialize_photo_asset(cursor, _row_to_dict(cursor, row) or {}) for row in (cursor.fetchall() or [])]


def serialize_photo_asset(cursor: Any, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "business_id": row.get("business_id"),
        "source": row.get("source"),
        "original_url": row.get("original_url"),
        "category": row.get("category") or "unknown",
        "quality_score": int(row.get("quality_score") or 0),
        "freshness_score": int(row.get("freshness_score") or 0),
        "orientation": row.get("orientation") or "unknown",
        "people_count": int(row.get("people_count") or 0),
        "service_tags": _json_value(row.get("service_tags"), []),
        "suitable_platforms": _json_value(row.get("suitable_platforms"), []),
        "asset_version": int(row.get("asset_version") or 1),
        "metadata_json": _json_value(row.get("metadata_json"), {}),
        "last_used_at": row.get("last_used_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def build_photo_coverage(cursor: Any, business_id: str) -> dict[str, Any]:
    business = load_business(cursor, business_id)
    library_key = detect_photo_library_key(business)
    required = PHOTO_LIBRARY.get(library_key) or PHOTO_LIBRARY["default"]
    assets = list_photo_assets(cursor, business_id)
    categories = {str(asset.get("category") or "") for asset in assets if int(asset.get("quality_score") or 0) >= 35}
    covered = [item for item in required if item["key"] in categories]
    missing = [item for item in required if item["key"] not in categories]
    percent = int(round((len(covered) / max(len(required), 1)) * 100))
    return {
        "schema": "localos_photo_coverage_v1",
        "library_key": library_key,
        "library_label": _library_label(library_key),
        "coverage_percent": percent,
        "summary": f"Фото закрывают {percent}% визуальных задач.",
        "covered": covered,
        "missing": missing,
        "missing_text": "Не хватает: " + ", ".join(item["label"] for item in missing[:4]) if missing else "Основные визуальные задачи закрыты.",
        "total_assets": len(assets),
    }


def _library_label(key: str) -> str:
    labels = {
        "cultural_center": "культурный центр",
        "beauty_salon": "салон красоты",
        "kids_hair_salon": "детская парикмахерская",
        "default": "локальный бизнес",
    }
    return labels.get(key, "локальный бизнес")


def _goal_categories(goal: str, platforms: list[str]) -> list[str]:
    source = goal.lower().replace("ё", "е")
    categories: list[str] = []
    if any(token in source for token in ["анонс", "событ", "афиша", "напомин"]):
        categories.extend(["event", "atmosphere", "team", "interior"])
    if any(token in source for token in ["акц", "прода", "сертификат", "окна"]):
        categories.extend(["result", "before_after", "process", "team"])
    if any(token in source for token in ["совет", "faq", "познав", "эксперт"]):
        categories.extend(["process", "product", "team", "interior"])
    if "instagram" in platforms:
        categories.extend(["result", "before_after", "atmosphere", "process"])
    if "yandex_maps" in platforms or "two_gis" in platforms or "google_business" in platforms:
        categories.extend(["entrance", "interior", "result", "process"])
    categories.extend(["result", "process", "interior", "team", "entrance", "other"])
    return list(dict.fromkeys(categories))


def rank_photo_assets(assets: list[dict[str, Any]], *, goal: str, platforms: list[str]) -> list[dict[str, Any]]:
    preferred = _goal_categories(goal, platforms)
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        score = int(asset.get("quality_score") or 0) * 2 + int(asset.get("freshness_score") or 0)
        category = str(asset.get("category") or "")
        if category in preferred:
            score += max(0, 80 - preferred.index(category) * 8)
        suitable = [str(item) for item in asset.get("suitable_platforms") or []]
        score += len(set(suitable).intersection(platforms)) * 15
        if asset.get("last_used_at"):
            score -= 20
        item = dict(asset)
        item["rank_score"] = score
        item["why"] = _photo_why(item, platforms)
        ranked.append(item)
    return sorted(ranked, key=lambda item: int(item.get("rank_score") or 0), reverse=True)


def _photo_why(asset: dict[str, Any], platforms: list[str]) -> str:
    category = str(asset.get("category") or "фото")
    score = int(asset.get("quality_score") or 0)
    if score < 45:
        return "Фото можно использовать, но лучше заменить: качество выглядит слабым."
    if platforms:
        return f"Подходит под задачу публикации и каналы: {', '.join(platforms[:3])}."
    return f"Подходит как визуальный актив категории «{category}»."


def recommend_media_for_post(
    cursor: Any,
    *,
    business_id: str,
    content_plan_item_id: str,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, theme, goal, draft_text, content_type
        FROM contentplanitems
        WHERE id = %s
        LIMIT 1
        """,
        (content_plan_item_id,),
    )
    item = _row_to_dict(cursor, cursor.fetchone())
    if not item:
        raise ValueError("Публикация не найдена")
    cursor.execute(
        """
        SELECT platform
        FROM social_posts
        WHERE content_plan_item_id = %s
        ORDER BY platform
        """,
        (content_plan_item_id,),
    )
    platforms = [str((_row_to_dict(cursor, row) or {}).get("platform") or "") for row in (cursor.fetchall() or [])]
    platforms = [platform for platform in platforms if platform]
    goal = " ".join([_clean_text(item.get("theme")), _clean_text(item.get("goal")), _clean_text(item.get("content_type"))])
    assets = list_photo_assets(cursor, business_id)
    ranked = rank_photo_assets(assets, goal=goal, platforms=platforms)
    coverage = build_photo_coverage(cursor, business_id)
    hints = [PLATFORM_HINTS[key] for key in platforms if key in PLATFORM_HINTS]
    if ranked:
        best = ranked[0]
        status = "ready" if int(best.get("quality_score") or 0) >= 55 else "weak"
        title = "Фото подобрано" if status == "ready" else "Лучше заменить фото"
        message = best["why"]
    else:
        best = None
        status = "missing"
        title = "Фото не выбрано"
        missing = coverage.get("missing") or []
        if missing:
            message = "Что снять: " + ", ".join(item["label"] for item in missing[:3]) + "."
        else:
            message = "Добавьте фото, которое показывает результат, место или процесс."
    return {
        "schema": "localos_media_recommendation_v1",
        "status": status,
        "title": title,
        "message": message,
        "selected_asset": best,
        "alternatives": ranked[1:4],
        "coverage": coverage,
        "platform_hints": hints[:4],
    }


def record_photo_usage(
    cursor: Any,
    *,
    business_id: str,
    photo_asset_id: str,
    usage_type: str,
    target_id: str = "",
    target_platform: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO photo_asset_usage_events (
            id, photo_asset_id, business_id, usage_type, target_id, target_platform, metadata_json, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (str(uuid.uuid4()), photo_asset_id, business_id, usage_type, target_id or None, target_platform or None, Json(metadata or {})),
    )
    cursor.execute(
        """
        UPDATE photo_assets
        SET last_used_at = %s, updated_at = NOW()
        WHERE id = %s AND business_id = %s
        """,
        (datetime.now(timezone.utc), photo_asset_id, business_id),
    )
