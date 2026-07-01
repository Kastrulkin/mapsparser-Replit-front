from core.service_catalog_compression import build_service_catalog_compression_draft


def _service(service_id: str, name: str, category: str = "", price: str = "1000"):
    return {
        "id": service_id,
        "business_id": "biz-1",
        "category": category,
        "name": name,
        "description": "",
        "keywords": [],
        "price": price,
    }


def test_laser_epilation_grouping_keeps_source_ids_and_target() -> None:
    services = [
        _service("laser-1", "Лазерная эпиляция голени женщины", "Эпиляция", "1500"),
        _service("laser-2", "Лазерная эпиляция голени мужчины", "Эпиляция", "2000"),
        _service("laser-3", "Лазерная эпиляция бикини", "Эпиляция", "2500"),
    ]

    draft = build_service_catalog_compression_draft(services)
    group = next(item for item in draft["groups"] if item["rule_id"] == "laser_epilation")

    assert group["action"] == "apply"
    assert group["source_service_ids"] == ["laser-1", "laser-2", "laser-3"]
    assert group["target"]["category"] == "Лазерная эпиляция"
    assert draft["after_count"] == 1


def test_injections_group_by_family_and_preserve_keywords() -> None:
    services = [
        {**_service("inj-1", "Биоревитализация Revi 1 мл", "Косметология"), "keywords": ["биоревитализация"]},
        {**_service("inj-2", "Биоревитализация Revi 2 мл", "Косметология"), "keywords": ["revi"]},
        {**_service("inj-3", "Контурная пластика филлер 1 мл", "Косметология"), "keywords": ["филлер"]},
    ]

    draft = build_service_catalog_compression_draft(services)
    group = next(item for item in draft["groups"] if item["rule_id"] == "injectable_cosmetology")

    assert group["action"] == "apply"
    assert group["target"]["name"] == "Инъекционная косметология"
    assert "биоревитализация" in group["target"]["keywords"]
    assert "филлер" in group["target"]["keywords"]


def test_seasonal_offers_are_marked_as_promotion_not_created_service() -> None:
    services = [
        _service("promo-1", "Сезонное предложение: уход лицо", "Акции"),
        _service("promo-2", "Сезонное предложение: лазер", "Акции"),
        _service("promo-3", "Сезонное предложение: массаж", "Акции"),
    ]

    draft = build_service_catalog_compression_draft(services)
    group = next(item for item in draft["groups"] if item["rule_id"] == "seasonal_offers")

    assert group["action"] == "promotion"
    assert group["recommended_count"] == 0
    assert draft["after_count"] == 0


def test_overloaded_category_gets_cleanup_group() -> None:
    services = [_service(f"svc-{index}", f"Услуга {index}", "Уходы") for index in range(30)]

    draft = build_service_catalog_compression_draft(services)
    group = next(item for item in draft["groups"] if item["rule_id"] == "overloaded_category")

    assert group["title"] == "Уходы"
    assert len(group["source_service_ids"]) == 30
    assert group["target"]["category"] == "Уходы"


def test_podology_and_nail_services_are_separate_groups() -> None:
    services = [
        _service("nail-1", "Гигиенический педикюр", "Маникюр и педикюр", "3300"),
        _service("nail-2", "Маникюр мужской", "Маникюр и педикюр", "2500"),
        _service("nail-3", "Японский маникюр", "Маникюр и педикюр", "3000"),
        _service("nail-4", "Массаж локальный (стопы/ШВЗ/спина) 30 мин", "Маникюр и педикюр", "2000"),
        _service("pod-1", "Консультация подолога", "Подология", "1000"),
        _service("pod-2", "Обработка вросшего ногтя", "Подология", "2800"),
        _service("pod-3", "Установка титановой нити", "Подология", "2800"),
    ]

    draft = build_service_catalog_compression_draft(services)
    podology = next(item for item in draft["groups"] if item["rule_id"] == "podology_treatment_podology_nail_correction")
    nails = next(item for item in draft["groups"] if item["rule_id"] == "nail_service_nail_manicure")

    assert podology["target"]["name"] == "Коррекция ногтей у подолога"
    assert podology["source_service_ids"] == ["pod-2", "pod-3"]
    assert nails["target"]["name"] == "Маникюр"
    assert nails["source_service_ids"] == ["nail-2", "nail-3"]
    assert "nail-4" not in podology["source_service_ids"]
    assert "nail-4" not in nails["source_service_ids"]


def test_scar_aesthetics_split_into_actionable_groups() -> None:
    services = [
        _service("scar-1", "Коррекция рубцов: до 3 см", "Эстетика рубцов", "5000"),
        _service("scar-2", "Коррекция рубцов: до 6 см", "Эстетика рубцов", "8000"),
        _service("scar-3", "Абдоминопластика", "Эстетика рубцов", "39000"),
        _service("scar-4", "Блефаропластика", "Эстетика рубцов", "19000"),
        _service("scar-5", "Рубцы постакне, селфхарм", "Эстетика рубцов", "15000"),
        _service("scar-6", "Рубцы от удаления родинок и папиллом (шт.)", "Эстетика рубцов", "3000"),
    ]

    draft = build_service_catalog_compression_draft(services)
    by_rule = {item["rule_id"]: item for item in draft["groups"]}

    assert by_rule["scar_aesthetics_scar_by_size"]["target"]["name"] == "Коррекция рубцов по размеру"
    assert by_rule["scar_aesthetics_scar_after_surgery"]["target"]["name"] == "Коррекция рубцов после операций"
    assert by_rule["scar_aesthetics_scar_skin_marks"]["target"]["name"] == "Коррекция рубцов кожи и постакне"
    assert by_rule["scar_aesthetics_scar_by_size"]["recommended_count"] == 1


def test_external_services_are_not_grouped_for_apply_diff() -> None:
    services = [
        {**_service("ext-1", "Лазерная эпиляция голени", "Эпиляция"), "is_external": True},
        {**_service("ext-2", "Лазерная эпиляция бикини", "Эпиляция"), "is_external": True},
        {**_service("ext-3", "Лазерная эпиляция руки", "Эпиляция"), "is_external": True},
    ]

    draft = build_service_catalog_compression_draft(services)

    assert draft["before_count"] == 0
    assert draft["groups"] == []
