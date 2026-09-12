from external_sources import ExternalSource
from google_business_api import GoogleBusinessAPI
from google_business_sync_worker import GoogleBusinessSyncWorker


def test_search_keywords_uses_performance_api_and_paginates():
    api = GoogleBusinessAPI.__new__(GoogleBusinessAPI)
    calls = []
    responses = [
        {"searchKeywordsCounts": [{"searchKeyword": "airport transfer"}], "nextPageToken": "next"},
        {"searchKeywordsCounts": [{"searchKeyword": "phuket taxi"}]},
    ]

    def request(method, path, params=None):
        calls.append((method, path, params))
        return responses.pop(0)

    api._performance_json = request

    result = api.get_search_keywords(
        "accounts/1/locations/42",
        "2026-08-01T00:00:00Z",
        "2026-09-01T00:00:00Z",
    )

    assert [item["searchKeyword"] for item in result] == ["airport transfer", "phuket taxi"]
    assert calls[0][1] == "locations/42/searchkeywords/impressions/monthly"
    assert ("monthlyRange.startMonth.month", 8) in calls[0][2]
    assert ("pageToken", "next") in calls[1][2]


def test_google_sync_keeps_goal_metrics_and_search_queries():
    worker = GoogleBusinessSyncWorker.__new__(GoogleBusinessSyncWorker)
    worker.source = ExternalSource.GOOGLE_BUSINESS

    class Api:
        def get_insights(self, location_name, start_date, end_date):
            return {
                "multiDailyMetricTimeSeries": [{
                    "dailyMetricTimeSeries": [
                        {"dailyMetric": "BUSINESS_IMPRESSIONS_MOBILE_SEARCH", "timeSeries": {"datedValues": [{"date": {"year": 2026, "month": 9, "day": 10}, "value": "40"}]}},
                        {"dailyMetric": "CALL_CLICKS", "timeSeries": {"datedValues": [{"date": {"year": 2026, "month": 9, "day": 10}, "value": "3"}]}},
                        {"dailyMetric": "WEBSITE_CLICKS", "timeSeries": {"datedValues": [{"date": {"year": 2026, "month": 9, "day": 10}, "value": "5"}]}},
                        {"dailyMetric": "BUSINESS_DIRECTION_REQUESTS", "timeSeries": {"datedValues": [{"date": {"year": 2026, "month": 9, "day": 10}, "value": "2"}]}},
                        {"dailyMetric": "BUSINESS_BOOKINGS", "timeSeries": {"datedValues": [{"date": {"year": 2026, "month": 9, "day": 10}, "value": "1"}]}},
                    ]
                }]
            }

        def get_search_keywords(self, location_name, start_date, end_date):
            return [{"searchKeyword": "private school"}]

    worker._get_api_client = lambda account: Api()

    points = worker._fetch_stats({
        "id": "account-1",
        "business_id": "business-1",
        "external_id": "accounts/1/locations/42",
    })

    assert len(points) == 1
    assert points[0].views_total == 40
    assert points[0].clicks_total == 10
    assert points[0].actions_total == 11
    assert points[0].raw_payload["metrics"]["calls"] == 3
    assert points[0].raw_payload["metrics"]["website_clicks"] == 5
    assert points[0].raw_payload["metrics"]["directions"] == 2
    assert points[0].raw_payload["metrics"]["bookings"] == 1
    assert points[0].raw_payload["search_queries"] == [{"searchKeyword": "private school"}]
