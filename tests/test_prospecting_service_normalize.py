from src.services.prospecting_service import ProspectingService


def test_normalize_results_uses_business_id_and_serializes_location() -> None:
    service = ProspectingService(api_token="")
    items = [
        {
            "businessId": "68466963715",
            "title": "Кебаб",
            "address": "Санкт-Петербург, Липовая аллея, 14А",
            "url": "https://yandex.ru/maps/org/68466963715",
            "rating": 4.7,
            "reviews": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}],
            "categories": ["Кафе"],
            "coordinates": {"lat": 59.99, "lng": 30.12},
            "description": "Кафе с шаурмой и кебабом",
            "logoUrl": "https://example.com/logo.png",
            "photos": [{"url": "https://example.com/photo1.jpg"}],
            "menu": [{"name": "Донер", "price": "450", "category": "Основное меню"}],
        }
    ]

    normalized = service.normalize_results(items)

    assert len(normalized) == 1
    lead = normalized[0]
    assert lead["source_external_id"] == "68466963715"
    assert lead["google_id"] == "68466963715"
    assert isinstance(lead["location"], str)
    assert "lat" in lead["location"]
    assert lead["reviews_count"] == 3
    assert lead["logo_url"] == "https://example.com/logo.png"
    assert lead["description"] == "Кафе с шаурмой и кебабом"
    assert isinstance(lead["photos_json"], list)
    assert isinstance(lead["services_json"], list)
    assert isinstance(lead["reviews_json"], list)
    assert isinstance(lead["raw_payload_json"], dict)
    assert isinstance(lead["search_payload_json"], dict)
    assert lead["search_payload_json"].get("logo_url") == "https://example.com/logo.png"
