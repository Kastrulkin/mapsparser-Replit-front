from src.core.card_audit import _extract_lead_import_payload
from src.services.prospecting_service import ProspectingService


def test_normalize_results_keeps_full_services_and_preview_count() -> None:
    service = ProspectingService(api_token="")
    menu_items = [
        {
            "name": f"Услуга {index}",
            "price": str(1000 + index),
            "category": "Основное меню",
        }
        for index in range(1, 41)
    ]
    items = [
        {
            "businessId": "24724791860",
            "title": "Дом красоты Capri",
            "address": "Ленинградская область, Кудрово, Областная улица, 1",
            "url": "https://yandex.ru/maps/org/24724791860",
            "rating": 4.8,
            "reviews": [{"id": "r1"}],
            "categories": ["Салон красоты"],
            "menu": {"items": menu_items},
        }
    ]

    normalized = service.normalize_results(items)

    assert len(normalized) == 1
    lead = normalized[0]
    assert len(lead["services_json"]) == 40
    assert len(lead["search_payload_json"]["menu_preview"]) == 30
    assert len(lead["search_payload_json"]["menu_full"]) == 40
    assert lead["search_payload_json"]["services_total_count"] == 40
    assert lead["search_payload_json"]["services_with_price_count"] == 40


def test_normalize_results_does_not_mix_profile_features_into_menu_services() -> None:
    service = ProspectingService(api_token="")
    items = [
        {
            "businessId": "153559548150",
            "title": "Хочу Красиво",
            "address": "Санкт-Петербург, Караваевская улица",
            "url": "https://yandex.ru/maps/org/153559548150",
            "categories": ["Косметология"],
            "menu": {
                "items": [
                    {"title": "Перманентный макияж бровей", "price": "10000"},
                    {"title": "Перманентный макияж век", "price": "10000"},
                    {"title": "Перманентный макияж губ", "price": "10000"},
                ],
                "totalItems": 3,
            },
            "features": {
                "cosmetology_services": ["пилинг", "RF-лифтинг"],
                "payment_method": ["наличными", "безналичная"],
                "promotions": ["бонусы", "спецпредложения"],
            },
        }
    ]

    lead = service.normalize_results(items)[0]

    assert [item["name"] for item in lead["services_json"]] == [
        "Перманентный макияж бровей",
        "Перманентный макияж век",
        "Перманентный макияж губ",
    ]
    assert lead["search_payload_json"]["services_total_count"] == 3
    assert lead["search_payload_json"]["services_with_price_count"] == 3


def test_normalize_results_does_not_present_features_as_a_missing_price_catalog() -> None:
    service = ProspectingService(api_token="")
    items = [
        {
            "businessId": "107657223262",
            "title": "Клиника скульптуры лица",
            "address": "Санкт-Петербург, Московский проспект",
            "url": "https://yandex.ru/maps/org/107657223262",
            "categories": ["Косметология"],
            "features": {
                "cosmetology_services": ["ботокс", "контурная пластика"],
                "dentist_services": ["ортодонтия", "лечение кариеса"],
            },
        }
    ]

    lead = service.normalize_results(items)[0]

    assert lead["services_json"] == []
    assert lead["search_payload_json"]["services_total_count"] == 0
    assert lead["search_payload_json"]["services_with_price_count"] == 0


def test_extract_lead_import_payload_prefers_full_services_count_over_preview_len() -> None:
    payload = _extract_lead_import_payload(
        {
            "search_payload_json": {
                "menu_preview": [
                    {"title": f"Услуга {index}", "price": "1000", "category": "preview"}
                    for index in range(1, 31)
                ],
                "menu_full": [
                    {"title": f"Услуга {index}", "price": "1000", "category": "full"}
                    for index in range(1, 164)
                ],
                "services_total_count": 163,
                "services_with_price_count": 163,
            }
        }
    )

    assert payload["services_total_count"] == 163
    assert payload["services_with_price_count"] == 163
    assert len(payload["services_preview"]) == 20
