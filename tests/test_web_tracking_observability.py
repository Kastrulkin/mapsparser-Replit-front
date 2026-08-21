from datetime import datetime, timezone

from services.web_tracking_observability import get_ingestion_metrics, record_ingestion_metrics


NOW = datetime(2026, 8, 16, 12, 34, tzinfo=timezone.utc)


class WritePipeline:
    def __init__(self):
        self.increments = []
        self.expirations = []

    def hincrby(self, key, field, amount):
        self.increments.append((key, field, amount))
        return self

    def expire(self, key, seconds):
        self.expirations.append((key, seconds))
        return self

    def execute(self):
        return []


class WriteClient:
    def __init__(self):
        self.value = WritePipeline()

    def pipeline(self, transaction=False):
        assert transaction is False
        return self.value


class ReadPipeline:
    def __init__(self, rows):
        self.rows = rows
        self.keys = []

    def hgetall(self, key):
        self.keys.append(key)
        return self

    def execute(self):
        return self.rows + [{}] * max(0, len(self.keys) - len(self.rows))


class ReadClient:
    def __init__(self, rows):
        self.value = ReadPipeline(rows)

    def pipeline(self, transaction=False):
        assert transaction is False
        return self.value


def test_records_safe_shared_response_counters_in_one_minute_bucket():
    client = WriteClient()

    record_ingestion_metrics(
        status=202,
        outcome="accepted",
        latency_ms=74,
        received=12,
        accepted=10,
        duplicates=2,
        now=NOW,
        client=client,
    )

    values = {field: amount for _key, field, amount in client.value.increments}
    assert values == {
        "requests": 1,
        "events_received": 12,
        "accepted": 10,
        "duplicates": 2,
        "responses_2xx": 1,
        "status_202": 1,
        "outcome_accepted": 1,
        "latency_le_100": 1,
    }
    assert client.value.expirations == [("localos:web_tracking:ingestion:202608161234", 172800)]


def test_aggregates_last_hour_and_returns_histogram_percentiles():
    client = ReadClient([
        {
            "requests": "5",
            "events_received": "50",
            "accepted": "45",
            "duplicates": "5",
            "responses_2xx": "5",
            "latency_le_50": "4",
            "latency_le_250": "1",
        },
        {
            "requests": "2",
            "rejected_requests": "2",
            "responses_4xx": "2",
            "latency_le_100": "2",
        },
    ])

    result = get_ingestion_metrics(minutes=60, now=NOW, client=client)

    assert result["available"] is True
    assert result["requests"] == 7
    assert result["accepted"] == 45
    assert result["duplicates"] == 5
    assert result["rejected_requests"] == 2
    assert result["p50_ms"] == 50
    assert result["p95_ms"] == 250
    assert result["p99_ms"] == 250
    assert len(client.value.keys) == 60


def test_redis_failure_never_escapes_ingestion_path():
    class BrokenClient:
        def pipeline(self, transaction=False):
            raise RuntimeError("redis unavailable")

    record_ingestion_metrics(
        status=500,
        outcome="ingestion_failed",
        latency_ms=20,
        now=NOW,
        client=BrokenClient(),
    )

    result = get_ingestion_metrics(now=NOW, client=BrokenClient())
    assert result["available"] is False
    assert result["requests"] == 0
