from core.beauty_service_optimization import (
    apply_beauty_service_guardrails,
    beauty_canonical_service_key,
    extract_beauty_service_attributes,
    format_beauty_generation_context,
    is_beauty_optimization_context,
)


def test_extracts_beauty_specific_attributes() -> None:
    attrs = extract_beauty_service_attributes("Биоревитализация, препарат Belarti lift 1 ml")

    assert "Belarti lift" in attrs["product_or_drug"]
    assert "1 ml" in attrs["dosage_or_volume"]


def test_guardrails_preserve_extra_long_hair() -> None:
    result = apply_beauty_service_guardrails(
        original_name="Афро на экстра длинные волосы",
        optimized_name="Биозавивка афрокудри на длинные волосы",
        seo_description="Биозавивка афрокудри на длинные волосы: услуга по исходному формату записи.",
    )

    assert result["fallback_used"] is True
    assert "экстра длинные волосы" in result["optimized_name"].lower()


def test_guardrails_do_not_turn_one_zone_waxing_into_brows() -> None:
    result = apply_beauty_service_guardrails(
        original_name="Ваксинг (восковая депиляция) - 1 зона",
        optimized_name="Коррекция бровей воском",
        seo_description="Коррекция бровей воском: услуга по исходному формату записи.",
    )

    assert result["fallback_used"] is True
    assert result["optimized_name"] == "Ваксинг (восковая депиляция) - 1 зона"
    assert any("added_unconfirmed_zone" in item for item in result["guardrail_reasons"])


def test_guardrails_preserve_drug_and_volume() -> None:
    result = apply_beauty_service_guardrails(
        original_name="Биоревитализация, препарат Belarti lift 1 ml",
        optimized_name="Биоревитализация лица",
        seo_description="Биоревитализация лица: услуга по исходному формату записи.",
    )

    assert result["fallback_used"] is True
    assert "Belarti lift" in result["optimized_name"]
    assert "1 ml" in result["optimized_name"]


def test_guardrails_preserve_gender_and_age() -> None:
    male_result = apply_beauty_service_guardrails(
        original_name="Коррекция бровей Мужская",
        optimized_name="Коррекция бровей",
        seo_description="Коррекция бровей: услуга по исходному формату записи.",
    )
    child_result = apply_beauty_service_guardrails(
        original_name="Детская стрижка (12-15 лет)",
        optimized_name="Детская стрижка",
        seo_description="Детская стрижка: услуга по исходному формату записи.",
    )

    assert male_result["fallback_used"] is True
    assert "Мужская" in male_result["optimized_name"]
    assert child_result["fallback_used"] is True
    assert "12-15 лет" in child_result["optimized_name"]


def test_guardrails_reject_added_promo_words() -> None:
    result = apply_beauty_service_guardrails(
        original_name="Биозавивка Экстра длинные волосы",
        optimized_name="Профессиональная биозавивка на длинные волосы",
        seo_description="Профессиональная биозавивка дает стойкий результат.",
    )

    assert result["fallback_used"] is True
    assert "профессиональная" not in result["optimized_name"].lower()
    assert "стойкий результат" not in result["seo_description"].lower()


def test_guardrails_reject_unconfirmed_medical_claims_and_zones() -> None:
    result = apply_beauty_service_guardrails(
        original_name="Плазмотерапия - 2 пробирки",
        optimized_name="Плазмотерапия кожи головы и лица от выпадения волос и воспалений",
        seo_description="Процедура плазмотерапии стимулирует рост волос, улучшает состояние кожи лица и устраняет воспаления.",
    )

    assert result["fallback_used"] is True
    assert result["optimized_name"] == "Плазмотерапия - 2 пробирки"
    assert any("added_unconfirmed_medical_claim" in item for item in result["guardrail_reasons"])


def test_beauty_generation_context_lists_attributes() -> None:
    context = format_beauty_generation_context(
        "Афро на экстра длинные волосы\n"
        "Биоревитализация, препарат Belarti lift 1 ml"
    )

    assert "экстра длинные волосы" in context
    assert "Belarti lift" in context
    assert "1 ml" in context


def test_beauty_context_is_not_global_for_other_businesses() -> None:
    assert is_beauty_optimization_context(
        vertical_key="cafe",
        business_profile="Кафе | завтраки | кофе",
        service_name="Кофе с собой",
        category="drink",
    ) is False
    assert is_beauty_optimization_context(
        vertical_key="beauty",
        business_profile="Салон красоты",
        service_name="Кофе для гостей",
        category="other",
    ) is True


def test_canonical_key_supports_duplicate_style_reuse() -> None:
    first = beauty_canonical_service_key("Афро на экстра длинные волосы")
    second = beauty_canonical_service_key("Афро на экстра длинные волосы")

    assert first == second
