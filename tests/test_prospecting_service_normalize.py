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
            "isVerifiedOwner": True,
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
    assert lead["is_verified"] is True
    assert lead["search_payload_json"].get("is_verified") is True


def test_normalize_google_hotel_payload_extracts_factual_fields() -> None:
    service = ProspectingService(api_token="", source="apify_google")
    items = [
        {
            "placeId": "0x14cab9a2ba4a9ac1:0x90792c333cf9f0ca",
            "title": "Nuray hotel",
            "categoryName": "Hotel",
            "categories": ["Hotel"],
            "address": "Sultan Ahmet, Akbıyık Değirmeni Sk. No:38, 34122 Fatih/İstanbul, Türkiye",
            "city": "Fatih",
            "url": "https://www.google.com/maps/search/?api=1&query=Nuray%20hotel&query_place_id=ChIJwZpKuqK5yhQRyvD5PDMseZA",
            "phone": "+90 532 326 81 24",
            "totalScore": 3.6,
            "reviewsCount": 107,
            "imageUrl": "https://example.com/hero.jpg",
            "imageUrls": ["https://example.com/gallery-1.jpg", "https://example.com/gallery-2.jpg"],
            "additionalInfo": {
                "Amenities": [
                    {"Free Wi-Fi": True},
                    {"Breakfast": True},
                    {"Parking": True},
                    {"Pool": False},
                ]
            },
            "reviews": [
                {"text": "Clean room and helpful staff", "rating": 4, "authorName": "A"},
                {"text": "Great location", "rating": 5, "authorName": "B"},
            ],
            "hotelReviewSummary": "Quiet hotel near the main attractions",
        }
    ]

    normalized = service.normalize_results(items)

    assert len(normalized) == 1
    lead = normalized[0]
    assert lead["rating"] == 3.6
    assert lead["reviews_count"] == 107
    assert lead["description"] == "Quiet hotel near the main attractions"
    assert len(lead["photos_json"]) >= 3
    assert len(lead["services_json"]) == 3
    assert {item["name"] for item in lead["services_json"]} == {"Free Wi-Fi", "Breakfast", "Parking"}
    assert len(lead["reviews_json"]) == 2
    assert lead["search_payload_json"].get("reviews_count") == 107


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
