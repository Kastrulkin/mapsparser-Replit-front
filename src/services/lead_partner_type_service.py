"""Canonical partner-type classification for prospecting leads.

Raw provider categories stay untouched in ``prospectingleads.category``.  This
module owns the stable product grouping used by API responses, UI filters, and
bulk outreach preparation.
"""

from __future__ import annotations

import re
from typing import Any


PARTNER_TYPE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("residential", "ЖК и апарт-комплексы"),
    ("dentistry", "Стоматологии"),
    ("medicine", "Медицина и клиники"),
    ("sport", "Фитнес и спорт"),
    ("food", "Кафе и рестораны"),
    ("photo_events", "Фото и мероприятия"),
    ("pets", "Ветеринария и зоотовары"),
    ("beauty", "Красота и уход"),
    ("children_retail", "Детские товары и одежда"),
    ("children_education", "Детские сады и обучение"),
    ("children_leisure", "Детский досуг и культура"),
    ("commercial_centers", "Бизнес- и торговые центры"),
    ("retail", "Другие магазины"),
    ("other", "Прочие партнёры"),
)

PARTNER_TYPE_LABELS = dict(PARTNER_TYPE_DEFINITIONS)
PARTNER_TYPE_IDS = frozenset(PARTNER_TYPE_LABELS)


def _normalized_category(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def _includes_any(category: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in category for keyword in keywords)


def _includes_standalone(category: str, keyword: str) -> bool:
    return re.search(
        rf"(?<![0-9a-zа-я]){re.escape(keyword)}(?![0-9a-zа-я])",
        category,
    ) is not None


def partner_types_for_category(value: Any) -> tuple[str, ...]:
    """Return every canonical category supported by a provider category.

    Map providers often return several categories for one company.  Keeping all
    matching canonical categories lets the leads registry answer practical
    completeness questions: a medical centre with cosmetology remains visible
    both under medicine and under beauty.
    """
    category = _normalized_category(value)
    if not category:
        return ("other",)

    matches: list[str] = []

    def add(partner_type: str, matched: bool) -> None:
        if matched and partner_type not in matches:
            matches.append(partner_type)

    add(
        "residential",
        _includes_any(category, ("жилой комплекс", "жилые комплексы", "апарт-отель", "апартаменты", "жк")),
    )
    add("pets", _includes_any(category, ("ветерин", "ветклиник", "зоомагазин", "кинолог", "питом", "амуници")))
    add("dentistry", _includes_any(category, ("стоматолог", "зуботех", "dental")))
    add(
        "medicine",
        _includes_any(category, ("медицин", "медцентр", "клиник", "диагност", "коррекция зрения", "поликлиник")),
    )
    add("sport", _includes_any(category, ("фитнес", "спорт", "секци", "бассейн", "единоборств", "танц", "йог", "каток", "скалолаз")))
    add(
        "food",
        _includes_any(category, ("ресторан", "кафе", "кофе", "столов", "быстрое питание", "доставка еды"))
        or _includes_standalone(category, "бар"),
    )
    add("photo_events", _includes_any(category, ("фотостуд", "фотоуслуг", "видеосъем", "мероприят", "праздник", "свадеб")))
    add(
        "beauty",
        _includes_any(
            category,
            (
                "beauty", "бьюти", "красот", "космет", "парфюм", "spa", "wellness",
                "массаж", "ногт", "парикмахер", "барбершоп", "эпиляц", "шугаринг",
                "бров", "ресниц", "перманент", "стилист", "солярий", "подолог",
            ),
        ),
    )
    children_retail = (
        _includes_any(category, ("детск", "ребен", "ребенок"))
        and _includes_any(category, ("магазин", "одеж", "обув", "товар", "игруш", "питание", "коляск", "мебель", "бутик"))
    )
    add("children_retail", children_retail)
    add("children_education", _includes_any(category, ("детский сад", "ясли", "центр развития", "школа", "обучен", "образован", "логопед", "дефектолог", "репетитор", "курсы", "музыкаль")))
    add("children_leisure", _includes_any(category, ("досуг", "развлекатель", "игров", "аттракцион", "театр", "музей", "зоопарк", "экскурси", "мастерская", "город профессий")))
    add("commercial_centers", _includes_any(category, ("бизнес-центр", "торговый комплекс", "торговый центр")))
    add("retail", not children_retail and _includes_any(category, ("магазин", "бутик", "торгов")))
    return tuple(matches or ["other"])


def partner_type_for_category(value: Any) -> str:
    """Return the primary stable product type for compatibility.

    Precedence is intentional.  A mixed ``медицинский центр / косметология``
    category is medicine; a mixed medical/dentistry category is dentistry.
    Filtering and completeness checks should use ``partner_types_for_category``
    so a company is not lost from its secondary category.
    """
    return partner_types_for_category(value)[0]


def partner_type_label(partner_type: Any) -> str:
    normalized = str(partner_type or "").strip()
    return PARTNER_TYPE_LABELS.get(normalized, PARTNER_TYPE_LABELS["other"])


def partner_type_options(counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    effective_counts = counts or {}
    return [
        {
            "id": partner_type,
            "label": label,
            "count": int(effective_counts.get(partner_type) or 0),
        }
        for partner_type, label in PARTNER_TYPE_DEFINITIONS
        if counts is None or int(effective_counts.get(partner_type) or 0) > 0
    ]
