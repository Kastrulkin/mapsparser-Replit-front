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


def test_external_services_are_not_grouped_for_apply_diff() -> None:
    services = [
        {**_service("ext-1", "Лазерная эпиляция голени", "Эпиляция"), "is_external": True},
        {**_service("ext-2", "Лазерная эпиляция бикини", "Эпиляция"), "is_external": True},
        {**_service("ext-3", "Лазерная эпиляция руки", "Эпиляция"), "is_external": True},
    ]

    draft = build_service_catalog_compression_draft(services)

    assert draft["before_count"] == 0
    assert draft["groups"] == []
