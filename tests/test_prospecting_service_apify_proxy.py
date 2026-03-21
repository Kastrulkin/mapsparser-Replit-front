import os

from src.services.prospecting_service import ProspectingService


def test_resolve_apify_proxy_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("APIFY_PROXY_URL", "http://user:pass@proxy.local:33335")
    monkeypatch.delenv("APIFY_HTTP_PROXY", raising=False)
    monkeypatch.delenv("APIFY_HTTPS_PROXY", raising=False)

    service = ProspectingService(api_token="")
    proxy = service._resolve_apify_proxy()
    assert proxy.get("id") == "env"
    assert proxy.get("url") == "http://user:pass@proxy.local:33335"


def test_resolve_apify_proxy_from_db(monkeypatch) -> None:
    monkeypatch.delenv("APIFY_PROXY_URL", raising=False)
    monkeypatch.delenv("APIFY_HTTP_PROXY", raising=False)
    monkeypatch.delenv("APIFY_HTTPS_PROXY", raising=False)

    service = ProspectingService(api_token="")
    monkeypatch.setattr(
        service,
        "_load_proxy_from_db",
        lambda: {"id": "abc", "url": "http://proxy-db.local:33335"},
    )

    proxy = service._resolve_apify_proxy()
    assert proxy.get("id") == "abc"
    assert proxy.get("http") == "http://proxy-db.local:33335"
    assert proxy.get("https") == "http://proxy-db.local:33335"


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
    assert payload.get("query") == "salon"
    assert payload.get("city") == "Saint Petersburg"
    assert payload.get("maxItems") == 50
    assert payload.get("proxyConfiguration", {}).get("useApifyProxy") is True
