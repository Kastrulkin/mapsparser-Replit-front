"""Canonical partner-type classification for prospecting leads.

Raw provider categories stay untouched in ``prospectingleads.category``.  This
module owns the stable product grouping used by API responses, UI filters, and
bulk outreach preparation.
"""

from __future__ import annotations

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


def partner_type_for_category(value: Any) -> str:
    """Return one stable product type for a raw provider category.

    Precedence is intentional.  A mixed ``медицинский центр / косметология``
    category is medicine; a mixed medical/dentistry category is dentistry.
    Every consumer receives the same result from this function.
    """
    category = _normalized_category(value)
    if not category:
        return "other"
    if _includes_any(category, ("жилой комплекс", "жилые комплексы", "апарт-отель", "апартаменты", "жк")):
        return "residential"
    if _includes_any(category, ("ветерин", "ветклиник", "зоомагазин", "кинолог", "питом", "амуници")):
        return "pets"
    if _includes_any(category, ("стоматолог", "зуботех", "dental")):
        return "dentistry"
    if _includes_any(category, ("медицин", "медцентр", "клиник", "диагност", "коррекция зрения", "поликлиник")):
        return "medicine"
    if _includes_any(category, ("фитнес", "спорт", "секци", "бассейн", "единоборств", "танц", "йог", "каток", "скалолаз")):
        return "sport"
    if _includes_any(category, ("ресторан", "кафе", "бар", "кофе", "столов", "быстрое питание", "доставка еды")):
        return "food"
    if _includes_any(category, ("фотостуд", "фотоуслуг", "видеосъем", "мероприят", "праздник", "свадеб")):
        return "photo_events"
    if _includes_any(category, ("beauty", "бьюти", "красот", "космет", "парфюм", "spa", "wellness", "массаж", "ногт")):
        return "beauty"
    if (
        _includes_any(category, ("детск", "ребен", "ребенок"))
        and _includes_any(category, ("магазин", "одеж", "обув", "товар", "игруш", "питание", "коляск", "мебель", "бутик"))
    ):
        return "children_retail"
    if _includes_any(category, ("детский сад", "ясли", "центр развития", "школа", "обучен", "образован", "логопед", "дефектолог", "репетитор", "курсы", "музыкаль")):
        return "children_education"
    if _includes_any(category, ("детск", "семейн", "досуг", "развлекатель", "игров", "аттракцион", "театр", "музей", "зоопарк", "экскурси", "мастерская", "город профессий")):
        return "children_leisure"
    if _includes_any(category, ("бизнес-центр", "торговый комплекс", "торговый центр")):
        return "commercial_centers"
    if _includes_any(category, ("магазин", "бутик", "торгов")):
        return "retail"
    return "other"


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
