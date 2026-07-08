from wordstat_client import WordstatClient
from update_wordstat_data import _extract_queries


class _OkResponse:
    status_code = 200
    headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [{"phrase": "стрижка москва", "count": "123"}],
            "associations": [{"phrase": "парикмахерская", "count": "77"}],
        }


def test_cloud_wordstat_client_calls_search_api_v2(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _OkResponse()

    monkeypatch.setattr("wordstat_client.requests.post", fake_post)

    client = WordstatClient(api_key="test-key", folder_id="test-folder")
    data = client.get_popular_queries(["стрижка", "маникюр"], 213)

    assert len(data) == 2
    assert calls[0]["url"] == "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"
    assert calls[0]["headers"]["Authorization"] == "Api-Key test-key"
    assert calls[0]["json"]["folderId"] == "test-folder"
    assert calls[0]["json"]["phrase"] == "стрижка"
    assert calls[0]["json"]["regions"] == ["213"]
    assert calls[0]["json"]["devices"] == ["DEVICE_ALL"]


def test_extract_queries_supports_cloud_results_section():
    rows = _extract_queries({
        "results": [{"phrase": "стрижка москва", "count": "123"}],
        "associations": [{"phrase": "парикмахерская", "count": "77"}],
    })

    assert {"key": "стрижка москва", "clicks": 123} in rows
    assert {"key": "парикмахерская", "clicks": 77} in rows
