# Валидация результата парсинга: только то, что реально пришло из источника (Яндекс).
# Никаких подмешиваний из БД. Отсутствующие поля фиксируются в found/missing/warnings.

from typing import Any, Dict, List

SOURCE_YANDEX_BUSINESS = "yandex_business"

# Поля, без которых считаем парсинг провальным (STATUS_ERROR)
# Здесь one-of группа: title OR name OR overview.title
FIELDS_HARD = ["title_or_name"]

# Критичные поля: отсутствие → предупреждение (status=completed, error_message=warnings)
FIELDS_CRITICAL = ["address", "rating", "reviews_count", "categories"]

# Опциональные: только для учёта в coverage/quality_score
FIELDS_OPTIONAL = [
    "reviews",
    "news",
    "products",
    "phone",
    "site",
    "hours",
    "hours_full",
    "description",
    "photos",
    "rubric",
]


def _get_value(data: dict, key: str, overview: dict) -> Any:
    """Получить значение из data или из overview (как в worker)."""
    v = data.get(key)
    if v is not None and v != "":
        return v
    return overview.get(key)


def _has_content(value: Any) -> bool:
    """Есть ли осмысленное значение (не пустая строка, не пустой список для списков)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _resolve_categories(data: dict, overview: dict) -> Any:
    """
    categories/rubric считаем найденным, если:
      - categories: непустой список
      - categories: непустой объект (обычно словарь) — считаем найденным,
      - rubric: непустая строка
      - rubric: объект, где есть id/name
    """
    cat = data.get("categories", None)
    if cat is None:
        cat = overview.get("categories", None)

    # categories как список
    if isinstance(cat, list):
        if len(cat) > 0:
            return cat

    # categories как объект (часто словарь с id/name)
    if isinstance(cat, dict) and len(cat) > 0:
        return cat

    # rubric: строка или объект
    rub = data.get("rubric") or overview.get("rubric")
    if isinstance(rub, str) and rub.strip():
        return rub
    if isinstance(rub, dict):
        if any((rub.get("id"), rub.get("name"))):
            return rub

    return None


def _normalize_payload(payload: dict) -> None:
    """
    Приведение payload к плоской структуре. Мутирует payload.
    Защита от сырого API-ответа {"data": {"reviews": [...]}}.
    """
    if not isinstance(payload, dict):
        return
    inner = payload.get("data")
    if isinstance(inner, dict):
        if "reviews" in inner and "reviews" not in payload:
            payload["reviews"] = inner["reviews"]
        if "title" in inner and not payload.get("title"):
            payload["title"] = inner["title"]
        if "name" in inner and not payload.get("name"):
            payload["name"] = inner["name"]
    # Гарантируем title_or_name из доступных источников
    if not payload.get("title_or_name", "").strip():
        pt = payload.get("page_title") or ""
        if isinstance(pt, str):
            pt = pt.replace(" — Яндекс Карты", "").replace(" - Яндекс Карты", "").strip()
        else:
            pt = ""
        t = (
            payload.get("title")
            or payload.get("name")
            or (payload.get("overview") or {}).get("title") if isinstance(payload.get("overview"), dict) else None
            or pt
        )
        if t and str(t).strip():
            payload["title_or_name"] = str(t).strip()


def validate_parsed_payload(parsed_data: dict, source: str = SOURCE_YANDEX_BUSINESS) -> dict:
    """
    Проверяет наличие ключевых полей в результате парсинга.
    Не подмешивает данные из БД — только то, что в parsed_data.

    Returns:
        found_fields: list[str]
        missing_fields: list[str]
        warnings: list[str]  # пояснения по критичным отсутствующим
        hard_missing: list[str]  # отсутствующие HARD поля → статус ERROR
        quality_score: float 0..1 (доля найденных CRITICAL + HARD от общего числа таких полей)
    """
    if not isinstance(parsed_data, dict):
        return {
            "found_fields": [],
            "missing_fields": [],
            "warnings": ["payload is not a dict"],
            "hard_missing": ["title"],
            "quality_score": 0.0,
        }

    _normalize_payload(parsed_data)

    overview = parsed_data.get("overview") or {}
    if not isinstance(overview, dict):
        overview = {}

    found: List[str] = []
    missing: List[str] = []
    warnings: List[str] = []
    hard_missing: List[str] = []

    def check(field: str, value: Any, kind: str) -> None:
        if _has_content(value):
            found.append(field)
        else:
            missing.append(field)
            if kind == "hard":
                hard_missing.append(field)
            elif kind == "critical":
                warnings.append(f"missing_in_source:{field}")

    # HARD: one-of (title OR name OR overview.title OR title_or_name)
    title_val = (
        parsed_data.get("title_or_name")
        or _get_value(parsed_data, "title", overview)
        or parsed_data.get("name")
        or overview.get("title")
    )
    if _has_content(title_val):
        found.append("title_or_name")
        # Восстановить title_or_name в payload для последующего использования
        if not parsed_data.get("title_or_name") and isinstance(title_val, str):
            parsed_data["title_or_name"] = title_val.strip()
    else:
        missing.append("title_or_name")
        hard_missing.append("title_or_name")

    # CRITICAL
    address_val = _get_value(parsed_data, "address", overview)
    check("address", address_val, "critical")

    rating_val = _get_value(parsed_data, "rating", overview)
    check("rating", rating_val, "critical")

    reviews_count_val = _get_value(parsed_data, "reviews_count", overview)
    # 0 — допустимое значение (поле присутствует)
    if reviews_count_val is not None and reviews_count_val != "":
        try:
            if int(reviews_count_val) >= 0:
                found.append("reviews_count")
            else:
                missing.append("reviews_count")
                warnings.append("missing_in_source:reviews_count")
        except (TypeError, ValueError):
            missing.append("reviews_count")
            warnings.append("missing_in_source:reviews_count")
    else:
        missing.append("reviews_count")
        warnings.append("missing_in_source:reviews_count")

    categories_val = _resolve_categories(parsed_data, overview)
    check("categories", categories_val, "critical")

    # OPTIONAL (только для found/missing, не для hard/warnings)
    for field in FIELDS_OPTIONAL:
        val = _get_value(parsed_data, field, overview)
        if _has_content(val):
            found.append(field)
        else:
            missing.append(field)

    # quality_score: доля найденных среди (HARD + CRITICAL)
    required = set(FIELDS_HARD + FIELDS_CRITICAL)
    found_required = len([f for f in found if f in required])
    quality_score = found_required / len(required) if required else 1.0

    return {
        "found_fields": list(dict.fromkeys(found)),
        "missing_fields": list(dict.fromkeys(missing)),
        "warnings": warnings,
        "hard_missing": hard_missing,
        "quality_score": round(quality_score, 2),
    }


def build_parsing_meta(parsed_data: dict, validation: dict, source: str = SOURCE_YANDEX_BUSINESS) -> dict:
    """Собрать объект _meta для сохранения в cards (в overview)."""
    return {
        "source": source,
        "found_fields": validation.get("found_fields", []),
        "missing_fields": validation.get("missing_fields", []),
        "warnings": validation.get("warnings", []),
        "quality_score": validation.get("quality_score", 0.0),
    }
