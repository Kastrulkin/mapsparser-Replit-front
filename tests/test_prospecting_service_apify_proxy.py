from src.services.prospecting_service import ProspectingService


def test_apify_actor_proxy_config_uses_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APIFY_ACTOR_PROXY_GROUPS", raising=False)
    monkeypatch.delenv("APIFY_ACTOR_PROXY_COUNTRY", raising=False)

    proxy = ProspectingService._apify_actor_proxy_config()
    assert proxy == {"useApifyProxy": True}


def test_apify_actor_proxy_config_uses_groups_and_country(monkeypatch) -> None:
    monkeypatch.setenv("APIFY_ACTOR_PROXY_GROUPS", "RESIDENTIAL,SHADER")
    monkeypatch.setenv("APIFY_ACTOR_PROXY_COUNTRY", "ru")

    proxy = ProspectingService._apify_actor_proxy_config()
    assert proxy.get("useApifyProxy") is True
    assert proxy.get("apifyProxyGroups") == ["RESIDENTIAL", "SHADER"]
    assert proxy.get("apifyProxyCountry") == "RU"


def test_build_run_input_yandex_format() -> None:
    service = ProspectingService(api_token="", source="apify_yandex")
    payload = service._build_run_input("restaurant", "Moscow", 100)
    assert payload.get("query") == ["restaurant"]
    assert payload.get("location") == "Moscow"
    assert payload.get("maxResults") == 100
    assert payload.get("category") == ""
    assert payload.get("language") == "ru"
    assert payload.get("enrichBusinessData") is False
    assert payload.get("maxPhotos") == 0
    assert payload.get("filterOpenNow") is False
    assert payload.get("filterCuisine") == []
    assert payload.get("filterPriceMin") is None
    assert payload.get("sortBy") == ""
    assert payload.get("proxyConfiguration", {}).get("useApifyProxy") is True


def test_selects_2gis_actor_from_env(monkeypatch) -> None:
    monkeypatch.setenv("APIFY_YANDEX_ACTOR_ID", "YANDEX_ACTOR")
    monkeypatch.setenv("APIFY_2GIS_ACTOR_ID", "TWOGIS_ACTOR")
    service = ProspectingService(api_token="", source="apify_2gis")
    assert service.actor_id == "TWOGIS_ACTOR"


def test_build_run_input_2gis_format() -> None:
    service = ProspectingService(api_token="", source="apify_2gis")
    payload = service._build_run_input("salon", "Saint Petersburg", 50)
    assert payload.get("query") == ["salon"]
    assert payload.get("city") == "Saint Petersburg"
    assert payload.get("maxItems") == 50
    assert payload.get("proxyConfiguration", {}).get("useApifyProxy") is True


def test_search_businesses_uses_run_search(monkeypatch) -> None:
    service = ProspectingService(api_token="token", source="apify_yandex")

    def fake_run_search(query: str, location: str, *, limit: int = 50, timeout_sec: int = 300):
        assert query == "АЗС Лукойл"
        assert location == "Санкт-Петербург"
        assert limit == 80
        assert timeout_sec > 0
        return {
            "items": [
                {"name": "Лукойл", "address": "СПб", "reviews_count": 12, "source_url": "https://yandex.ru/maps/org/1"},
                "skip-me",
            ]
        }

    monkeypatch.setattr(service, "run_search", fake_run_search)

    items = service.search_businesses("АЗС Лукойл", "Санкт-Петербург", 80)

    assert len(items) == 1
    assert items[0]["name"] == "Лукойл"
    assert items[0]["reviews_count"] == 12
    assert items[0]["source_url"] == "https://yandex.ru/maps/org/1"


def test_normalize_result_exposes_geo_coordinates() -> None:
    service = ProspectingService(api_token="", source="apify_yandex")

    normalized = service._normalize_result(
        {
            "title": "Лукойл",
            "address": "Санкт-Петербург, Железноводская улица, 1А",
            "businessId": "191280394455",
            "url": "https://yandex.com/maps/org/lukoyl/191280394455/",
            "website": "https://auto.lukoil.ru/",
            "reviewCount": 268,
            "categories": ["АЗС"],
            "latitude": 59.952875,
            "longitude": 30.261805,
        }
    )

    assert normalized["geo_lat"] == 59.952875
    assert normalized["geo_lon"] == 30.261805
