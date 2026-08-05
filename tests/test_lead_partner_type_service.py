from services.lead_partner_type_service import (
    PARTNER_TYPE_DEFINITIONS,
    partner_type_for_category,
    partner_type_label,
    partner_type_options,
    partner_types_for_category,
)


def test_canonical_partner_type_classification_covers_interface_groups() -> None:
    examples = {
        "Апарт-отель / жилой комплекс": "residential",
        "Медицинский центр / стоматология": "dentistry",
        "Диагностический центр / клиника": "medicine",
        "Детская спортивная секция": "sport",
        "Семейное кафе": "food",
        "Фотостудия и организация праздников": "photo_events",
        "Ветеринарная клиника / зоомагазин": "pets",
        "Салон красоты / SPA / массаж": "beauty",
        "Магазин детской одежды": "children_retail",
        "Детский сад / центр развития": "children_education",
        "Детский город профессий": "children_leisure",
        "Торговый центр": "commercial_centers",
        "Магазин товаров для дома": "retail",
        "Банк": "other",
    }
    assert {
        category: partner_type_for_category(category)
        for category in examples
    } == examples


def test_mixed_categories_have_one_explicit_precedence() -> None:
    assert partner_type_for_category("Медицинский центр / косметология") == "medicine"
    assert partner_type_for_category("Клиника / стоматология / косметология") == "dentistry"


def test_mixed_categories_remain_filterable_by_every_relevant_business_category() -> None:
    assert partner_types_for_category("Медицинский центр / косметология") == (
        "medicine",
        "beauty",
    )
    assert partner_types_for_category("Клиника / стоматология / косметология") == (
        "dentistry",
        "medicine",
        "beauty",
    )


def test_barbershops_and_hairdressers_are_beauty_not_food_or_other() -> None:
    assert partner_types_for_category("Салон красоты / барбершоп / парикмахерская") == (
        "beauty",
    )
    assert partner_types_for_category("Парикмахерская") == ("beauty",)
    assert partner_type_for_category("Бар") == "food"


def test_api_options_use_the_same_ids_labels_and_counts() -> None:
    options = partner_type_options({"beauty": 61, "medicine": 27})
    assert options == [
        {"id": "medicine", "label": "Медицина и клиники", "count": 27},
        {"id": "beauty", "label": "Красота и уход", "count": 61},
    ]
    assert partner_type_label("unknown") == "Прочие партнёры"
    assert len(PARTNER_TYPE_DEFINITIONS) == 14
