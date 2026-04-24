"""Shared SEO keyword selection/ranking logic for API and prompt generation."""

from __future__ import annotations

import re
from typing import Any


STOP_WORDS = {
    "и", "в", "на", "с", "по", "для", "или", "от", "до", "под", "при", "за", "к", "из", "о",
    "the", "and", "for", "with", "from", "to", "of", "a", "an",
    "услуга", "услуги", "service", "services",
    "курс", "курсы", "центр", "студия", "занятие", "занятия", "обучение", "урок", "уроки",
    "базовый", "базовые", "современные", "дети", "детский", "школьник", "школьники",
}

BEAUTY_BUSINESS_TYPES = {
    "beauty_salon", "barbershop", "nail_studio", "spa", "massage", "cosmetology", "brows_lashes", "makeup", "tanning"
}
BEAUTY_CATEGORIES = {"barber", "cosmetology", "eyebrows", "nails", "spa", "beauty", "hair", "makeup", "lashes"}
BEAUTY_TERMS = {
    "маникюр", "педикюр", "ногти", "ногт", "барбер", "косметолог", "ресниц", "бров", "спа", "стрижк", "окрашив",
    "эпиляц", "биоревитал", "мезотерап", "гель лак", "гел лак", "мелирован", "наращиван",
    "парикмахер", "hair", "lash", "nail",
}

BUSINESS_TYPE_HINTS = {
    "beauty_salon": ["салон красоты", "косметология", "маникюр", "педикюр", "парикмахерская"],
    "barbershop": ["барбершоп", "мужская стрижка", "борода", "бритье"],
    "nail_studio": ["маникюр", "педикюр", "ногти", "гель лак"],
    "spa": ["спа", "массаж", "релакс", "уход за телом"],
    "massage": ["массаж", "релакс", "лечебный массаж"],
    "cosmetology": ["косметология", "чистка лица", "пилинг", "уход за лицом"],
    "brows_lashes": ["брови", "ресницы", "ламинирование ресниц"],
    "auto_service": ["автосервис", "сто", "ремонт авто", "диагностика авто", "техобслуживание"],
    "gas_station": [
        "азс",
        "азс рядом",
        "заправка",
        "заправка рядом",
        "заправка на карте",
        "круглосуточная азс",
        "бензин",
        "бензин 92",
        "бензин 95",
        "дизель",
        "дт",
        "топливо",
        "цены на бензин",
        "цены на дизель",
        "заправиться рядом",
    ],
    "cafe": ["кафе", "кофе", "обед", "завтрак", "доставка еды"],
    "school": ["школа", "обучение", "курсы", "уроки", "дети"],
    "workshop": ["мастерская", "ремонт", "изготовление", "срочный ремонт"],
    "shoe_repair": ["ремонт обуви", "обувная мастерская", "набойки", "растяжка обуви"],
    "gym": ["спортзал", "фитнес", "тренировки", "тренажерный зал"],
    "shawarma": ["шаверма", "шаурма", "быстрое питание", "фастфуд"],
    "theater": ["театр", "спектакль", "сцена", "билеты"],
}


def _row_get(row: Any, key: str, idx: int = 0, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            pass
    if isinstance(row, (tuple, list)):
        return row[idx] if len(row) > idx else default
    return default


def extract_terms(text: str) -> list[str]:
    terms = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", (text or "").lower())
    out: list[str] = []
    for term in terms:
        if len(term) < 3 or term in STOP_WORDS or term.isdigit():
            continue
        out.append(term)
    return out


def is_beauty_keyword(keyword_text: str, category: str = "") -> bool:
    category_l = (category or "").strip().lower()
    if category_l in BEAUTY_CATEGORIES:
        return True
    keyword_l = (keyword_text or "").lower()
    normalized = keyword_l.replace("-", " ")
    return any(term in normalized for term in BEAUTY_TERMS)


def _score_keyword(keyword_text: str, terms: list[str], long_weight: int, short_weight: int) -> int:
    text = (keyword_text or "").lower()
    score = 0
    for term in terms:
        if term in text:
            score += long_weight if len(term) >= 6 else short_weight
    return score


def collect_ranked_keywords(
    cursor: Any,
    business_id: str | None,
    user_id: str | None,
    *,
    service_name: str | None = None,
    service_description: str | None = None,
    limit: int = 600,
    add_city_suffix: bool = False,
    fallback_global_when_empty_terms: bool = False,
    long_weight: int = 2,
    short_weight: int = 1,
    include_negative_blocked: bool = False,
) -> dict[str, Any]:
    """Collect and rank Wordstat keywords by business context.

    Returns dict with:
    - items: list[dict]
    - grouped: dict[str, list[dict]]
    - city: str
    - business_type: str
    """
    try:
        cursor.execute("SELECT to_regclass('public.wordstatkeywords')")
        reg_row = cursor.fetchone()
        reg_val = _row_get(reg_row, "to_regclass", 0, None)
        if not reg_val:
            return {"items": [], "grouped": {}, "city": "", "business_type": ""}
    except Exception:
        return {"items": [], "grouped": {}, "city": "", "business_type": ""}

    terms: list[str] = []
    city = ""
    business_type = ""

    if business_id:
        try:
            cursor.execute("SELECT city, business_type FROM businesses WHERE id = %s", (business_id,))
            business_row = cursor.fetchone()
            city = (_row_get(business_row, "city", 0, "") or "").strip()
            business_type = (_row_get(business_row, "business_type", 1, "") or "").strip()

            if business_type:
                cursor.execute(
                    "SELECT label, description FROM businesstypes WHERE type_key = %s OR id = %s LIMIT 1",
                    (business_type, business_type),
                )
                bt_row = cursor.fetchone()
                terms.extend(extract_terms(_row_get(bt_row, "label", 0, "") or ""))
                terms.extend(extract_terms(_row_get(bt_row, "description", 1, "") or ""))
        except Exception:
            pass

    if service_name or service_description:
        terms.extend(extract_terms(service_name or ""))
        terms.extend(extract_terms(service_description or ""))
    else:
        try:
            if business_id:
                cursor.execute(
                    """
                    WITH latest_ts AS (
                        SELECT MAX(updated_at) AS ts
                        FROM userservices
                        WHERE business_id = %s
                          AND source IN ('yandex_maps', 'yandex_business')
                          AND (is_active IS TRUE OR is_active IS NULL)
                    )
                    SELECT name, description
                    FROM userservices
                    WHERE business_id = %s
                      AND (is_active IS TRUE OR is_active IS NULL)
                      AND (
                          updated_at = (SELECT ts FROM latest_ts)
                          OR source IS NULL
                      )
                    """,
                    (business_id, business_id),
                )
            elif user_id:
                cursor.execute(
                    """
                    SELECT name, description
                    FROM userservices
                    WHERE user_id = %s
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 600
                    """,
                    (user_id,),
                )
            else:
                cursor.execute("SELECT '' AS name, '' AS description WHERE FALSE")
            for row in cursor.fetchall() or []:
                terms.extend(extract_terms(_row_get(row, "name", 0, "") or ""))
                terms.extend(extract_terms(_row_get(row, "description", 1, "") or ""))
        except Exception:
            pass

    if business_type:
        terms.extend(extract_terms(business_type))
        for hint in BUSINESS_TYPE_HINTS.get(str(business_type), []):
            terms.extend(extract_terms(hint))

    try:
        cursor.execute(
            """
            SELECT keyword, views, category, updated_at
            FROM wordstatkeywords
            ORDER BY views DESC NULLS LAST
            LIMIT 5000
            """
        )
        rows = cursor.fetchall() or []
        keywords = [
            {
                "keyword": _row_get(row, "keyword", 0, "") or "",
                "views": int(_row_get(row, "views", 1, 0) or 0),
                "category": _row_get(row, "category", 2, "") or "",
                "updated_at": _row_get(row, "updated_at", 3, None),
            }
            for row in rows
        ]
    except Exception:
        return {"items": [], "grouped": {}, "city": city, "business_type": business_type}

    excluded_keywords: set[str] = set()
    if business_id:
        try:
            cursor.execute("SELECT keyword FROM wordstatkeywordsexcluded WHERE business_id = %s", (business_id,))
            for row in cursor.fetchall() or []:
                kw = str(_row_get(row, "keyword", 0, "") or "").strip().lower()
                if kw:
                    excluded_keywords.add(kw)
        except Exception:
            pass

    if excluded_keywords:
        keywords = [k for k in keywords if (k.get("keyword") or "").strip().lower() not in excluded_keywords]

    if business_id:
        try:
            cursor.execute(
                """
                SELECT keyword, views, category, updated_at
                FROM wordstatkeywordscustom
                WHERE business_id = %s
                ORDER BY views DESC, updated_at DESC
                """,
                (business_id,),
            )
            custom_rows = cursor.fetchall() or []
            custom_items = [
                {
                    "keyword": _row_get(row, "keyword", 0, "") or "",
                    "views": int(_row_get(row, "views", 1, 0) or 0),
                    "category": _row_get(row, "category", 2, "") or "",
                    "updated_at": _row_get(row, "updated_at", 3, None),
                }
                for row in custom_rows
            ]
            if excluded_keywords:
                custom_items = [k for k in custom_items if (k.get("keyword") or "").strip().lower() not in excluded_keywords]
            existing = {(k.get("keyword") or "").strip().lower() for k in keywords}
            for item in custom_items:
                kw = (item.get("keyword") or "").strip().lower()
                if kw and kw not in existing:
                    keywords.append(item)
                    existing.add(kw)
        except Exception:
            pass

    business_type_l = str(business_type).strip().lower()
    if business_type_l and business_type_l not in BEAUTY_BUSINESS_TYPES:
        keywords = [
            k for k in keywords
            if not is_beauty_keyword(k.get("keyword") or "", k.get("category") or "")
        ]

    negative_global: list[str] = []
    negative_by_category: dict[str, list[str]] = {}
    if business_id:
        try:
            cursor.execute(
                """
                SELECT phrase, scope, category
                FROM seonegativekeywords
                WHERE business_id = %s
                  AND is_active IS TRUE
                ORDER BY created_at DESC
                """,
                (business_id,),
            )
            for row in cursor.fetchall() or []:
                phrase = str(_row_get(row, "phrase", 0, "") or "").strip().lower()
                if not phrase:
                    continue
                scope = str(_row_get(row, "scope", 1, "global") or "global").strip().lower()
                category = str(_row_get(row, "category", 2, "") or "").strip().lower()
                if scope == "category" and category:
                    negative_by_category.setdefault(category, []).append(phrase)
                else:
                    negative_global.append(phrase)
        except Exception:
            pass

    def _negative_reason(keyword_item: dict[str, Any]) -> str | None:
        kw = str(keyword_item.get("keyword") or "").strip().lower()
        if not kw:
            return None
        category = str(keyword_item.get("category") or "").strip().lower()
        for phrase in negative_global:
            if phrase and phrase in kw:
                return f"global:{phrase}"
        for phrase in negative_by_category.get(category, []):
            if phrase and phrase in kw:
                return f"category:{category}:{phrase}"
        return None

    if negative_global or negative_by_category:
        filtered: list[dict[str, Any]] = []
        for item in keywords:
            reason = _negative_reason(item)
            if reason:
                if include_negative_blocked:
                    item["negative_blocked"] = True
                    item["negative_reason"] = reason
                    filtered.append(item)
                continue
            item["negative_blocked"] = False
            item["negative_reason"] = ""
            filtered.append(item)
        keywords = filtered

    uniq_terms = list(dict.fromkeys(terms))[:80]
    if uniq_terms:
        filtered = []
        city_l = (city or "").strip().lower()
        for keyword_item in keywords:
            kw = keyword_item.get("keyword") or ""
            score = _score_keyword(kw, uniq_terms, long_weight=long_weight, short_weight=short_weight)
            kw_l = kw.lower()
            strong_term_match = any((len(term) >= 5 and term in kw_l) for term in uniq_terms)
            if city_l and city_l in kw.lower():
                score += 1
            if score > 0 and strong_term_match:
                keyword_item["match_score"] = score
                filtered.append(keyword_item)
        filtered.sort(key=lambda x: (int(x.get("views") or 0), x.get("match_score", 0)), reverse=True)
        keywords = filtered[:limit]
    else:
        keywords = keywords[:limit] if fallback_global_when_empty_terms else ([] if business_id else keywords[:limit])

    keywords.sort(key=lambda x: int(x.get("views") or 0), reverse=True)

    if add_city_suffix and city:
        city_clean = str(city).strip()
        for keyword_item in keywords:
            kw = (keyword_item.get("keyword") or "").strip()
            if city_clean and city_clean.lower() not in kw.lower():
                keyword_item["keyword_with_city"] = f"{kw} {city_clean}"
            else:
                keyword_item["keyword_with_city"] = kw

    grouped: dict[str, list[dict[str, Any]]] = {}
    for keyword_item in keywords:
        category = (keyword_item.get("category") or "other").strip() or "other"
        grouped.setdefault(category, []).append(keyword_item)

    return {"items": keywords, "grouped": grouped, "city": city, "business_type": business_type}
