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
