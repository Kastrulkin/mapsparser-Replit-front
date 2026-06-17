from src.api.admin_prospecting import (
    PARTNER_KIND_BUSINESS,
    PARTNER_KIND_RESIDENTIAL_COMPLEX,
    _build_partner_source_label,
    _is_residential_partner_card,
    _normalize_partner_candidate,
    _normalize_partner_card_for_response,
    _normalize_partner_kind,
)


def test_partner_kind_detects_residential_complex_from_russian_text() -> None:
    kind = _normalize_partner_kind("", "ЖК Новые кварталы", "жилой комплекс")

    assert kind == PARTNER_KIND_RESIDENTIAL_COMPLEX


def test_partner_kind_defaults_to_business_for_regular_partner() -> None:
    kind = _normalize_partner_kind("", "Органика", "салон красоты")

    assert kind == PARTNER_KIND_BUSINESS


def test_partner_kind_does_not_treat_dom_krasoty_as_residential() -> None:
    kind = _normalize_partner_kind("", "Дом красоты Capri", "салон красоты")

    assert kind == PARTNER_KIND_BUSINESS


def test_residential_partner_card_is_skipped_by_kind() -> None:
    card = {
        "partner_kind": "residential_complex",
        "partner_name": "ЖК Солнечный",
        "partner_category": "Недвижимость",
    }

    assert _is_residential_partner_card(card) is True


def test_partner_candidate_scoring_prefers_exact_name_and_address() -> None:
    card = {
        "partner_name": "Органика",
        "partner_address": "Саратов, улица Радищева, 10",
    }
    candidate = {
        "title": "Органика",
        "address": "Саратов, улица Радищева, 10",
        "url": "https://yandex.ru/maps/org/organika/123456",
        "rating": 4.9,
        "reviews": [{"id": "r1"}, {"id": "r2"}],
    }

    normalized = _normalize_partner_candidate(card, candidate)

    assert normalized["confidence"] >= 0.99
    assert normalized["yandex_maps_url"] == "https://yandex.ru/maps/org/organika/123456"
    assert normalized["reviews_count"] == 2


def test_partner_card_response_adds_source_label_and_residential_flag() -> None:
    payload = _normalize_partner_card_for_response(
        {
            "source_company_name": "Весёлая расчёска Энгельса",
            "partner_kind": "business",
            "partner_name": "Детская школа",
        }
    )

    assert payload["source_label"] == "Партнёр Весёлая расчёска Энгельса"
    assert payload["is_residential_complex"] is False


def test_partner_source_label_has_fallback() -> None:
    assert _build_partner_source_label({}) == "Партнёр компании"
