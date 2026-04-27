import json
import pytest

from src.services.prospecting_service import ProspectingService


def test_build_run_input_for_yandex_business_url() -> None:
    service = ProspectingService(api_token="", source="apify_yandex")
    run_input = service._build_run_input_for_map_url("https://yandex.ru/maps/org/vesyolaya_raschyoska/1221240931/")

    assert isinstance(run_input.get("startUrls"), list)
    assert run_input.get("startUrls")[0].get("url") == "https://yandex.ru/maps/org/vesyolaya_raschyoska/1221240931"
    assert run_input.get("businessIds") == ["1221240931"]
    assert run_input.get("enrichBusinessData") is True
    assert run_input.get("maxPhotos") == 20
    assert run_input.get("maxPosts") == 10


def test_build_run_input_for_2gis_business_url() -> None:
    service = ProspectingService(api_token="", source="apify_2gis")
    run_input = service._build_run_input_for_map_url("https://2gis.ru/spb/firm/70000001060001437")

    assert run_input.get("query") == ["https://2gis.ru/spb/firm/70000001060001437"]
    assert int(run_input.get("maxItems")) == 1


def test_build_run_input_for_google_business_url_preserves_raw_place_url_and_place_id() -> None:
    service = ProspectingService(api_token="", source="apify_google")
    raw_url = (
        "https://www.google.com/maps/place/Nuray+hotel/@41.003303,28.9747988,17z/"
        "data=!3m1!4b1!4m9!3m8!1s0x14cab9a2ba4a9ac1:0x90792c333cf9f0ca!"
        "5m2!4m1!1i2!8m2!3d41.003303!4d28.9773737!16s%2Fg%2F11g03kypph"
    )

    run_input = service._build_run_input_for_map_url(raw_url)

    assert run_input.get("startUrls")[0].get("url") == raw_url
    assert run_input.get("placeIds") == ["0x14cab9a2ba4a9ac1:0x90792c333cf9f0ca"]
    assert run_input.get("scrapePlaceDetailPage") is True


def test_build_run_input_for_google_search_url_uses_query_without_start_urls() -> None:
    service = ProspectingService(api_token="", source="apify_google")
    raw_url = "https://www.google.com/search?q=Transfer+Office&kgmid=/g/1hhh3vj4j"

    run_input = service._build_run_input_for_map_url(raw_url, city="Istanbul")

    assert run_input.get("searchStringsArray") == ["Transfer Office"]
    assert run_input.get("location") == "Istanbul"
    assert run_input.get("startUrls") in (None, [])
    assert run_input.get("placeIds") in (None, [])


def test_run_business_by_map_url_writes_apify_trace(tmp_path) -> None:
    service = ProspectingService(api_token="token", source="apify_yandex")

    service._start_run_with_input = lambda run_input: {
        "run_id": "run-1",
        "dataset_id": "dataset-1",
        "status": "RUNNING",
        "run_input": run_input,
    }
    service.get_run = lambda run_id: {"status": "SUCCEEDED", "defaultDatasetId": "dataset-1"}
    service.fetch_dataset_items = lambda dataset_id: [
        {
            "businessId": "154973111920",
            "title": "Test place",
            "address": "Санкт-Петербург, Невский проспект, 1",
            "city": "Санкт-Петербург",
            "url": "https://yandex.ru/maps/org/test/154973111920",
            "rating": 4.8,
            "reviewsCount": 14,
        }
    ]

    result = service.run_business_by_map_url(
        "https://yandex.ru/maps/org/test/154973111920/",
        timeout_sec=120,
        debug_bundle_dir=str(tmp_path),
        debug_context={"queue_id": "q-1"},
    )

    trace_path = tmp_path / "apify_trace.json"
    assert result.get("run_id") == "run-1"
    assert trace_path.exists()

    events = json.loads(trace_path.read_text(encoding="utf-8"))
    event_names = [str(item.get("event") or "") for item in events]

    assert "input_prepared" in event_names
    assert "run_started" in event_names
    assert "run_polled" in event_names
    assert "dataset_fetch_started" in event_names
    assert "run_succeeded" in event_names


def test_run_business_by_map_url_rejects_wrong_yandex_entity(tmp_path) -> None:
    service = ProspectingService(api_token="token", source="apify_yandex")

    service._start_run_with_input = lambda run_input: {
        "run_id": "run-1",
        "dataset_id": "dataset-1",
        "status": "RUNNING",
        "run_input": run_input,
    }
    service.get_run = lambda run_id: {"status": "SUCCEEDED", "defaultDatasetId": "dataset-1"}
    service.fetch_dataset_items = lambda dataset_id: [
        {
            "businessId": "999999999",
            "title": "Чужой бизнес",
            "address": "Москва, Тверская, 1",
            "url": "https://yandex.ru/maps/org/chuzhoy/999999999",
            "rating": 4.5,
            "reviewsCount": 12,
        }
    ]

    with pytest.raises(RuntimeError, match="Parsed entity mismatch"):
        service.run_business_by_map_url(
            "https://yandex.ru/maps/org/test/154973111920/",
            timeout_sec=120,
            debug_bundle_dir=str(tmp_path),
        )


def test_matches_requested_map_entity_accepts_exact_yandex_org_id_even_with_missing_city() -> None:
    normalized_item = {
        "source": "apify_yandex",
        "source_external_id": "26239780572",
        "name": "Girlie",
        "city": "",
        "address": "Санкт-Петербург, Каменноостровский проспект, 34",
        "source_url": "https://yandex.ru/maps/org/girlie/26239780572",
    }

    assert ProspectingService._matches_requested_map_entity(
        normalized_item=normalized_item,
        raw_item={"businessId": "26239780572"},
        map_url="https://yandex.ru/maps/org/girlie/26239780572/",
        city="Санкт-Петербург",
    ) is True


def test_matches_requested_map_entity_accepts_numeric_yandex_org_url_without_source_id() -> None:
    normalized_item = {
        "source": "apify_yandex",
        "source_external_id": "",
        "name": "Органика",
        "city": "Санкт-Петербург",
        "address": "Санкт-Петербург, проспект Испытателей, 35",
        "source_url": "",
    }

    assert ProspectingService._extract_query_from_map_url("https://yandex.ru/maps/org/230326995176/") == ""
    assert ProspectingService._matches_requested_map_entity(
        normalized_item=normalized_item,
        raw_item={},
        map_url="https://yandex.ru/maps/org/230326995176/",
        city="Санкт-Петербург",
    ) is True


def test_matches_requested_map_entity_accepts_google_district_when_address_contains_city() -> None:
    normalized_item = {
        "source": "apify_google",
        "name": "Transfer Office",
        "city": "Kadıköy",
        "address": "Konur İş Merkezi, Hasanpaşa, Uzunçayır Cd. No:2, 34722 Kadıköy/İstanbul, Türkiye",
        "source_url": "",
    }

    assert ProspectingService._matches_requested_map_entity(
        normalized_item=normalized_item,
        raw_item={},
        map_url="https://www.google.com/search?q=Transfer+Office&kgmid=/g/1hhh3vj4j",
        city="Istanbul",
    ) is True
