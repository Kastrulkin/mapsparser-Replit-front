#!/usr/bin/env python3
"""Verify real Redis ingestion metrics using an isolated disposable namespace."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import uuid

import redis

from services.web_tracking_observability import (
    METRICS_TTL_SECONDS,
    _minute_key,
    get_ingestion_metrics,
    record_ingestion_metrics,
)


def main() -> int:
    url = os.getenv("WEB_TRACKING_METRICS_REDIS_URL", "redis://redis:6379/0")
    os.environ["WEB_TRACKING_METRICS_PREFIX"] = f"localos:web_tracking:qa:{uuid.uuid4().hex}"
    client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    key = _minute_key(now)
    try:
        record_ingestion_metrics(
            status=202,
            outcome="accepted",
            latency_ms=74,
            received=12,
            accepted=10,
            duplicates=2,
            now=now,
            client=client,
        )
        record_ingestion_metrics(
            status=429,
            outcome="rate_limited",
            latency_ms=240,
            now=now,
            client=client,
        )
        metrics = get_ingestion_metrics(minutes=1, now=now, client=client)
        ttl = client.ttl(key)
        checks = {
            "available": metrics["available"] is True,
            "requests": metrics["requests"] == 2,
            "accepted": metrics["accepted"] == 10,
            "duplicates": metrics["duplicates"] == 2,
            "rejected_requests": metrics["rejected_requests"] == 1,
            "responses_4xx": metrics["responses_4xx"] == 1,
            "p50_ms": metrics["p50_ms"] == 100,
            "p95_ms": metrics["p95_ms"] == 250,
            "ttl": 0 < ttl <= METRICS_TTL_SECONDS,
        }
        print(json.dumps({"success": all(checks.values()), "checks": checks, "metrics": metrics, "ttl": ttl}, indent=2, sort_keys=True))
        return 0 if all(checks.values()) else 1
    finally:
        client.delete(key)


if __name__ == "__main__":
    raise SystemExit(main())
