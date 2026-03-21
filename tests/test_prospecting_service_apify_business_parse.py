from src.services.prospecting_service import ProspectingService


def test_build_run_input_for_yandex_business_url() -> None:
    service = ProspectingService(api_token="", source="apify_yandex")
    run_input = service._build_run_input_for_map_url("https://yandex.ru/maps/org/vesyolaya_raschyoska/1221240931/")

    assert isinstance(run_input.get("startUrls"), list)
    assert run_input.get("startUrls")[0].get("url") == "https://yandex.ru/maps/org/vesyolaya_raschyoska/1221240931/"
    assert run_input.get("businessIds") == ["1221240931"]
    assert run_input.get("enrichBusinessData") is True


def test_build_run_input_for_2gis_business_url() -> None:
    service = ProspectingService(api_token="", source="apify_2gis")
    run_input = service._build_run_input_for_map_url("https://2gis.ru/spb/firm/70000001060001437")

    assert run_input.get("query") == "https://2gis.ru/spb/firm/70000001060001437"
    assert isinstance(run_input.get("startUrls"), list)
    assert run_input.get("startUrls")[0].get("url") == "https://2gis.ru/spb/firm/70000001060001437"
    assert int(run_input.get("maxItems")) == 1
